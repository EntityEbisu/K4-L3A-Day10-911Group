from __future__ import annotations

from datetime import datetime
import html
import re

import pandas as pd

from ingestion.crossref import PaperRecord


def _calculate_age_days(published_str: str, run_date: datetime) -> int:
    """Tính toán age_days = (run_date - published).days một cách an toàn."""
    try:
        pub_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if run_date.tzinfo is not None and pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=run_date.tzinfo)
        elif run_date.tzinfo is None and pub_dt.tzinfo is not None:
            pub_dt = pub_dt.replace(tzinfo=None)
        return (run_date - pub_dt).days
    except Exception:
        pub_ts = pd.to_datetime(published_str, utc=True)
        run_ts = pd.Timestamp(run_date)
        if run_ts.tzinfo is None:
            run_ts = run_ts.tz_localize("UTC")
        else:
            run_ts = run_ts.tz_convert("UTC")
        return int((run_ts - pub_ts).days)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Làm sạch raw records thành dataframe sẵn sàng để embed và đánh chỉ mục vector.

    Các bước thực hiện:
    1. Chuẩn hóa title, summary, authors, categories.
    2. Parse ngày published/updated.
    3. Tính toán độ tươi của dữ liệu: age_days = (run_date - published).days.
    4. Tạo các cột hỗ trợ:
       - authors_joined: Ghép danh sách tác giả cách nhau bởi dấu phẩy
       - categories_joined: Ghép danh sách lĩnh vực cách nhau bởi dấu phẩy
       - summary_chars: Độ dài ký tự tóm tắt
       - text_for_embedding: Khối văn bản ngữ cảnh 5 phần cho Vector DB
    5. Khử trùng lặp bản ghi theo khóa duy nhất paper_id và lọc các dòng lỗi/rỗng.
    6. Sắp xếp dataframe và reset index.
    """
    rows: list[dict] = []

    for r in records:
        paper_id = str(r.paper_id or "").strip()
        if not paper_id:
            continue

        raw_title = str(r.title or "")
        title = " ".join(html.unescape(raw_title).split()).strip()

        raw_summary = str(r.summary or "")
        clean_summary = re.sub(r"<[^>]+>", " ", raw_summary)
        summary = " ".join(html.unescape(clean_summary).split()).strip()

        authors = [str(a).strip() for a in r.authors if str(a).strip()] if isinstance(r.authors, list) else []
        authors_joined = ", ".join(authors)

        categories = [str(c).strip() for c in r.categories if str(c).strip()] if isinstance(r.categories, list) else []
        categories_joined = ", ".join(categories)

        primary_category = str(r.primary_category or "").strip() or (categories[0] if categories else "")
        published = str(r.published or "").strip()
        updated = str(r.updated or "").strip() or published
        abs_url = str(r.abs_url or "").strip()
        pdf_url = str(r.pdf_url or "").strip() or abs_url
        comment = str(r.comment or "").strip()

        summary_chars = len(summary)
        age_days = _calculate_age_days(published, run_date)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "comment": comment,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Lọc bỏ các dòng thiếu thông tin thiết yếu
    df = df.dropna(subset=["paper_id", "title", "summary"])
    df = df[(df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "")]

    # Khử trùng lặp theo paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Sắp xếp theo ngày xuất bản mới nhất lên đầu
    df = df.sort_values(by=["published"], ascending=False).reset_index(drop=True)

    return df
