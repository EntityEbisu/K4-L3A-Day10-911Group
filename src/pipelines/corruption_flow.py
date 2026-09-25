from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


TOTAL_STEPS = 9


def _step(number: int, message: str) -> None:
    print(f"[{number}/{TOTAL_STEPS}] {message}", flush=True)


def _save_clean_like(df: pd.DataFrame, csv_path, json_path) -> None:
    """Luu dataframe (da lam sach / bi tien loi / phuc hoi) ra ca CSV va JSON."""
    write_csv(df, csv_path)
    df.to_json(json_path, orient="records", indent=2, force_ascii=True)


def _evaluate(
    settings: Settings,
    df: pd.DataFrame,
    embeddings_path,
    metrics_path,
    answers_path,
    label: str,
) -> dict[str, Any]:
    """Build index cho mot trang thai du lieu roi danh gia tren cung bo test set."""
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        metrics_path,
        answers_path,
    )
    print(
        f"      -> {label}: {len(index.documents)} docs | "
        f"hit_rate={bundle.summary['retrieval_hit_rate']:.4f} "
        f"token_f1={bundle.summary['mean_token_f1']:.4f} "
        f"judge_acc={bundle.summary['judge_accuracy']:.4f}"
    )
    return bundle.summary


def _repair_from_raw(settings: Settings, run_date: datetime) -> pd.DataFrame:
    """Idempotent Repair: dung lai du lieu sach tu raw snapshot dang tin cay.

    Chay lai nhieu lan tren cung raw snapshot luon cho ket qua giong het nhau,
    nen day la co che phuc hoi an toan (idempotent), khong phu thuoc du lieu da hong.
    """
    records = load_raw_records(settings.paths.raw_records_json)
    return build_clean_dataframe(records, run_date)


def _print_comparison(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> None:
    """In bang so sanh 3 trang thai ra console (tin hieu nghiem thu CP5)."""
    keys = (
        ("samples", "So cau hoi"),
        ("retrieval_hit_rate", "Retrieval Hit Rate"),
        ("mean_token_f1", "Mean Token F1"),
        ("judge_accuracy", "LLM Judge Accuracy"),
        ("mean_judge_score", "Mean Judge Score"),
    )
    print()
    print("=" * 74)
    print(f"{'Chi so':<24}{'Baseline':>16}{'Corrupted':>16}{'Repaired':>16}")
    print("-" * 74)
    for key, label in keys:
        vals = []
        for metrics in (baseline, corrupted, repaired):
            value = metrics.get(key)
            vals.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        print(f"{label:<24}{vals[0]:>16}{vals[1]:>16}{vals[2]:>16}")
    print("=" * 74)


def main() -> None:
    """Chay corruption -> evaluate -> repair -> compare flow."""
    settings = load_settings()
    run_date = datetime.now(UTC)

    # 1) Doc baseline metrics va du lieu sach lam diem xuat phat.
    _step(1, "Doc baseline metrics va du lieu sach...")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = pd.read_json(settings.paths.clean_json)
    print(f"      -> baseline {len(clean_df)} docs | hit_rate={baseline_metrics['retrieval_hit_rate']:.4f}")

    # 2) Tien loi du lieu (6 kich ban).
    _step(2, "Tien loi du lieu (6 kich ban)...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    log = read_json(settings.paths.corruption_log)
    print(f"      -> {len(corrupted_df)} dong | {log['scenarios_total']} kich ban -> corruption_log.json")

    # 3) Luu artifact cua trang thai corrupted.
    _step(3, "Luu artifact corrupted...")
    _save_clean_like(
        corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json
    )

    # 4) Quality gate + freshness tren du lieu bi tien loi (ky vong: FAIL).
    _step(4, "Quality gate tren du lieu corrupted (ky vong KHONG DAT)...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(
        f"      -> quality success={corrupted_quality['success']} "
        f"({corrupted_quality['expectations_failed']} loi) | "
        f"is_fresh={corrupted_freshness['is_fresh']} "
        f"(stale {corrupted_freshness['stale_rows']}/{corrupted_freshness['total_rows']})"
    )

    # 5) Danh gia RAG tren du lieu corrupted (do suy giam - Silent Failure).
    _step(5, "Danh gia RAG tren du lieu corrupted...")
    corrupted_metrics = _evaluate(
        settings,
        corrupted_df,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
        "corrupted",
    )

    # 6) Idempotent Repair tu raw snapshot.
    _step(6, "Idempotent Repair tu raw snapshot...")
    repaired_df = _repair_from_raw(settings, run_date)
    _save_clean_like(
        repaired_df, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json
    )
    print(f"      -> {len(repaired_df)} dong sach duoc phuc hoi tu raw records")

    # 7) Quality gate tren du lieu da phuc hoi (ky vong: PASS lai).
    _step(7, "Quality gate tren du lieu repaired (ky vong DAT)...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, settings.paths.quality_dir / "repaired_freshness_report.json"
    )
    print(
        f"      -> quality success={repaired_quality['success']} "
        f"| is_fresh={repaired_freshness['is_fresh']}"
    )

    # 8) Danh gia RAG tren du lieu phuc hoi.
    _step(8, "Danh gia RAG tren du lieu repaired...")
    repaired_metrics = _evaluate(
        settings,
        repaired_df,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
        "repaired",
    )

    # 9) Bang so sanh 3 trang thai + bao cao markdown.
    _step(9, "Tao bang so sanh 3 trang thai va bao cao...")
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics)
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"      -> {settings.paths.comparison_report}")
    print(f"\nHoan tat corruption flow: baseline -> corrupted -> repaired.")


if __name__ == "__main__":
    main()
