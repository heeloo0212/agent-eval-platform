from __future__ import annotations

import csv
import io
import json

from .models import DatasetCase

REQUIRED_COLUMNS = {"Case_ID", "Category", "Query", "Expected_Output"}


def parse_dataset_file(filename: str, content: bytes) -> list[DatasetCase]:
    text = content.decode("utf-8-sig")
    suffix = filename.lower().rsplit(".", 1)[-1]

    if suffix == "csv":
        rows = list(csv.DictReader(io.StringIO(text)))
    elif suffix == "jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        raise ValueError("仅支持 CSV 或 JSONL 文件")

    if not rows:
        raise ValueError("数据集不能为空")

    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise ValueError(f"缺少字段: {', '.join(sorted(missing))}")

    return [DatasetCase.model_validate(row) for row in rows]
