from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from core.utils import compact_join, write_json


NOISE_TOKEN = "@@@###$$$"


def _rebuild_derived(df: pd.DataFrame, run_date: pd.Timestamp | None = None) -> pd.DataFrame:
    df = df.copy()
    df["authors_joined"] = df["authors"].apply(lambda x: compact_join(x) if isinstance(x, list) else str(x or ""))
    df["categories_joined"] = df["categories"].apply(lambda x: compact_join(x) if isinstance(x, list) else str(x or ""))
    published = pd.to_datetime(df["published"], utc=True, errors="coerce")
    if run_date is None:
        run_date = pd.Timestamp.now(tz="UTC")
    df["age_days"] = (run_date - published).dt.days.fillna(df.get("age_days", 0)).astype(int)
    df["text_for_embedding"] = (
        "Title: " + df["title"].fillna("").astype(str)
        + "\nAuthors: " + df["authors_joined"].fillna("").astype(str)
        + "\nPublished: " + df["published"].fillna("").astype(str)
        + "\nCategories: " + df["categories_joined"].fillna("").astype(str)
        + "\nSummary: " + df["summary"].fillna("").astype(str)
    )
    return df


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    log: dict = {}

    sorted_df = df.sort_values("published", ascending=False)
    drop_count = max(1, int(round(len(df) * 0.20)))
    dropped_ids = sorted_df.head(drop_count)["paper_id"].tolist()
    df = df[~df["paper_id"].isin(dropped_ids)].copy().reset_index(drop=True)
    log["drop_latest_records"] = {"type": "drop_latest_records", "count": drop_count, "dropped_paper_ids": dropped_ids}

    blank_indices = list(range(min(3, len(df))))
    for idx in blank_indices:
        df.loc[idx, "summary"] = ""
    log["blank_summary"] = {"type": "blank_summary", "count": len(blank_indices), "affected_indices": blank_indices}

    noise_indices = [i for i in range(len(df)) if i not in blank_indices][:3]
    for idx in noise_indices:
        current = str(df.loc[idx, "summary"] or "")
        df.loc[idx, "summary"] = f"{current} {NOISE_TOKEN}".strip()
    log["inject_noise"] = {
        "type": "inject_noise",
        "count": len(noise_indices),
        "noise_strings": [NOISE_TOKEN],
        "affected_indices": noise_indices,
    }

    used = set(blank_indices + noise_indices)
    truncate_indices = [i for i in range(len(df)) if i not in used][:3]
    for idx in truncate_indices:
        df.loc[idx, "title"] = str(df.loc[idx, "title"])[:5]
    log["truncate_title"] = {
        "type": "truncate_title",
        "count": len(truncate_indices),
        "new_max_length": 5,
        "affected_indices": truncate_indices,
    }

    used.update(truncate_indices)
    stale_indices = [i for i in range(len(df)) if i not in used][:5]
    for idx in stale_indices:
        old_date = pd.to_datetime(df.loc[idx, "published"], utc=True, errors="coerce")
        if pd.isna(old_date):
            continue
        new_date = old_date - timedelta(days=365)
        df.loc[idx, "published"] = new_date.strftime("%Y-%m-%d")
    log["stale_date"] = {
        "type": "stale_date",
        "count": len(stale_indices),
        "days_moved_back": 365,
        "affected_indices": stale_indices,
    }

    dup_rows = df.head(min(2, len(df))).copy()
    df = pd.concat([df, dup_rows], ignore_index=True)
    log["duplicate_rows"] = {
        "type": "duplicate_rows",
        "count": len(dup_rows),
        "duplicated_paper_ids": dup_rows["paper_id"].tolist(),
    }

    df = _rebuild_derived(df)
    write_json(Path(output_log_path), log)
    return df
