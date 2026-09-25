from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import re
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


# Nguong toi thieu cho `summary`, dong bo voi expectation `ExpectColumnValueLengthsToBeBetween`
# o buoc Data Quality: dong nao ngan hon nguong nay bi coi la "dong xau" va loai bo.
MIN_SUMMARY_CHARS = 30

AUTHORS_FALLBACK = "Unknown"
CATEGORIES_FALLBACK = "Uncategorized"


def _field(record: Any, name: str, default: Any = None) -> Any:
    """Doc 1 truong tu PaperRecord (dataclass) hoac tu dict."""
    if isinstance(record, dict):
        return record.get(name, default)
    if is_dataclass(record) and not isinstance(record, type):
        return asdict(record).get(name, default)
    return getattr(record, name, default)


def _parse_date(value: Any) -> date | None:
    """Parse gia tri ngay thanh `datetime.date`, tra ve None neu khong doc duoc."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    matched = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if matched:
        try:
            return date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
        except ValueError:
            return None
    # Fallback: chi co nam (vi du "2026").
    matched = re.match(r"^(\d{4})$", text)
    if matched:
        return date(int(matched.group(1)), 1, 1)
    return None


def _normalize_list(value: Any) -> list[str]:
    """Chuan hoa list[str]: bo khoang trang thua, bo rong, khu trung lap (giu thu tu)."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple, set)) else [value]
    normalized: list[str] = []
    for item in items:
        text = normalize_whitespace(str(item))
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _build_text_for_embedding(row: dict[str, Any]) -> str:
    """Ghep ngu canh day du dua vao mo hinh nhung vector.

    Dinh dang bat buoc:
        Title: <Tieu de>
        Authors: <Danh sach tac gia>
        Published: <Ngay xuat ban>
        Categories: <Chuyen nganh>
        Summary: <Tom tat>
    """
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def build_text_for_embedding(row: dict[str, Any]) -> str:
    """Ban cong khai cua `_build_text_for_embedding` cho cac module khac tai su dung."""
    return _build_text_for_embedding(row)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Luong xu ly:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper: authors_joined, categories_joined, summary_chars, text_for_embedding.
    5. Drop duplicates theo `paper_id` va filter row xau.
    6. Sort dataframe va return.
    """
    run_date_value = run_date.date() if isinstance(run_date, datetime) else run_date

    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = normalize_whitespace(str(_field(record, "paper_id", "") or ""))
        title = normalize_whitespace(str(_field(record, "title", "") or ""))
        summary = normalize_whitespace(str(_field(record, "summary", "") or ""))

        # Row xau: thieu khoa dinh danh / tieu de, hoac summary qua ngan de AI doc hieu.
        if not paper_id or not title:
            continue
        if len(summary) < MIN_SUMMARY_CHARS:
            continue

        published_date = _parse_date(_field(record, "published"))
        if published_date is None:
            # Khong co ngay xuat ban thi khong the theo doi do tuoi (freshness SLA).
            continue
        updated_date = _parse_date(_field(record, "updated")) or published_date

        authors = _normalize_list(_field(record, "authors"))
        categories = _normalize_list(_field(record, "categories"))

        published = published_date.isoformat()
        abs_url = normalize_whitespace(str(_field(record, "abs_url", "") or ""))

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(
                    str(_field(record, "primary_category", "") or "")
                )
                or (categories[0] if categories else CATEGORIES_FALLBACK),
                "published": published,
                "updated": updated_date.isoformat(),
                "abs_url": abs_url or f"https://doi.org/{paper_id}",
                "pdf_url": normalize_whitespace(str(_field(record, "pdf_url", "") or ""))
                or abs_url
                or f"https://doi.org/{paper_id}",
                "comment": normalize_whitespace(str(_field(record, "comment", "") or "")),
                "authors_joined": compact_join(authors) or AUTHORS_FALLBACK,
                "categories_joined": compact_join(categories) or CATEGORIES_FALLBACK,
                "summary_chars": len(summary),
                "age_days": (run_date_value - published_date).days,
            }
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return dataframe

    # Khu trung lap ban ghi theo khoa duy nhat `paper_id` (giu ban ghi dau tien).
    dataframe = dataframe.drop_duplicates(subset="paper_id", keep="first")

    dataframe["text_for_embedding"] = dataframe.apply(
        lambda row: _build_text_for_embedding(row.to_dict()), axis=1
    )

    # Sap xep bai moi nhat len dau, `paper_id` lam khoa phu de ket qua on dinh.
    dataframe = dataframe.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)

    return dataframe
