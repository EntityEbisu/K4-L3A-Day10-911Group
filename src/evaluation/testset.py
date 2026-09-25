from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


_QUESTION_TYPES = ("summary", "authors", "date", "categories")


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    if df.empty:
        return []

    ordered = df.sort_values("paper_id").reset_index(drop=True)
    test_set: list[dict[str, Any]] = []
    for index in range(10):
        row = ordered.iloc[index % len(ordered)]
        qtype = _QUESTION_TYPES[index % 4]
        title = row["title"]
        paper_id = row["paper_id"]
        if qtype == "summary":
            question = f"Tóm tắt nội dung bài báo '{title}' là gì?"
            ground_truth = first_sentence(str(row.get("summary") or ""))
        elif qtype == "authors":
            question = f"Ai là tác giả của bài báo '{title}'?"
            ground_truth = str(row.get("authors_joined") or "")
        elif qtype == "date":
            question = f"Bài báo '{title}' được xuất bản / ngày công bố khi nào?"
            ground_truth = str(row.get("published") or "")
        else:
            question = f"Bài báo '{title}' thuộc lĩnh vực / chuyên ngành nào?"
            ground_truth = str(row.get("categories_joined") or row.get("primary_category") or "")
        test_set.append(
            {
                "id": f"eval_{index + 1:03d}",
                "question_type": qtype,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
