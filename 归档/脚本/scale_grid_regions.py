import os
import math
import geopandas as gpd
import pandas as pd
import argparse
from typing import List


def _haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371000.0
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    s = (math.sin(dlat / 2) ** 2) + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * (math.sin(dlng / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, s))))


def _boundary_from_total_bounds(bounds):
    min_lng, min_lat, max_lng, max_lat = bounds
    return float(min_lat), float(min_lng), float(max_lat), float(max_lng)


def _scaled_bounds(min_lat: float, min_lng: float, max_lat: float, max_lng: float, scale: float):
    c_lat = (min_lat + max_lat) / 2.0
    c_lng = (min_lng + max_lng) / 2.0
    half_h = (max_lat - min_lat) / 2.0
    half_w = (max_lng - min_lng) / 2.0
    nh = half_h * scale
    nw = half_w * scale
    return (c_lat - nh), (c_lng - nw), (c_lat + nh), (c_lng + nw)


def _boundary_str(min_lat: float, min_lng: float, max_lat: float, max_lng: float) -> str:
    return f"({min_lat},{min_lng});({max_lat},{min_lng});({max_lat},{max_lng});({min_lat},{max_lng})"


def build_scaled_grid_boundary_csv(
    shp_path: str,
    output_csv_path: str,
    base_grid_size: int = 30,
    target_grid_sizes=None,
):
    if target_grid_sizes is None:
        target_grid_sizes = [20, 50, 80, 100]

    if not os.path.exists(shp_path):
        raise FileNotFoundError(shp_path)

    gdf = gpd.read_file(shp_path, encoding="utf-8")
    try:
        if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
    except Exception:
        pass

    min_lat, min_lng, max_lat, max_lng = _boundary_from_total_bounds(gdf.total_bounds)
    c_lat = (min_lat + max_lat) / 2.0
    c_lng = (min_lng + max_lng) / 2.0

    rows = []
    for gs in target_grid_sizes:
        scale = float(gs) / float(base_grid_size)
        n_min_lat, n_min_lng, n_max_lat, n_max_lng = _scaled_bounds(min_lat, min_lng, max_lat, max_lng, scale)

        mid_lat = (n_min_lat + n_max_lat) / 2.0
        mid_lng = (n_min_lng + n_max_lng) / 2.0
        vert_m = _haversine_m(n_min_lat, mid_lng, n_max_lat, mid_lng)
        hori_m = _haversine_m(mid_lat, n_min_lng, mid_lat, n_max_lng)

        cell_edge_m = (vert_m / float(gs) + hori_m / float(gs)) / 2.0 if gs > 0 else 0.0
        step_div = max(1, gs - 1)
        cell_step_m = (vert_m / float(step_div) + hori_m / float(step_div)) / 2.0

        rows.append(
            {
                "source_shp": os.path.normpath(shp_path),
                "base_grid_size": int(base_grid_size),
                "target_grid_size": int(gs),
                "scale_factor": scale,
                "center_lat": c_lat,
                "center_lng": c_lng,
                "min_lat": n_min_lat,
                "min_lng": n_min_lng,
                "max_lat": n_max_lat,
                "max_lng": n_max_lng,
                "boundary_corners_latlng": _boundary_str(n_min_lat, n_min_lng, n_max_lat, n_max_lng),
                "cell_edge_m": cell_edge_m,
                "cell_step_m": cell_step_m,
            }
        )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv_path) or ".", exist_ok=True)
    df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    return output_csv_path


def build_scaled_grid_boundary_csv_for_data_root(
    data_root: str,
    output_csv_path: str,
    base_grid_size: int,
    target_grid_sizes: List[int],
    grid_shp_name: str = "格网数据.shp",
):
    if not os.path.exists(data_root):
        raise FileNotFoundError(data_root)

    rows = []
    subfolders = [f for f in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, f))]
    subfolders.sort()

    for region in subfolders:
        shp_path = os.path.join(data_root, region, grid_shp_name)
        if not os.path.exists(shp_path):
            continue

        gdf = gpd.read_file(shp_path, encoding="utf-8")
        try:
            if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
        except Exception:
            pass

        min_lat, min_lng, max_lat, max_lng = _boundary_from_total_bounds(gdf.total_bounds)
        c_lat = (min_lat + max_lat) / 2.0
        c_lng = (min_lng + max_lng) / 2.0

        for gs in target_grid_sizes:
            scale = float(gs) / float(base_grid_size)
            n_min_lat, n_min_lng, n_max_lat, n_max_lng = _scaled_bounds(min_lat, min_lng, max_lat, max_lng, scale)

            mid_lat = (n_min_lat + n_max_lat) / 2.0
            mid_lng = (n_min_lng + n_max_lng) / 2.0
            vert_m = _haversine_m(n_min_lat, mid_lng, n_max_lat, mid_lng)
            hori_m = _haversine_m(mid_lat, n_min_lng, mid_lat, n_max_lng)

            cell_edge_m = (vert_m / float(gs) + hori_m / float(gs)) / 2.0 if gs > 0 else 0.0
            step_div = max(1, gs - 1)
            cell_step_m = (vert_m / float(step_div) + hori_m / float(step_div)) / 2.0

            rows.append(
                {
                    "source_shp": os.path.normpath(shp_path),
                    "base_grid_size": int(base_grid_size),
                    "target_grid_size": int(gs),
                    "scale_factor": scale,
                    "center_lat": c_lat,
                    "center_lng": c_lng,
                    "min_lat": n_min_lat,
                    "min_lng": n_min_lng,
                    "max_lat": n_max_lat,
                    "max_lng": n_max_lng,
                    "boundary_corners_latlng": _boundary_str(n_min_lat, n_min_lng, n_max_lat, n_max_lng),
                    "cell_edge_m": cell_edge_m,
                    "cell_step_m": cell_step_m,
                }
            )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv_path) or ".", exist_ok=True)
    df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    return output_csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shp", default=os.path.join("data", "北京天安门", "格网数据.shp"))
    parser.add_argument("--data-root", default="")
    parser.add_argument("--out", default=os.path.join("data", "北京天安门", "格网边界缩放汇总.csv"))
    parser.add_argument("--base", type=int, default=30)
    parser.add_argument("--targets", default="20,50,80,100")
    args = parser.parse_args()

    targets = []
    for part in str(args.targets).split(","):
        part = part.strip()
        if not part:
            continue
        targets.append(int(part))

    if str(args.data_root).strip():
        saved = build_scaled_grid_boundary_csv_for_data_root(
            data_root=str(args.data_root).strip(),
            output_csv_path=args.out,
            base_grid_size=int(args.base),
            target_grid_sizes=targets,
        )
    else:
        saved = build_scaled_grid_boundary_csv(args.shp, args.out, base_grid_size=int(args.base), target_grid_sizes=targets)
    print(os.path.abspath(saved))
