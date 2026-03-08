"""
裁剪人口栅格到徐家汇范围
========================
用法: python clip_population.py

依赖: pip install rasterio shapely

输出: population/ 目录下的多个裁剪后 TIF
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# ==================== 配置 ====================
POP_BASE = Path(r"F:\Aworks\2026studio\xujiahui\population")

# 源文件路径 -> 输出文件名（每个键可对应多个候选路径，取第一个存在的）
SOURCES = {
    "population_age65above": [
        POP_BASE / "population_age65above" / "population_age65above.tif",
        POP_BASE / "population_age65above.tif",
    ],
    "population_age0_14": [POP_BASE / "population_age0_14.tif"],
    "population_age15_59": [POP_BASE / "population_age15_59.tif"],
    "population_age60_64": [POP_BASE / "population_age60_64.tif"],
    "population_total_pop": [POP_BASE / "population_total_pop.tif"],
}

LON_MIN, LON_MAX = 121.37, 121.48
LAT_MIN, LAT_MAX = 31.12, 31.23
OUT_DIR = Path(__file__).parent / "population"


def clip_one(src_path: Path, out_name: str) -> bool:
    try:
        import rasterio
        from rasterio.mask import mask
        from rasterio.crs import CRS
        from shapely.geometry import box, mapping
    except ImportError as e:
        print(f"Missing deps: {e}\nRun: pip install rasterio shapely")
        return False

    if not src_path.exists():
        print(f"Skip (not found): {src_path}")
        return False

    bbox = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)
    bbox_geom = [mapping(bbox)]

    with rasterio.open(src_path) as src:
        target_crs = CRS.from_epsg(4326)
        if src.crs != target_crs:
            from rasterio.warp import transform_geom
            bbox_geom = [transform_geom(target_crs, src.crs, mapping(bbox))]
        out_image, out_transform = mask(src, bbox_geom, crop=True, nodata=src.nodata)
        out_meta = src.meta.copy()

    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform,
        "compress": "lzw",
    })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{out_name}.tif"
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(out_image)

    data = out_image[0].astype(float)
    nodata = out_meta.get("nodata")
    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)
    valid = data[~np.isnan(data)]
    total = float(valid.sum()) if len(valid) > 0 else 0
    print(f"  OK {out_name}.tif  size {out_image.shape[2]}x{out_image.shape[1]}  total {total:,.0f}")
    return True


def main() -> None:
    print("Clipping population rasters to Xujiahui extent...")
    print(f"Bounds: lon [{LON_MIN}, {LON_MAX}], lat [{LAT_MIN}, {LAT_MAX}]\n")
    for name, paths in SOURCES.items():
        path_list = paths if isinstance(paths, list) else [paths]
        src = next((p for p in path_list if p.exists()), path_list[0])
        clip_one(src, name)
    print("\nDone.")


if __name__ == "__main__":
    main()
