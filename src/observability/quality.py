from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    mapping = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return mapping.get(report_name, settings.paths.quality_dir / f"{report_name}_quality_report.json")


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"{report_name}_suite")
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30, max_value=None)
    )

    results = batch.validate(suite)
    report = {
        "success": bool(results.success),
        "evaluated_expectations": len(results.results),
        "passed_expectations": sum(1 for r in results.results if r.success),
        "failed_expectations": sum(1 for r in results.results if not r.success),
    }
    write_json(_quality_report_path(settings, report_name), report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    if df.empty:
        report = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "is_fresh": False,
            "freshness_threshold_days": settings.freshness_threshold_days,
        }
        write_json(report_path, report)
        return report

    df_copy = df.copy()
    published = pd.to_datetime(df_copy["published"], utc=True, errors="coerce")
    age_days = pd.to_numeric(df_copy["age_days"], errors="coerce")
    stale_count = int((age_days > settings.freshness_threshold_days).sum())
    stale_ratio = stale_count / len(df_copy) if len(df_copy) else 0.0
    report = {
        "latest_published": published.max().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().isoformat() if published.notna().any() else None,
        "stale_rows": stale_count,
        "total_rows": int(len(df_copy)),
        "stale_ratio": round(float(stale_ratio), 4),
        "is_fresh": bool(stale_ratio <= 0.25),
        "freshness_threshold_days": settings.freshness_threshold_days,
    }
    write_json(report_path, report)
    return report
