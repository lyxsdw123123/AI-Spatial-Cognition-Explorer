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


def build_merged_bounds_grid_cell_size_csv(
    data_root: str,
    output_csv_path: str,
    regions: List[str],
    grid_size: int = 30,
    grid_shp_name: str = "格网数据.shp",
):
    if not os.path.exists(data_root):
        raise FileNotFoundError(data_root)
    if not regions:
        raise ValueError("regions is empty")
    if int(grid_size) <= 0:
        raise ValueError("grid_size must be > 0")

    merged_bounds = None
    used_sources = []
    missing_sources = []

    for region in regions:
        shp_path = os.path.join(data_root, region, grid_shp_name)
        if not os.path.exists(shp_path):
            missing_sources.append(os.path.normpath(shp_path))
            continue

        gdf = gpd.read_file(shp_path, encoding="utf-8")
        try:
            if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
        except Exception:
            pass

        b = gdf.total_bounds
        if merged_bounds is None:
            merged_bounds = [float(x) for x in b]
        else:
            merged_bounds[0] = min(merged_bounds[0], float(b[0]))
            merged_bounds[1] = min(merged_bounds[1], float(b[1]))
            merged_bounds[2] = max(merged_bounds[2], float(b[2]))
            merged_bounds[3] = max(merged_bounds[3], float(b[3]))

        used_sources.append(os.path.normpath(shp_path))

    if merged_bounds is None:
        raise FileNotFoundError(f"未找到任何可用的格网数据: {grid_shp_name}")

    min_lat, min_lng, max_lat, max_lng = _boundary_from_total_bounds(merged_bounds)
    dx = (max_lng - min_lng) / float(grid_size)
    dy = (max_lat - min_lat) / float(grid_size)

    rows = []
    for row in range(int(grid_size)):
        for col in range(int(grid_size)):
            cell_min_lng = min_lng + dx * float(col)
            cell_max_lng = min_lng + dx * float(col + 1)
            cell_min_lat = min_lat + dy * float(row)
            cell_max_lat = min_lat + dy * float(row + 1)
            mid_lat = (cell_min_lat + cell_max_lat) / 2.0
            mid_lng = (cell_min_lng + cell_max_lng) / 2.0

            cell_height_m = _haversine_m(cell_min_lat, mid_lng, cell_max_lat, mid_lng)
            cell_width_m = _haversine_m(mid_lat, cell_min_lng, mid_lat, cell_max_lng)

            rows.append(
                {
                    "grid_size": int(grid_size),
                    "row": int(row),
                    "col": int(col),
                    "min_lat": float(cell_min_lat),
                    "min_lng": float(cell_min_lng),
                    "max_lat": float(cell_max_lat),
                    "max_lng": float(cell_max_lng),
                    "center_lat": float(mid_lat),
                    "center_lng": float(mid_lng),
                    "cell_height_m": float(cell_height_m),
                    "cell_width_m": float(cell_width_m),
                    "cell_height_deg": float(cell_max_lat - cell_min_lat),
                    "cell_width_deg": float(cell_max_lng - cell_min_lng),
                }
            )

    df = pd.DataFrame(rows)
    df.insert(0, "merged_boundary_corners_latlng", _boundary_str(min_lat, min_lng, max_lat, max_lng))
    df.insert(0, "missing_sources", ";".join(missing_sources))
    df.insert(0, "used_sources", ";".join(used_sources))
    df.insert(0, "regions", ",".join(regions))
    df.insert(0, "data_root", os.path.normpath(data_root))

    os.makedirs(os.path.dirname(output_csv_path) or ".", exist_ok=True)
    df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    return output_csv_path


def build_regions_grid_cell_size_summary_csv(
    data_root: str,
    output_csv_path: str,
    regions: List[str],
    grid_size: int = 30,
    grid_shp_name: str = "格网数据.shp",
):
    if not os.path.exists(data_root):
        raise FileNotFoundError(data_root)
    if not regions:
        raise ValueError("regions is empty")
    if int(grid_size) <= 0:
        raise ValueError("grid_size must be > 0")

    rows = []
    for region in regions:
        shp_path = os.path.join(data_root, region, grid_shp_name)
        if not os.path.exists(shp_path):
            rows.append({"区域": str(region), "长_m": None, "宽_m": None})
            continue

        gdf = gpd.read_file(shp_path, encoding="utf-8")
        try:
            if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)
        except Exception:
            pass

        min_lat, min_lng, max_lat, max_lng = _boundary_from_total_bounds(gdf.total_bounds)
        mid_lat = (min_lat + max_lat) / 2.0
        mid_lng = (min_lng + max_lng) / 2.0
        total_height_m = _haversine_m(min_lat, mid_lng, max_lat, mid_lng)
        total_width_m = _haversine_m(mid_lat, min_lng, mid_lat, max_lng)

        rows.append(
            {
                "区域": str(region),
                "长_m": float(total_height_m) / float(grid_size),
                "宽_m": float(total_width_m) / float(grid_size),
            }
        )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv_path) or ".", exist_ok=True)
    df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
    return output_csv_path


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
    default_out = os.path.join("data", "北京天安门", "格网边界缩放汇总.csv")
    parser = argparse.ArgumentParser()
    parser.add_argument("--shp", default=os.path.join("data", "北京天安门", "格网数据.shp"))
    parser.add_argument("--data-root", default="")
    parser.add_argument("--out", default=default_out)
    parser.add_argument("--base", type=int, default=30)
    parser.add_argument("--targets", default="20,50,80,100")
    parser.add_argument("--merged-cn-grid", action="store_true")
    parser.add_argument("--cn-grid-summary", action="store_true")
    parser.add_argument("--grid-size", type=int, default=30)
    parser.add_argument("--regions", default="北京天安门,上海外滩,广州塔,长沙五一广场,武汉黄鹤楼")
    args = parser.parse_args()

    if bool(args.cn_grid_summary):
        regions = []
        for part in str(args.regions).split(","):
            part = part.strip()
            if not part:
                continue
            regions.append(part)

        data_root = str(args.data_root).strip() or "data"
        raw_out = str(args.out).strip()
        out_path = (
            os.path.join("归档", "csv", "中国五区域_30x30_格网单元长宽.csv")
            if (not raw_out) or (os.path.normpath(raw_out) == os.path.normpath(default_out))
            else raw_out
        )

        saved = build_regions_grid_cell_size_summary_csv(
            data_root=data_root,
            output_csv_path=out_path,
            regions=regions,
            grid_size=int(args.grid_size),
        )
        print(os.path.abspath(saved))
        raise SystemExit(0)

    if bool(args.merged_cn_grid):
        regions = []
        for part in str(args.regions).split(","):
            part = part.strip()
            if not part:
                continue
            regions.append(part)

        data_root = str(args.data_root).strip() or "data"
        raw_out = str(args.out).strip()
        out_path = (
            os.path.join("归档", "csv", "中国五区域_30x30_格网单元长宽.csv")
            if (not raw_out) or (os.path.normpath(raw_out) == os.path.normpath(default_out))
            else raw_out
        )

        saved = build_merged_bounds_grid_cell_size_csv(
            data_root=data_root,
            output_csv_path=out_path,
            regions=regions,
            grid_size=int(args.grid_size),
        )
        print(os.path.abspath(saved))
        raise SystemExit(0)

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
