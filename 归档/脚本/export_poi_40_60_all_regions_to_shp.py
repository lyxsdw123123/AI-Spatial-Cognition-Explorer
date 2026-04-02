import os
import math
from typing import Dict, Iterable, List, Optional, Tuple
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from config.config import Config
from backend.map_service import MapServiceManager


def _haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371000.0
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    s = (math.sin(dlat / 2) ** 2) + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * (math.sin(dlng / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, s))))


def _rect_polygon(min_lat: float, min_lng: float, max_lat: float, max_lng: float, close: bool = True) -> List[Tuple[float, float]]:
    pts = [
        (min_lat, min_lng),
        (max_lat, min_lng),
        (max_lat, max_lng),
        (min_lat, max_lng),
    ]
    if close:
        pts.append(pts[0])
    return pts


def _amap_polygon_param(polygon: List[Tuple[float, float]]) -> str:
    return "|".join([f"{lng},{lat}" for lat, lng in polygon])


def _truncate(v: Optional[str], max_len: int = 254) -> str:
    if v is None:
        return ""
    s = str(v)
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _dedupe_key(poi_id: str, name: str, lat: float, lng: float) -> str:
    if poi_id:
        return f"id:{poi_id}"
    return f"n:{name}|{round(lat, 6)}|{round(lng, 6)}"


def _parse_region_from_source_shp(source_shp: str) -> str:
    p = os.path.normpath(str(source_shp))
    parts = p.split(os.sep)
    if len(parts) >= 2 and parts[0].lower() == "data":
        return parts[1]
    if len(parts) >= 2:
        return parts[-2]
    return p


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
        "polygon": _amap_polygon_param(polygon),
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
            pid = poi.get("id") or ""
            pname = poi.get("name") or ""
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


def _format_amap_raw_to_schema(poi: Dict) -> Optional[Dict]:
    loc = poi.get("location") or ""
    parts = loc.split(",")
    if len(parts) != 2:
        return None
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except Exception:
        return None

    pid = str(poi.get("id") or "")
    pname = str(poi.get("name") or "")
    if not pid or not pname:
        return None

    return {
        "id": _truncate(pid),
        "name": _truncate(pname),
        "type": _truncate(poi.get("type", "未知类型")),
        "typecode": _truncate(poi.get("typecode", "")),
        "address": _truncate(poi.get("address", "")),
        "tel": _truncate(poi.get("tel", "")),
        "business": _truncate(poi.get("business_area", poi.get("business", ""))),
        "tag": _truncate(poi.get("tag", "[]")),
        "geometry": Point(lng, lat),
        "_lat": lat,
        "_lng": lng,
    }


def _format_osm_formatted_to_schema(poi: Dict) -> Optional[Dict]:
    if not isinstance(poi, dict):
        return None
    loc = poi.get("location")
    if not (isinstance(loc, list) and len(loc) == 2):
        return None
    try:
        lat = float(loc[0])
        lng = float(loc[1])
    except Exception:
        return None

    pid = str(poi.get("id") or "")
    pname = str(poi.get("name") or "")
    if not pid or not pname:
        return None

    return {
        "id": _truncate(pid),
        "name": _truncate(pname),
        "type": _truncate(poi.get("type", "")),
        "typecode": _truncate(poi.get("typecode", "")),
        "address": _truncate(poi.get("address", "")),
        "tel": _truncate(poi.get("tel", "")),
        "business": "",
        "tag": "[]",
        "geometry": Point(lng, lat),
        "_lat": lat,
        "_lng": lng,
    }


def _read_local_poi_gdf(local_poi_shp: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(local_poi_shp, encoding="utf-8")
    if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
        try:
            gdf = gdf.to_crs(epsg=4326)
        except Exception:
            pass
    return gdf


def _try_get_lat_lng_from_row(row: pd.Series, geom) -> Optional[Tuple[float, float]]:
    try:
        if "latitude" in row and "longitude" in row:
            lat = row.get("latitude")
            lng = row.get("longitude")
            if lat is not None and lng is not None:
                return float(lat), float(lng)
    except Exception:
        pass

    try:
        if geom is not None and (not geom.is_empty):
            return float(geom.y), float(geom.x)
    except Exception:
        pass

    return None


def _merge_key_from_row(row: pd.Series, geom) -> str:
    poi_id = ""
    try:
        if "id" in row and row.get("id") is not None:
            poi_id = str(row.get("id")).strip()
    except Exception:
        poi_id = ""

    name = ""
    try:
        if "name" in row and row.get("name") is not None:
            name = str(row.get("name")).strip()
    except Exception:
        name = ""

    latlng = _try_get_lat_lng_from_row(row, geom)
    if latlng is None:
        return _dedupe_key(poi_id, name, 0.0, 0.0)
    lat, lng = latlng
    return _dedupe_key(poi_id, name, lat, lng)


def _build_remote_rows_for_schema(
    schema_cols: List[str],
    service_name: str,
    amap_raw_pois: Optional[List[Dict]] = None,
    osm_formatted_pois: Optional[List[Dict]] = None,
) -> List[Dict]:
    rows: List[Dict] = []

    def _empty_row() -> Dict:
        return {c: None for c in schema_cols}

    if amap_raw_pois:
        for poi in amap_raw_pois:
            rec = _format_amap_raw_to_schema(poi)
            if rec is None:
                continue
            row = _empty_row()
            if "id" in row:
                row["id"] = rec.get("id")
            if "name" in row:
                row["name"] = rec.get("name")
            if "type" in row:
                row["type"] = rec.get("type")
            if "typecode" in row:
                row["typecode"] = rec.get("typecode")
            if "address" in row:
                row["address"] = rec.get("address")
            if "tel" in row:
                row["tel"] = rec.get("tel")
            if "business" in row:
                row["business"] = rec.get("business")
            if "business_a" in row:
                row["business_a"] = rec.get("business")
            if "tag" in row:
                row["tag"] = rec.get("tag")
            if "service" in row:
                row["service"] = service_name
            if "distance" in row:
                row["distance"] = poi.get("distance") or "[]"
            if "latitude" in row:
                row["latitude"] = rec.get("_lat")
            if "longitude" in row:
                row["longitude"] = rec.get("_lng")
            if "geometry" in row:
                row["geometry"] = rec.get("geometry")
            rows.append(row)

    if osm_formatted_pois:
        for poi in osm_formatted_pois:
            rec = _format_osm_formatted_to_schema(poi)
            if rec is None:
                continue
            row = _empty_row()
            if "id" in row:
                row["id"] = rec.get("id")
            if "name" in row:
                row["name"] = rec.get("name")
            if "type" in row:
                row["type"] = rec.get("type")
            if "typecode" in row:
                row["typecode"] = rec.get("typecode")
            if "address" in row:
                row["address"] = rec.get("address")
            if "tel" in row:
                row["tel"] = rec.get("tel")
            if "business" in row:
                row["business"] = ""
            if "business_a" in row:
                row["business_a"] = ""
            if "tag" in row:
                row["tag"] = "[]"
            if "service" in row:
                row["service"] = service_name
            if "distance" in row:
                row["distance"] = "[]"
            if "latitude" in row:
                row["latitude"] = rec.get("_lat")
            if "longitude" in row:
                row["longitude"] = rec.get("_lng")
            if "geometry" in row:
                row["geometry"] = rec.get("geometry")
            rows.append(row)

    return rows


def export_all_regions_pois_40_60(
    boundary_csv_path: str,
    data_root: str,
    output_root: str,
    target_grid_sizes: List[int],
    poi_type: str = "",
    only_international: bool = False,
    only_missing_remote: bool = False,
    force_rebuild: bool = False,
    require_remote: bool = False,
    jobs: Optional[List[Tuple[str, int]]] = None,
    osm_max_tries: int = 3,
    osm_retry_sleep_s: float = 2.0,
):
    boundary_df = pd.read_csv(boundary_csv_path, encoding="utf-8-sig")
    boundary_df = boundary_df[boundary_df["target_grid_size"].isin([int(x) for x in target_grid_sizes])].copy()
    boundary_df["region"] = boundary_df["source_shp"].apply(_parse_region_from_source_shp)

    manager = MapServiceManager()
    regions = sorted(set(boundary_df["region"].tolist()))

    def _needs_remote_fetch(region_name: str, grid_size: int, local_rows: int) -> bool:
        out_shp = os.path.join(output_root, region_name, str(int(grid_size)), "POI数据.shp")
        if not os.path.exists(out_shp):
            return True
        try:
            out_gdf = gpd.read_file(out_shp, encoding="utf-8")
        except Exception:
            return True
        if "service" in out_gdf.columns:
            try:
                services = set([str(x).strip().lower() for x in out_gdf["service"].tolist() if x is not None])
                return "osm" not in services
            except Exception:
                pass
        try:
            return len(out_gdf) <= int(local_rows)
        except Exception:
            return True

    for region in regions:
        local_poi_shp = os.path.join(data_root, region, "POI数据.shp")
        if not os.path.exists(local_poi_shp):
            print(f"[SKIP] {region}: 本地POI数据不存在: {local_poi_shp}", flush=True)
            continue

        local_gdf = _read_local_poi_gdf(local_poi_shp)
        schema_cols = list(local_gdf.columns)
        geom_col = local_gdf.geometry.name
        if geom_col not in schema_cols:
            schema_cols.append(geom_col)

        region_rows = boundary_df[boundary_df["region"] == region]
        if region_rows.empty:
            print(f"[SKIP] {region}: 边界CSV缺少区域记录", flush=True)
            continue
        try:
            r0 = region_rows.iloc[0]
            r_center_lat = float(r0.get("center_lat"))
            r_center_lng = float(r0.get("center_lng"))
        except Exception:
            r_center_lat = None
            r_center_lng = None

        is_domestic = False
        try:
            if r_center_lat is not None and r_center_lng is not None:
                is_domestic = bool(manager.is_domestic_region(r_center_lng, r_center_lat))
        except Exception:
            is_domestic = False

        if only_international and is_domestic:
            print(f"[SKIP] {region}: 国内区域，按要求跳过", flush=True)
            continue

        for grid_size in target_grid_sizes:
            if jobs is not None and (region, int(grid_size)) not in jobs:
                continue

            df_r = boundary_df[(boundary_df["target_grid_size"] == int(grid_size)) & (boundary_df["region"] == region)]
            if df_r.empty:
                print(f"[SKIP] {region} {grid_size}: 边界CSV缺少记录", flush=True)
                continue
            row = df_r.iloc[0]

            if (not force_rebuild) and only_missing_remote and not _needs_remote_fetch(region, int(grid_size), len(local_gdf)):
                print(f"[SKIP] {region} {grid_size}: 已有OSM结果或已扩充，跳过", flush=True)
                continue

            min_lat = float(row["min_lat"])
            min_lng = float(row["min_lng"])
            max_lat = float(row["max_lat"])
            max_lng = float(row["max_lng"])
            center_lat = float(row.get("center_lat") or (min_lat + max_lat) / 2.0)
            center_lng = float(row.get("center_lng") or (min_lng + max_lng) / 2.0)

            polygon = _rect_polygon(min_lat, min_lng, max_lat, max_lng, close=True)

            amap_raw: List[Dict] = []
            osm_formatted: List[Dict] = []
            service_name = "local"
            use_amap = is_domestic and bool(Config.AMAP_API_KEY) and Config.AMAP_API_KEY != "YOUR_AMAP_API_KEY"
            if use_amap:
                try:
                    amap_raw = fetch_amap_pois_in_polygon_all(polygon, poi_type=poi_type)
                    service_name = "amap"
                except Exception as e:
                    if require_remote:
                        raise
                    print(f"[WARN] {region} {grid_size}: 高德获取失败: {e}", flush=True)
                    amap_raw = []
                    service_name = "local"
            else:
                last_err = None
                for attempt in range(1, max(1, int(osm_max_tries)) + 1):
                    try:
                        tmp = manager.osm_service.get_poi_in_polygon(polygon, poi_type=poi_type)
                        if tmp:
                            osm_formatted = tmp
                            service_name = "osm"
                            last_err = None
                            break
                        osm_formatted = []
                        service_name = "local"
                        last_err = RuntimeError("empty_result")
                    except Exception as e:
                        last_err = e
                        osm_formatted = []
                        service_name = "local"
                    if attempt < int(osm_max_tries):
                        time.sleep(float(osm_retry_sleep_s) * float(attempt))
                if require_remote and (service_name != "osm" or len(osm_formatted) == 0):
                    raise RuntimeError(f"{region} {grid_size}: OSM获取失败或结果为空: {last_err}")

            remote_rows = _build_remote_rows_for_schema(schema_cols, service_name=service_name, amap_raw_pois=amap_raw, osm_formatted_pois=osm_formatted)
            remote_gdf = gpd.GeoDataFrame(remote_rows, geometry=geom_col, crs="EPSG:4326") if remote_rows else gpd.GeoDataFrame(columns=schema_cols, geometry=geom_col, crs="EPSG:4326")

            combined = pd.concat([remote_gdf, local_gdf], ignore_index=True)
            combined = gpd.GeoDataFrame(combined, geometry=geom_col, crs="EPSG:4326")
            combined["_merge_key"] = combined.apply(lambda r: _merge_key_from_row(r, r[geom_col]), axis=1)
            combined = combined.drop_duplicates(subset=["_merge_key"], keep="last").drop(columns=["_merge_key"])

            if "OBJECTID" in combined.columns:
                combined["OBJECTID"] = list(range(1, len(combined) + 1))

            out_dir = os.path.join(output_root, region, str(int(grid_size)))
            os.makedirs(out_dir, exist_ok=True)
            out_shp = os.path.join(out_dir, "POI数据.shp")
            combined.to_file(out_shp, driver="ESRI Shapefile", encoding="utf-8")

            local_keys = set([_merge_key_from_row(r, r[geom_col]) for _, r in local_gdf.iterrows()])
            out_keys = set([_merge_key_from_row(r, r[geom_col]) for _, r in combined.iterrows()])
            missing = [k for k in local_keys if k not in out_keys]
            if missing:
                raise RuntimeError(f"{region} {grid_size}: 输出未包含全部本地POI，缺失数量={len(missing)}")

            print(
                f"[OK] {region} {grid_size}: local={len(local_gdf)} remote={len(remote_gdf)} merged={len(combined)} -> {out_shp}",
                flush=True,
            )

    return output_root


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary-csv", default=os.path.join("txt_statistics", "大模型空间认知项目数据", "13不同格网", "边界汇总", "边界汇总.csv"))
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-root", default=os.path.join("txt_statistics", "大模型空间认知项目数据", "13不同格网", "地区"))
    parser.add_argument("--targets", default="40,60")
    parser.add_argument("--only-international", action="store_true", default=False)
    parser.add_argument("--only-missing-remote", action="store_true", default=False)
    parser.add_argument("--force-rebuild", action="store_true", default=False)
    parser.add_argument("--require-remote", action="store_true", default=False)
    parser.add_argument("--jobs", default="")
    parser.add_argument("--osm-max-tries", type=int, default=3)
    parser.add_argument("--osm-retry-sleep-s", type=float, default=2.0)
    args = parser.parse_args()

    targets = []
    for part in str(args.targets).split(","):
        part = part.strip()
        if part:
            targets.append(int(part))

    jobs = None
    jobs_str = str(args.jobs).strip()
    if jobs_str:
        jobs = []
        for token in jobs_str.split(";"):
            token = token.strip()
            if not token:
                continue
            if ":" not in token:
                continue
            region, gs = token.split(":", 1)
            region = region.strip()
            gs = gs.strip()
            if not region or not gs:
                continue
            jobs.append((region, int(gs)))

    saved_root = export_all_regions_pois_40_60(
        boundary_csv_path=args.boundary_csv,
        data_root=args.data_root,
        output_root=args.output_root,
        target_grid_sizes=targets,
        poi_type="",
        only_international=bool(args.only_international),
        only_missing_remote=bool(args.only_missing_remote),
        force_rebuild=bool(args.force_rebuild),
        require_remote=bool(args.require_remote),
        jobs=jobs,
        osm_max_tries=int(args.osm_max_tries),
        osm_retry_sleep_s=float(args.osm_retry_sleep_s),
    )
    print(os.path.abspath(saved_root))
