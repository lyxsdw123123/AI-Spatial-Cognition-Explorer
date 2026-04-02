import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterator


def iter_context_text_values(obj: Any) -> Iterator[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "context_text" and isinstance(v, str):
                yield v
            yield from iter_context_text_values(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_context_text_values(item)


def load_context_text(file_path: Path, context_index: int) -> str:
    raw_text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text

    values = list(iter_context_text_values(data))
    if not values:
        return ""
    if context_index < 0:
        context_index = 0
    if context_index >= len(values):
        context_index = 0
    return values[context_index]


def count_steps(context_text: str, pattern: re.Pattern[str]) -> int:
    if not context_text:
        return 0
    return len(pattern.findall(context_text))


def collect_files(input_dir: Path, glob_pattern: str) -> list[Path]:
    files = [p for p in input_dir.rglob(glob_pattern) if p.is_file()]
    files.sort(key=lambda p: str(p).lower())
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("txt_statistics")
        / "大模型空间认知项目数据"
        / "2三种记忆"
        / "三记忆+direct+是否有原始记忆"
        / "有",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("txt_statistics")
        / "大模型空间认知项目数据"
        / "2三种记忆"
        / "三记忆+direct+是否有原始记忆"
        / "有"
        / "三记忆统计思考次数2"
        / "三记忆_step统计.csv",
    )
    parser.add_argument("--glob", type=str, default="*.json")
    parser.add_argument("--context-index", type=int, default=0)
    parser.add_argument(
        "--thought-regex",
        type=str,
        default=r'(?m)^\s*(?:"step_index"|step_index)\s*:\s*\d+\s*,?\s*$',
    )
    parser.add_argument(
        "--step-regex",
        type=str,
        default=None,
        help="兼容旧参数：如传入则会覆盖 --thought-regex",
    )
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_csv: Path = args.output_csv
    glob_pattern: str = args.glob
    context_index: int = args.context_index
    regex_text = args.step_regex if args.step_regex else args.thought_regex
    thought_pattern = re.compile(regex_text)

    files = collect_files(input_dir, glob_pattern)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for file_path in files:
        try:
            context_text = load_context_text(file_path, context_index=context_index)
            step_count = count_steps(context_text, thought_pattern)
        except Exception:
            step_count = 0
        rows.append({"文件名": file_path.name, "step_index次数": step_count})

    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        extra_fields: set[str] = set()
        for row in rows:
            for k in row.keys():
                if k != "文件名":
                    extra_fields.add(k)
        fieldnames = ["文件名"] + sorted(extra_fields)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已处理文件数: {len(rows)}")
    print(f"CSV输出: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

