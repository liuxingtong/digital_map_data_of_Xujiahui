"""
合并 1.csv 与 2.csv 为 merged.csv
用法: python merge_csv.py
"""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "streetview_images"
OUTPUT = DATA_DIR / "merged.csv"

def main():
    p1 = DATA_DIR / "1.csv"
    p2 = DATA_DIR / "2.csv"
    if not p1.exists() or not p2.exists():
        print(f"错误: 需要 {p1.name} 和 {p2.name}")
        return
    print("正在合并 1.csv 与 2.csv...")
    df1 = pd.read_csv(p1, low_memory=False)
    df2 = pd.read_csv(p2, low_memory=False)
    merged = pd.concat([df1, df2], ignore_index=True)
    merged.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"已保存至 {OUTPUT}，共 {len(merged):,} 条记录")

if __name__ == "__main__":
    main()
