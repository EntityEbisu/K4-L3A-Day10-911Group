from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


TOTAL_STEPS = 8


def _step(number: int, message: str) -> None:
    print(f"[{number}/{TOTAL_STEPS}] {message}", flush=True)


def _load_records(settings: Settings) -> tuple[list[PaperRecord], str]:
    """Lay raw records: doc snapshot da luu, hoac goi API neu chua co.

    Tra ve (records, cach lay du lieu) de ghi vao bao cao lineage.
    """
    snapshot_path = settings.paths.raw_records_json
    if snapshot_path.exists() and not settings.refresh_source:
        return load_raw_records(snapshot_path), "raw_records_json"
    records = fetch_source_records(settings)
    return records, "crossref_api_or_offline_snapshot"


def _source_summary(
    settings: Settings,
    records: list[PaperRecord],
    clean_df: pd.DataFrame,
    lineage: str,
) -> dict[str, Any]:
    """Tong hop thong tin nguon goc du lieu (data lineage) cho bao cao."""
    published = pd.to_datetime(clean_df.get("published"), errors="coerce").dropna()
    clean_rows = int(len(clean_df))
    return {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "sys_source": settings.source_api,
        "max_results": settings.max_results,
        "lineage_mode": lineage,
        "raw_response_path": str(settings.paths.raw_api_response),
        "raw_records_path": str(settings.paths.raw_records_json),
        "raw_record_count": len(records),
        "clean_rows": clean_rows,
        "dropped_rows": len(records) - clean_rows,
        "collection_name": settings.baseline_collection_name,
        "embedding_model": settings.embedding_model,
        "latest_published": published.max().date().isoformat() if not published.empty else None,
        "oldest_published": published.min().date().isoformat() if not published.empty else None,
    }


def main() -> None:
    """Chay baseline pipeline end-to-end va sinh day du artifact cho Phase 1."""
    settings = load_settings()
    run_date = datetime.now(UTC)

    # 1) Lay raw records (kem co che cuu ho offline trong fetch_source_records).
    _step(1, "Lay raw records tu Crossref (hoac snapshot offline)...")
    records, lineage = _load_records(settings)
    print(f"      -> {len(records)} ban ghi tho (nguon: {lineage})")

    # 2) Lam sach du lieu.
    _step(2, "Lam sach du lieu...")
    clean_df = build_clean_dataframe(records, run_date)
    if clean_df.empty:
        raise RuntimeError("Dataframe sau khi lam sach rong, khong the tiep tuc pipeline.")
    write_csv(clean_df, settings.paths.clean_csv)
    clean_df.to_json(settings.paths.clean_json, orient="records", indent=2, force_ascii=True)
    print(f"      -> {len(clean_df)} dong sach -> {settings.paths.clean_csv.name}")

    # 3) Data quality gate (GX 1.x) va freshness SLA.
    _step(3, "Chay Data Quality Gate (Great Expectations 1.x)...")
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(
        f"      -> quality success={quality['success']} "
        f"({quality['expectations_passed']}/{quality['expectations_total']} expectation dat)"
    )
    print(
        f"      -> freshness is_fresh={freshness['is_fresh']} "
        f"(stale {freshness['stale_rows']}/{freshness['total_rows']})"
    )
    if not quality["success"]:
        print("      !! CANH BAO: du lieu chua dat chuan, baseline co the khong dang tin cay.")

    # 4) Build ChromaDB index.
    _step(4, "Build ChromaDB index...")
    index = LocalEmbeddingIndex.build(clean_df, settings)
    print(f"      -> collection '{settings.baseline_collection_name}' voi {len(index.documents)} docs")

    # 5) Tao hoac doc lai benchmark test set.
    _step(5, "Tao / doc lai benchmark test set...")
    test_set = load_or_create_test_set(
        clean_df, settings.paths.eval_testset, refresh=settings.refresh_test_set
    )
    cache_note = "doc lai tu cache" if test_set.loaded_from_cache else "sinh moi"
    print(f"      -> {len(test_set)} cau hoi ({cache_note})")

    # 6) Danh gia baseline (retrieval hit rate, token F1, LLM judge).
    _step(6, "Danh gia baseline (retrieval + token F1 + LLM judge)...")
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    print(f"      -> hit_rate={bundle.summary['retrieval_hit_rate']:.4f} "
          f"mean_token_f1={bundle.summary['mean_token_f1']:.4f} "
          f"judge_accuracy={bundle.summary['judge_accuracy']:.4f}")

    # 7) Sinh bao cao markdown.
    _step(7, "Sinh bao cao Phase 1...")
    source_summary = _source_summary(settings, records, clean_df, lineage)
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    print(f"      -> {settings.paths.baseline_report}")

    # 8) Tom tat artifacts.
    _step(8, "Hoan tat. Cac artifact da sinh:")
    artifacts = [
        settings.paths.clean_csv,
        settings.paths.clean_json,
        settings.paths.chroma_dir,
        settings.paths.embeddings_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
        settings.paths.baseline_quality_report,
        settings.paths.freshness_report,
        settings.paths.baseline_report,
    ]
    for path in artifacts:
        mark = "OK " if path.exists() else "THIEU"
        print(f"      [{mark}] {path}")

    print(
        f"\nBaseline hoan tat: {len(clean_df)} tai lieu, {len(test_set)} cau hoi, "
        f"hit_rate={bundle.summary['retrieval_hit_rate']:.4f}."
    )
