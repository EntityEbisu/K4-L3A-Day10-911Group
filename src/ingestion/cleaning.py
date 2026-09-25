from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, first_sentence, normalize_whitespace
from ingestion.crossref import PaperRecord, strip_jats


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    rows = []
    for record in records:
        title = strip_jats(record.title)
        summary = strip_jats(record.summary)
        paper_id = normalize_whitespace(record.paper_id)
        if not paper_id or not title:
            continue
        if not record.published:
            continue
        published_dt = pd.to_datetime(record.published, utc=True).to_pydatetime()
        if run_date.tzinfo is None:
            published_naive = published_dt.replace(tzinfo=None)
            age_days = (run_date - published_naive).days
        else:
            age_days = (run_date - published_dt).days

        authors_joined = compact_join(record.authors)
        categories_joined = compact_join(record.categories)
        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {record.published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )
        if not text_for_embedding.strip():
            continue
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": record.authors,
                "categories": record.categories,
                "primary_category": record.primary_category,
                "published": record.published,
                "published_dt": published_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated": record.updated,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": int(age_days),
                "text_for_embedding": text_for_embedding,
                "source": "crossref",
                "summary_first_sentence": first_sentence(summary),
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values(["published_dt", "paper_id"], ascending=[False, True])
    df = df.drop_duplicates(subset=["paper_id"], keep="first").reset_index(drop=True)
    return df
