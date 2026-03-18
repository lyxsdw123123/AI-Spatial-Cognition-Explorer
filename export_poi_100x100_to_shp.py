import os
import math
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from config.config import Config


def _haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371000.0
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    s = (math.sin(dlat / 2) ** 2) + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * (math.sin(dlng / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, s))))


def _polygon_from_bounds(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> List[Tuple[float, float]]:
    return [
        (min_lat, min_lng),
        (max_lat, min_lng),
        (max_lat, max_lng),
        (min_lat, max_lng),
    ]


def _amap_polygon_str(polygon: List[Tuple[float, float]]) -> str:
    return "|".join([f"{lng},{lat}" for lat, lng in polygon])


def _truncate_str(v: Optional[str], max_len: int = 254) -> str:
    if v is None:
        return ""
    s = str(v)
    if len(s) <= max_len:
        return s
    return s[:max_len]


def fetch_amap_pois_in_polygon_all(
    polygon: List[Tuple[float, float]],
    poi_type: str = "",
    offset: int = 25,
    max_pages: int = 200,
    timeout_s: int = 30,
) -> List[Dict]:
    url = f"{Config.AMAP_BASE_URL}/place/polygon"
    params_base = {
        "key": Config.AMAP_API_KEY,
        "polygon": _amap_polygon_str(polygon),
        "types": poi_type,
        "output": "json",
        "extensions": "all",
        "offset": str(int(offset)),
    }

    seen_ids = set()
    out: List[Dict] = []
    total_count: Optional[int] = None

    for page in range(1, max_pages + 1):
        params = dict(params_base)
        params["page"] = str(page)
        resp = requests.get(url, params=params, timeout=timeout_s)
        data = resp.json()

        if data.get("status") != "1":
            raise RuntimeError(f"高德API错误: {data.get('info', '未知错误')} (infocode={data.get('infocode')})")

        if total_count is None:
            try:
                total_count = int(data.get("count") or 0)
            except Exception:
                total_count = None

        pois = data.get("pois") or []
        if not pois:
            break

        for poi in pois:
            if not isinstance(poi, dict):
                continue
            pid = poi.get("id")
            pname = poi.get("name")
            loc = poi.get("location") or ""
            if not pid or not pname or not loc:
                continue
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            out.append(poi)

        if total_count is not None and page * int(offset) >= total_count:
            break

    return out


def _format_poi_to_schema(poi: Dict) -> Optional[Dict]:
    loc = poi.get("location") or ""
    parts = loc.split(",")
    if len(parts) != 2:
        return None
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except Exception:
        return None

    pid = poi.get("id")
    pname = poi.get("name")
    if not pid or not pname:
        return None

    return {
        "id": _truncate_str(pid, 80),
        "name": _truncate_str(pname, 80),
        "type": _truncate_str(poi.get("type", "未知类型"), 120),
        "typecode": _truncate_str(poi.get("typecode", ""), 20),
        "address": _truncate_str(poi.get("address", ""), 160),
        "tel": _truncate_str(poi.get("tel", ""), 80),
        "business": _truncate_str(poi.get("business_area", poi.get("business", "")), 80),
        "tag": _truncate_str(poi.get("tag", ""), 120),
        "geometry": Point(lng, lat),
        "_lat": lat,
        "_lng": lng,
    }


def export_pois_from_scaled_boundary_csv_to_shp(
    boundary_csv_path: str,
    target_grid_size: int,
    output_dir: str,
    output_basename: str,
    poi_type: str = "",
):
    if not Config.AMAP_API_KEY or Config.AMAP_API_KEY == "YOUR_AMAP_API_KEY":
        raise RuntimeError("未配置AMAP_API_KEY环境变量")

    df = pd.read_csv(boundary_csv_path, encoding="utf-8-sig")
    df = df[df["target_grid_size"] == int(target_grid_size)]
    if df.empty:
        raise RuntimeError(f"CSV中未找到 target_grid_size={target_grid_size} 的记录: {boundary_csv_path}")

    row = df.iloc[0]
    min_lat = float(row["min_lat"])
    min_lng = float(row["min_lng"])
    max_lat = float(row["max_lat"])
    max_lng = float(row["max_lng"])

    polygon = _polygon_from_bounds(min_lat, min_lng, max_lat, max_lng)
    raw_pois = fetch_amap_pois_in_polygon_all(polygon, poi_type=poi_type)

    records: List[Dict] = []
    for p in raw_pois:
        rec = _format_poi_to_schema(p)
        if rec is not None:
            records.append(rec)

    if not records:
        raise RuntimeError("未获取到任何POI")

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")

    cols = ["id", "name", "type", "typecode", "address", "tel", "business", "tag", "geometry"]
    gdf = gdf[cols]
    gdf.insert(0, "OBJECTID", list(range(1, len(gdf) + 1)))

    os.makedirs(output_dir, exist_ok=True)
    shp_path = os.path.join(output_dir, f"{output_basename}.shp")
    gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")
    return shp_path


if __name__ == "__main__":
    boundary_csv = os.path.join("data", "北京天安门", "格网边界缩放汇总.csv")
    out_dir = os.path.join("data", "北京天安门", "不同格网POI数据")
    shp_path = export_pois_from_scaled_boundary_csv_to_shp(
        boundary_csv_path=boundary_csv,
        target_grid_size=100,
        output_dir=out_dir,
        output_basename="POI数据_100x100",
        poi_type="",
    )
    print(os.path.abspath(shp_path))
