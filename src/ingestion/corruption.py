from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import build_text_for_embedding


# Cau hinh 6 kich ban tien loi du lieu.
DROP_LATEST_RATIO = 0.20   # bo roi 20% ban ghi moi nhat
BLANK_SUMMARY_ROWS = 3     # so dong bi xoa trang tom tat
NOISE_ROWS = 3             # so dong bi chen ky tu rac
TRUNCATE_TITLE_ROWS = 3    # so dong bi cat ngan tieu de
TRUNCATED_TITLE_CHARS = 6  # do dai tieu de sau khi cat (thoa "< 8" va "< 10")
STALE_DATE_ROWS = 6        # so dong bi lui ngay xuat ban (du de ti le qua han > 25%)
STALE_YEARS_BACK = 5       # lui ve 5 nam truoc
MIN_DUPLICATE_ROWS = 3     # so dong nhan ban toi thieu

NOISE_TOKEN = "xzqv#@!!~##garbage-noise"
KEPT_TIMESTAMP_COLUMNS = (
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
)


def _rebuild_embedding_text(df: pd.DataFrame) -> pd.DataFrame:
    """Dung lai `text_for_embedding` va `summary_chars` sau khi da lam bien dang."""
    df["text_for_embedding"] = df.apply(
        lambda row: build_text_for_embedding(row.to_dict()), axis=1
    )
    df["summary_chars"] = df["summary"].astype(str).str.len()
    return df


def _stale_date(value: Any, run_date: date, years_back: int) -> str:
    """Lui ngay xuất ban ve `years_back` nam truoc, gioi han khong vuot qua run_date."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)
    try:
        shifted = parsed.date().replace(year=parsed.date().year - years_back)
    except ValueError:
        # 29/02 khong ton tai o nam dich -> lui ve 28/02.
        shifted = parsed.date().replace(year=parsed.date().year - years_back, day=28)
    if shifted > run_date:
        return str(run_date)
    return shifted.isoformat()


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Mo phong 6 dang data corruption tren dataframe sach va ghi log chi tiet.

    Cac kich ban:
    1. Drop latest records  - bo roi 20% ban ghi moi nhat.
    2. Blank summary        - xoa trang tom tat o mot so dong.
    3. Inject noise         - chen chuoi ky tu rac vao `text_for_embedding`.
    4. Truncate title       - cat ngan tieu de xuong con 6 ky tu.
    5. Stale date           - lui ngay xuat ban ve 5 nam truoc.
    6. Duplicate rows       - nhan ban mot so dong de tao ban ghi trung lap.

    Tra ve dataframe da bi lam bien dang (chu y: so dong co the tang do nhan ban).
    """
    if df is None or df.empty:
        raise ValueError("Dataframe dau vao rong, khong the tien loi du lieu.")

    run_date = datetime.now(UTC).date()
    working = df.copy().reset_index(drop=True)
    log: list[dict[str, Any]] = []

    # --- 1. Drop latest records -------------------------------------------------
    ordered = working.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    )
    drop_count = int(round(len(working) * DROP_LATEST_RATIO))
    drop_count = min(drop_count, max(0, len(working) - 1))
    dropped_ids = ordered["paper_id"].astype(str).head(drop_count).tolist()
    working = working[~working["paper_id"].astype(str).isin(dropped_ids)].reset_index(drop=True)
    log.append(
        {
            "scenario": "drop_latest_records",
            "description": f"Bo roi {drop_count} ban ghi moi nhat ({DROP_LATEST_RATIO:.0%} du lieu tuoi).",
            "affected_rows": drop_count,
            "affected_paper_ids": dropped_ids,
        }
    )

    # --- 2. Blank summary ------------------------------------------------------
    blank_ids = working["paper_id"].astype(str).head(BLANK_SUMMARY_ROWS).tolist()
    blank_mask = working["paper_id"].astype(str).isin(blank_ids)
    working.loc[blank_mask, "summary"] = ""
    log.append(
        {
            "scenario": "blank_summary",
            "description": "Xoa trang tom tat (mo phong thieu thong tin).",
            "affected_rows": int(blank_mask.sum()),
            "affected_paper_ids": blank_ids,
        }
    )

    # --- 3. Inject text noise --------------------------------------------------
    noise_ids = working["paper_id"].astype(str).iloc[
        BLANK_SUMMARY_ROWS : BLANK_SUMMARY_ROWS + NOISE_ROWS
    ].tolist()
    noise_mask = working["paper_id"].astype(str).isin(noise_ids)
    working.loc[noise_mask, "summary"] = (
        working.loc[noise_mask, "summary"].astype(str) + " " + NOISE_TOKEN
    )
    log.append(
        {
            "scenario": "inject_text_noise",
            "description": f"Chen chuoi ky tu rac '{NOISE_TOKEN}' vao tom tat/text embedding.",
            "affected_rows": int(noise_mask.sum()),
            "affected_paper_ids": noise_ids,
        }
    )

    # --- 4. Truncate title -----------------------------------------------------
    title_start = BLANK_SUMMARY_ROWS + NOISE_ROWS
    truncate_ids = working["paper_id"].astype(str).iloc[
        title_start : title_start + TRUNCATE_TITLE_ROWS
    ].tolist()
    truncate_mask = working["paper_id"].astype(str).isin(truncate_ids)
    working.loc[truncate_mask, "title"] = (
        working.loc[truncate_mask, "title"].astype(str).str.slice(0, TRUNCATED_TITLE_CHARS)
    )
    log.append(
        {
            "scenario": "truncate_title",
            "description": f"Cat ngan tieu de xuong con {TRUNCATED_TITLE_CHARS} ky tu.",
            "affected_rows": int(truncate_mask.sum()),
            "affected_paper_ids": truncate_ids,
        }
    )

    # --- 5. Stale date --------------------------------------------------------
    stale_start = title_start + TRUNCATE_TITLE_ROWS
    stale_ids = working["paper_id"].astype(str).iloc[
        stale_start : stale_start + STALE_DATE_ROWS
    ].tolist()
    stale_mask = working["paper_id"].astype(str).isin(stale_ids)
    working.loc[stale_mask, "published"] = working.loc[stale_mask, "published"].apply(
        lambda value: _stale_date(value, run_date, STALE_YEARS_BACK)
    )
    working.loc[stale_mask, "updated"] = working.loc[stale_mask, "published"]
    # age_days phai duoc tinh lai de freshness SLA phat hien duoc du lieu moc.
    working["age_days"] = (
        run_date - pd.to_datetime(working["published"], errors="coerce").dt.date
    ).apply(lambda delta: delta.days if pd.notna(delta) else 0)
    log.append(
        {
            "scenario": "stale_date",
            "description": f"Lui ngay xuat ban ve {STALE_YEARS_BACK} nam truoc (du lieu moc).",
            "affected_rows": int(stale_mask.sum()),
            "affected_paper_ids": stale_ids,
            "new_published": working.loc[stale_mask, "published"].tolist(),
            # Cac ban ghi bi nhan ban o buoc 6 se mang theo ca tinh moc, nen tong so
            # dong qua han sau cung co the lon hon so dong bi sua truc tiep o day.
            "baseline_stale_rows": int((df["age_days"] > 180).sum()),
            "total_stale_after_duplicates": None,  # duoc dien sau buoc 6
        }
    )

    # --- 6. Duplicate rows ----------------------------------------------------
    # So dong nhan ban duoc chon de TONG so dong quay ve bang ban goc.
    # Day chinh la kich ban "Silent Failure" dien hinh: so luong ban ghi khong doi
    # nen monitoring tho (row count) khong he bao dong, trong khi noi dung da hong.
    duplicate_count = max(MIN_DUPLICATE_ROWS, len(df) - len(working))
    duplicate_count = min(duplicate_count, len(working))
    # Lay tu CUOI (cac bai cu nhat) de khong giam vao vung da bi blank/noise/truncate
    # o dau dataframe, giu 6 kich ban tac dong len cac nhom dong tach roi nhau.
    duplicate_ids = working["paper_id"].astype(str).tail(duplicate_count).tolist()
    duplicates = working[working["paper_id"].astype(str).isin(duplicate_ids)].copy()
    working = pd.concat([working, duplicates], ignore_index=True)
    log.append(
        {
            "scenario": "duplicate_rows",
            "description": (
                f"Nhan ban {len(duplicates)} ban ghi de tao du lieu trung lap "
                f"(bu lai phan da bi bo, giu row count khong doi)."
            ),
            "affected_rows": int(len(duplicates)),
            "affected_paper_ids": duplicate_ids,
        }
    )

    # Dung lai text_for_embedding tren du lieu da bi bien dang.
    working = _rebuild_embedding_text(working)

    # Ghi nhan tong so dong qua han sau khi da nhan ban (minh bach cho bao cao).
    for entry in log:
        if entry["scenario"] == "stale_date":
            entry["total_stale_after_duplicates"] = int((working["age_days"] > 180).sum())
            break

    # Sap xep lai cho on dinh (ban ghi bi nhan ban nam canh nhau).
    working = working.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)

    summary_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_date": run_date.isoformat(),
        "input_rows": int(len(df)),
        "output_rows": int(len(working)),
        "scenarios_total": len(log),
        "scenarios": log,
        # Thong tin tong hop giup doi chieu nhanh voi quality gate.
        "summary": {
            "unique_paper_ids_input": int(df["paper_id"].nunique()),
            "unique_paper_ids_output": int(working["paper_id"].nunique()),
            "duplicated_rows": int(working["paper_id"].duplicated().sum()),
            "blank_summary_rows": int((working["summary"].astype(str).str.len() == 0).sum()),
            "noisy_rows": int(working["summary"].astype(str).str.contains(NOISE_TOKEN, regex=False).sum()),
            "truncated_title_rows": int((working["title"].astype(str).str.len() < 8).sum()),
            "stale_rows": int((working["age_days"] > 180).sum()),
        },
    }
    write_json(Path(output_log_path), summary_payload)

    return working
