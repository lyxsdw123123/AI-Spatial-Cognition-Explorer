from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

import geopandas as gpd


def _default_data_root(script_path: Path) -> Path:
    root_dir = script_path.resolve().parent
    return (
        root_dir
        / "txt_statistics"
        / "大模型空间认知项目数据"
        / "15不同格网4060数据"
        / "4060制作"
        / "区域"
    )


def _find_poi_shp(folder: Path, size: str) -> Optional[Path]:
    if not folder.exists():
        return None

    preferred = [
        folder / f"POI{size}.shp",
        folder / f"{size}POI.shp",
        folder / f"poi{size}.shp",
        folder / f"{size}poi.shp",
    ]
    for p in preferred:
        if p.exists():
            return p

    poi_shps = [p for p in folder.glob("*.shp") if "poi" in p.stem.lower()]
    sized = [p for p in poi_shps if size in p.stem]
    if sized:
        return sorted(sized, key=lambda x: x.name)[0]
    if len(poi_shps) == 1:
        return poi_shps[0]
    return None


def _count_features(shp_path: Path) -> int:
    gdf = gpd.read_file(shp_path)
    return int(len(gdf))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="统计15个区域在40/60文件夹下POI shp的要素数量，并输出CSV到项目根目录。"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(_default_data_root(Path(__file__))),
        help="区域数据根目录（默认指向 txt_statistics/.../4060制作/区域）",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parent / "poi_counts_4060_regions.csv"),
        help="输出CSV路径（默认输出到项目根目录）",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    if not data_root.exists():
        print(f"[ERROR] data_root不存在: {data_root}", file=sys.stderr)
        return 2

    region_dirs = sorted([p for p in data_root.iterdir() if p.is_dir()], key=lambda x: x.name)
    if not region_dirs:
        print(f"[ERROR] 未找到区域目录: {data_root}", file=sys.stderr)
        return 2

    rows = []
    for region_dir in region_dirs:
        row = {"区域": region_dir.name, "40POI": "", "60POI": ""}
        for size in ("40", "60"):
            shp = _find_poi_shp(region_dir / size, size)
            if shp is None:
                print(f"[WARN] 未找到POI shp: region={region_dir.name}, size={size}", file=sys.stderr)
                continue
            try:
                cnt = _count_features(shp)
            except Exception as e:
                print(
                    f"[WARN] 读取失败: region={region_dir.name}, size={size}, shp={shp} err={e}",
                    file=sys.stderr,
                )
                continue
            row[f"{size}POI"] = cnt
        rows.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["区域", "40POI", "60POI"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] 已输出: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

