from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


@dataclass(frozen=True)
class TestSet:
    """Bọc danh sách câu hỏi để tiện truy cập và kiểm tra nguồn gốc."""

    samples: list[dict[str, Any]]
    source_path: Path | None = None
    loaded_from_cache: bool = False

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self):
        return iter(self.samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.samples[index]


def load_or_create_test_set(
    df: pd.DataFrame,
    output_path: str | Path | None = None,
    refresh: bool = False,
) -> TestSet:
    """Đọc lại test set đã lưu, nếu chưa có (hoặc `refresh=True`) thì sinh mới.

    Nhờ vậy bộ đề thi giữ nguyên giữa các lần chạy, tránh việc mỗi lần đánh giá
    lại sinh đề khác nhau khiến chỉ số Hit Rate / Token F1 không so sánh được.
    """
    path = Path(output_path) if output_path is not None else None

    if path is not None and path.exists() and not refresh:
        payload = read_json(path)
        if isinstance(payload, list) and payload:
            return TestSet(samples=payload, source_path=path, loaded_from_cache=True)

    samples = build_test_set(df, path)
    return TestSet(samples=samples, source_path=path, loaded_from_cache=False)


def build_test_set(df: pd.DataFrame, output_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Xây dựng bộ benchmark evaluation test set từ cleaned dataframe.

    Bao gồm 5 dạng câu hỏi dựa trên nội dung thực tế của các bài báo:
    1. summary: Tóm tắt nội dung nghiên cứu chính.
    2. authors: Ai là tác giả của nghiên cứu về chủ đề X?
    3. date: Nghiên cứu Y được công bố vào năm/tháng nào?
    4. category: Công trình này thuộc lĩnh vực chuyên môn nào?
    5. multi_hop: Câu hỏi kết hợp liên ngành giữa hai chủ đề.

    Mỗi mẫu trong test_set.json bắt buộc có:
    - id: Mã định danh mẫu test (eval_001, eval_002, ...)
    - type: Dạng câu hỏi (summary, authors, date, category, multi_hop)
    - question_type: Tương thích với luồng tính toán metrics
    - question: Câu hỏi truy vấn
    - ground_truth: Đáp án chuẩn từ dữ liệu thực tế của bài báo
    - ground_truth_doc_ids: Danh sách DOI / paper_id của các tài liệu liên quan
    """
    if df is None or len(df) < 5:
        raise ValueError(
            f"Dataframe must contain at least 5 documents, found: {len(df) if df is not None else 0}"
        )

    # Xây dựng bảng tra cứu theo paper_id và title để lấy thông tin thực tế
    paper_map_by_id = {str(row["paper_id"]): row for _, row in df.iterrows()}
    paper_map_by_title = {str(row["title"]).strip().lower(): row for _, row in df.iterrows()}

    def get_paper(paper_id: str, title: str | None = None, fallback_idx: int = 0) -> pd.Series:
        if paper_id in paper_map_by_id:
            return paper_map_by_id[paper_id]
        if title and title.strip().lower() in paper_map_by_title:
            return paper_map_by_title[title.strip().lower()]
        return df.iloc[fallback_idx % len(df)]

    # Chọn các paper đại diện từ tập dữ liệu thực tế
    p1 = get_paper(
        "10.1145/3637528.3671801",
        "Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
        0,
    )
    p2 = get_paper(
        "10.1145/3637528.3671802",
        "Data Observability and Quality Gates for Production RAG Systems",
        1,
    )
    p3 = get_paper(
        "10.1145/3637528.3671808",
        "Multi-Agent Consensus for High-Stakes Fact Verification",
        2,
    )
    p4 = get_paper(
        "10.1145/3637528.3671804",
        "Freshness SLAs for Real-Time LLM Knowledge Augmentation",
        3,
    )
    p5 = get_paper(
        "10.1145/3637528.3671805",
        "Evaluating Retrieval Precision with Token F1 and LLM Judges",
        4,
    )
    p6 = get_paper(
        "10.1145/3637528.3671807",
        "Synthetic Corruption Testing: Stress-Testing Vector Search Robustness",
        5,
    )
    p7 = get_paper(
        "10.1145/3637528.3671803",
        "Mitigating Ghost Vectors in Dense Retrieval via Idempotent Indexing",
        6,
    )
    p8 = get_paper(
        "10.1145/3637528.3671810",
        "Automated Data Quality Profiling with Great Expectations in CI/CD",
        7,
    )

    test_items: list[dict[str, Any]] = [
        # 1. summary: Tóm tắt nội dung nghiên cứu chính
        {
            "id": "eval_001",
            "type": "summary",
            "question_type": "summary",
            "question": f"What is the summary of the paper '{p1['title']}'?",
            "ground_truth": first_sentence(str(p1["summary"])),
            "ground_truth_doc_ids": [str(p1["paper_id"])],
        },
        {
            "id": "eval_002",
            "type": "summary",
            "question_type": "summary",
            "question": f"What is the summary of the paper '{p2['title']}'?",
            "ground_truth": first_sentence(str(p2["summary"])),
            "ground_truth_doc_ids": [str(p2["paper_id"])],
        },
        # 2. authors: Ai là tác giả của nghiên cứu về chủ đề X?
        {
            "id": "eval_003",
            "type": "authors",
            "question_type": "authors",
            "question": f"Who authored the research on '{p3['title']}'?",
            "ground_truth": str(p3.get("authors_joined") or ", ".join(p3.get("authors", []))),
            "ground_truth_doc_ids": [str(p3["paper_id"])],
        },
        {
            "id": "eval_004",
            "type": "authors",
            "question_type": "authors",
            "question": f"Who authored the research on '{p4['title']}'?",
            "ground_truth": str(p4.get("authors_joined") or ", ".join(p4.get("authors", []))),
            "ground_truth_doc_ids": [str(p4["paper_id"])],
        },
        # 3. date: Nghiên cứu Y được công bố vào năm/tháng nào?
        {
            "id": "eval_005",
            "type": "date",
            "question_type": "date",
            "question": f"When was the paper '{p5['title']}' published?",
            "ground_truth": str(p5["published"]),
            "ground_truth_doc_ids": [str(p5["paper_id"])],
        },
        {
            "id": "eval_006",
            "type": "date",
            "question_type": "date",
            "question": f"When was the paper '{p6['title']}' published?",
            "ground_truth": str(p6["published"]),
            "ground_truth_doc_ids": [str(p6["paper_id"])],
        },
        # 4. category: Công trình này thuộc lĩnh vực chuyên môn nào?
        {
            "id": "eval_007",
            "type": "category",
            "question_type": "category",
            "question": f"What categories describe the paper '{p7['title']}'?",
            "ground_truth": str(
                p7.get("categories_joined")
                or p7.get("primary_category")
                or ", ".join(p7.get("categories", []))
            ),
            "ground_truth_doc_ids": [str(p7["paper_id"])],
        },
        {
            "id": "eval_008",
            "type": "category",
            "question_type": "category",
            "question": f"What categories describe the paper '{p8['title']}'?",
            "ground_truth": str(
                p8.get("categories_joined")
                or p8.get("primary_category")
                or ", ".join(p8.get("categories", []))
            ),
            "ground_truth_doc_ids": [str(p8["paper_id"])],
        },
        # 5. multi_hop: Câu hỏi kết hợp liên ngành giữa hai chủ đề
        {
            "id": "eval_009",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": (
                f"How do '{p2['title']}' and '{p8['title']}' together "
                "address data quality and pipeline validation?"
            ),
            "ground_truth": first_sentence(str(p2["summary"])),
            "ground_truth_doc_ids": [str(p2["paper_id"]), str(p8["paper_id"])],
        },
        {
            "id": "eval_010",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": (
                f"How do '{p1['title']}' and '{p3['title']}' combine "
                "agentic reasoning with knowledge retrieval and verification?"
            ),
            "ground_truth": first_sentence(str(p1["summary"])),
            "ground_truth_doc_ids": [str(p1["paper_id"]), str(p3["paper_id"])],
        },
    ]

    if output_path is not None:
        write_json(Path(output_path), test_items)

    return test_items
