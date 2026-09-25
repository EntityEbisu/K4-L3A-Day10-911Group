from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


# Nguong nghiep vu cho tram kiem soat chat luong du lieu.
MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
STALE_AGE_DAYS = 180
STALE_RATIO_LIMIT = 0.25

# Ten cac doi tuong GX dung xuyen suot module.
DATASOURCE_NAME = "papers_source"
DATA_ASSET_NAME = "papers_asset"
BATCH_DEFINITION_NAME = "papers_batch"
SUITE_NAME = "papers_quality_suite"
VALIDATION_DEFINITION_NAME = "papers_validation"
CHECKPOINT_NAME = "papers_checkpoint"


def _build_suite(context: Any) -> Any:
    """Tao ExpectationSuite voi 4 hang rao kiểm định bat buoc (GX 1.x)."""
    suite = context.suites.add(gx.ExpectationSuite(name=SUITE_NAME))

    # 1) So luong ban ghi nam trong nguong hop le.
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=MIN_ROWS,
            max_value=MAX_ROWS,
            meta={"rule": "row_count"},
        )
    )
    # 2) Cac cot quan trong khong duoc de trong.
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="paper_id",
            meta={"rule": "paper_id_not_null"},
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="title",
            meta={"rule": "title_not_null"},
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="text_for_embedding",
            meta={"rule": "text_for_embedding_not_null"},
        )
    )
    # 3) `paper_id` la khoa duy nhat, khong chap nhan ban ghi trung lap.
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(
            column="paper_id",
            meta={"rule": "paper_id_unique"},
        )
    )
    # 4) `summary` phai du dai de AI doc hieu.
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=MIN_SUMMARY_CHARS,
            meta={"rule": "summary_min_length"},
        )
    )
    return suite


def _run_batch_validation(df: pd.DataFrame) -> Any:
    """Chay GX 1.x ephemeral context tren dataframe va tra ve CheckpointResult."""
    # mode="ephemeral": chay tam tren RAM, khong sinh file rac.
    context = gx.get_context(mode="ephemeral")

    data_source = context.data_sources.add_pandas(name=DATASOURCE_NAME)
    data_asset = data_source.add_dataframe_asset(name=DATA_ASSET_NAME)
    batch_definition = data_asset.add_batch_definition_whole_dataframe(BATCH_DEFINITION_NAME)
    batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = _build_suite(context)
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            data=batch_definition,
            suite=suite,
            name=VALIDATION_DEFINITION_NAME,
        )
    )
    checkpoint = context.checkpoints.add(
        gx.Checkpoint(name=CHECKPOINT_NAME, validation_definitions=[validation_definition])
    )
    return checkpoint.run(batch_parameters={"dataframe": df})


def _json_safe(value: Any) -> Any:
    """Doi NaN/NaT sang None de report la JSON hop le."""
    if isinstance(value, float) and value != value:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _summarize_expectation(result: Any) -> dict[str, Any]:
    """Chuyen 1 ExpectationValidationResult thanh dict de ghi report."""
    config = result.expectation_config
    payload: dict[str, Any] = {
        "expectation": config.type,
        "column": config.kwargs.get("column"),
        "rule": (config.meta or {}).get("rule"),
        "success": bool(result.success),
    }
    # Voi cac expectation bi fail, giu lai so lieu de biet hong o dau.
    if not result.success and isinstance(result.result, dict):
        for key in (
            "element_count",
            "unexpected_count",
            "unexpected_percent",
            "missing_count",
            "observed_value",
        ):
            if key in result.result:
                payload[key] = _json_safe(result.result[key])
        unexpected = result.result.get("partial_unexpected_list")
        if unexpected is not None:
            payload["sample_unexpected"] = [_json_safe(item) for item in list(unexpected)[:5]]
    return payload


def _collect_failures(checkpoint_result: Any) -> list[dict[str, Any]]:
    """Boc tach ket qua tung expectation tu CheckpointResult."""
    summaries: list[dict[str, Any]] = []
    for validation_result in checkpoint_result.run_results.values():
        for result in validation_result.results:
            summaries.append(_summarize_expectation(result))
    return summaries


def _quarantine_failures(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in summaries if not item["success"]]


def _freshness_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """Tinh toan do tuoi du lieu: ti le bai qua han va co canh bao hay khong."""
    if df.empty or "age_days" not in df.columns:
        return {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": int(len(df)),
            "stale_ratio": 0.0,
            "is_fresh": True,
        }

    age_days = pd.to_numeric(df["age_days"], errors="coerce").fillna(0)
    stale_rows = int((age_days > STALE_AGE_DAYS).sum())
    total_rows = int(len(df))
    stale_ratio = stale_rows / total_rows if total_rows else 0.0

    published = df["published"].dropna() if "published" in df.columns else pd.Series(dtype=str)
    return {
        "latest_published": str(published.max()) if not published.empty else None,
        "oldest_published": str(published.min()) if not published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        # Du lieu bi coi la "moc" khi ti le bai qua han vuot qua 25%.
        "is_fresh": stale_ratio <= STALE_RATIO_LIMIT,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks (Great Expectations 1.x) va ghi report.

    Tra ve payload tong hop gom: success, so luong expectation, danh sach loi,
    freshness metrics, va ket qua validate.
    """
    checkpoint_result = _run_batch_validation(df)
    expectation_results = _collect_failures(checkpoint_result)
    failures = _quarantine_failures(expectation_results)
    freshness = _freshness_metrics(df)

    # Quality gate chi "pass" khi ca 4 hang rao dat VA du lieu con tuoi.
    success = bool(checkpoint_result.success) and bool(freshness["is_fresh"])

    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "success": success,
        "gx_success": bool(checkpoint_result.success),
        "total_rows": int(len(df)),
        "expectations_total": len(expectation_results),
        "expectations_passed": sum(1 for item in expectation_results if item["success"]),
        "expectations_failed": len(failures),
        "failures": failures,
        "expectation_results": expectation_results,
        "thresholds": {
            "min_rows": MIN_ROWS,
            "max_rows": MAX_ROWS,
            "min_summary_chars": MIN_SUMMARY_CHARS,
            "stale_age_days": STALE_AGE_DAYS,
            "stale_ratio_limit": STALE_RATIO_LIMIT,
        },
        "freshness": freshness,
    }

    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    """Tong hop freshness report va ghi JSON vao report_path."""
    payload = _freshness_metrics(df)
    payload.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "stale_age_days": STALE_AGE_DAYS,
            "stale_ratio_limit": STALE_RATIO_LIMIT,
            # Cac key nay phuc vu bao cao va kiem tra hoi quy.
            "total_stale_rows": payload["stale_rows"],
            "total_records": payload["total_rows"],
        }
    )
    write_json(Path(report_path), payload)
    return payload
