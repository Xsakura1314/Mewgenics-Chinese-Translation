import argparse
import csv
import os
from typing import Dict, List, Sequence, Tuple

SECTION_MARKER_PREFIX = "//"
LANGUAGE_KEYS = {"CURRENT_LANGUAGE_NAME", "CURRENT_LANGUAGE_SHIPPABLE"}


def normalize_header(field: str) -> str:
    return (field or "").lstrip("\ufeff")


def parse_reference_combined(reference_path: str) -> Tuple[List[str], List[str]]:
    with open(reference_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise SystemExit(f"参考 combined 为空: {reference_path}") from exc

        header = [normalize_header(col) for col in raw_header]
        order: List[str] = []
        for row in reader:
            if not row:
                continue
            first = (row[0] or "").strip()
            if first.startswith(SECTION_MARKER_PREFIX) and first.endswith(".csv"):
                file_name = first[len(SECTION_MARKER_PREFIX):].strip()
                order.append(file_name)

    if not order:
        raise SystemExit("未能从参考 combined 中提取任何分段顺序")

    return header, order


def read_csv_rows(file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return [], []

        fieldnames = [normalize_header(name) for name in reader.fieldnames]
        rows: List[Dict[str, str]] = []
        for row in reader:
            fixed: Dict[str, str] = {}
            for key, value in row.items():
                fixed[normalize_header(key)] = value if value is not None else ""
            rows.append(fixed)

    return fieldnames, rows


def to_output_row(source_row: Dict[str, str], output_columns: Sequence[str]) -> List[str]:
    return [source_row.get(col, "") for col in output_columns]


def build_combined_rows(
    text_dir: str,
    output_columns: Sequence[str],
    section_order: Sequence[str],
) -> Tuple[List[List[str]], List[str]]:
    rows_out: List[List[str]] = []
    warnings: List[str] = []

    # 先从 additions.csv 提取 CURRENT_LANGUAGE_* 作为 combined 顶部两行
    additions_path = os.path.join(text_dir, "additions.csv")
    language_rows_added = 0
    if os.path.isfile(additions_path):
        _, additions_rows = read_csv_rows(additions_path)
        for row in additions_rows:
            key = (row.get("KEY") or "").strip()
            if key in LANGUAGE_KEYS:
                rows_out.append(to_output_row(row, output_columns))
                language_rows_added += 1

    if language_rows_added == 0:
        warnings.append("未在 additions.csv 中找到 CURRENT_LANGUAGE_* 行，combined 顶部语言行将缺失")

    # 顶部空行（匹配官方 combined 结构）
    rows_out.append([""] * len(output_columns))

    for index, file_name in enumerate(section_order):
        file_path = os.path.join(text_dir, file_name)

        # 分段标题行：// filename.csv
        marker_row = [""] * len(output_columns)
        marker_row[0] = f"// {file_name}"
        rows_out.append(marker_row)

        if not os.path.isfile(file_path):
            warnings.append(f"缺少文件，已保留空分段: {file_name}")
        else:
            _, source_rows = read_csv_rows(file_path)
            for row in source_rows:
                key = (row.get("KEY") or "").strip()
                if file_name == "additions.csv" and key in LANGUAGE_KEYS:
                    continue
                rows_out.append(to_output_row(row, output_columns))

        # 分段之间插入空行（最后一个分段后不插）
        if index < len(section_order) - 1:
            rows_out.append([""] * len(output_columns))

    return rows_out, warnings


def write_combined(output_path: str, output_columns: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(list(output_columns))
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按官方 combined.csv 的列与文件顺序，将 data/text 下所有 csv 合并为 combined.csv"
    )
    parser.add_argument("text_dir", help="文本目录（例如 Mewgenics_CN_patch/data/text）")
    parser.add_argument(
        "--reference-combined",
        default=r"D:\steam\steamapps\common\Mewgenics\Output\data\text\combined.csv",
        help="参考 combined.csv 路径（用于读取列顺序与文件分段顺序）",
    )
    parser.add_argument(
        "--output",
        default="",
        help="输出路径，默认写到 text_dir/combined.csv",
    )
    args = parser.parse_args()

    text_dir = os.path.abspath(args.text_dir)
    if not os.path.isdir(text_dir):
        raise SystemExit(f"输入目录不存在: {text_dir}")

    reference_path = os.path.abspath(args.reference_combined)
    if not os.path.isfile(reference_path):
        raise SystemExit(f"参考 combined 不存在: {reference_path}")

    output_columns, section_order = parse_reference_combined(reference_path)
    rows, warnings = build_combined_rows(text_dir, output_columns, section_order)

    output_path = args.output.strip()
    if not output_path:
        output_path = os.path.join(text_dir, "combined.csv")
    elif not os.path.isabs(output_path):
        output_path = os.path.abspath(output_path)

    write_combined(output_path, output_columns, rows)

    print(f"sections: {len(section_order)}")
    print(f"rows written (without header): {len(rows)}")
    if warnings:
        print("warnings:")
        for message in warnings:
            print(f"  - {message}")
    print(f"combined written: {output_path}")


if __name__ == "__main__":
    main()
