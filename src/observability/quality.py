from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings

logger = logging.getLogger(__name__)


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path | None = None
) -> dict[str, Any]:
    """Tổng hợp báo cáo Freshness SLA theo dõi độ tươi mới của dữ liệu.

    - Ngưỡng quá hạn mặc định: age_days > 180 ngày.
    - Cảnh báo vi phạm SLA (is_fresh = False) nếu tỷ lệ bài quá hạn vượt quá 25%.
    """
    target_path = report_path or settings.paths.freshness_report
    total_rows = len(df)
    stale_rows = (
        int((df["age_days"] > settings.freshness_threshold_days).sum())
        if "age_days" in df.columns
        else 0
    )
    stale_ratio = (stale_rows / total_rows) if total_rows > 0 else 0.0
    is_fresh = stale_ratio <= 0.25

    latest_published = (
        str(df["published"].max()) if ("published" in df.columns and not df.empty) else ""
    )
    oldest_published = (
        str(df["published"].min()) if ("published" in df.columns and not df.empty) else ""
    )

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "is_fresh": is_fresh,
    }

    if target_path:
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return payload


def run_data_quality_checks(
    df: pd.DataFrame, settings: Settings, report_name: str
) -> dict[str, Any]:
    """Thực thi chốt kiểm dịch chất lượng dữ liệu với Great Expectations 1.x.

    Thiết lập 4 kỳ vọng (Expectations) cốt lõi:
    1. ExpectTableRowCountToBeBetween: Số lượng bản ghi hợp lệ (5 - 5000 dòng).
    2. ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding không được null.
    3. ExpectColumnValuesToBeUnique: paper_id là khóa duy nhất.
    4. ExpectColumnValueLengthsToBeBetween: Trường summary có độ dài >= 30 ký tự.
    5. Kiểm tra Freshness SLA: Tỷ lệ bản ghi có age_days > 180 <= 25%.
    """
    # 1. Khởi tạo Great Expectations Ephemeral Context (chạy trên RAM)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # 2. Xây dựng Expectation Suite
    suite_name = f"papers_{report_name}_suite"
    suite = gx.ExpectationSuite(name=suite_name)

    # Expectation 1: Row count
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))

    # Expectation 2: Non-null values for vital columns
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))

    # Expectation 3: Uniqueness of paper_id
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))

    # Expectation 4: Minimum length of summary
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    context.suites.add(suite)

    # 3. Thực thi validation
    validation_results = batch.validate(suite)
    report_dict = validation_results.describe_dict()

    # 4. Kiểm tra độ tươi (Freshness Check)
    freshness_info = build_freshness_report(
        df,
        settings,
        report_path=settings.paths.freshness_report if report_name in {"baseline", "test"} else None,
    )
    report_dict["freshness"] = freshness_info

    # 5. Lưu báo cáo kiểm định vào data/quality/
    if report_name == "baseline":
        report_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        report_path = settings.paths.corrupted_quality_report
    else:
        report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return report_dict
