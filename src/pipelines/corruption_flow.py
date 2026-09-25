from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    if not settings.paths.clean_json.exists() or not settings.paths.baseline_metrics.exists():
        raise FileNotFoundError("Chạy script/run_phase1.py trước flow tham ô hóa.")

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = __import__("pandas").read_json(settings.paths.clean_json)

    print("[Tham ô] Tạo dữ liệu bị tham ô hóa...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    log = read_json(settings.paths.corruption_log)
    print(f"  ✓ Đã tạo tập dữ liệu tham ô hóa ({len(corrupted_df)} bản ghi)")
    for key, item in log.items():
        print(f"  - {key}: count={item.get('count')}")

    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.quality_dir / "corrupted_freshness_report.json",
    )
    print(f"  Quality Gate: {'✓ ĐẠT' if corrupted_quality['success'] else '✗ KHÔNG ĐẠT'}")

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(f"  Chỉ số sau tham ô: Hit Rate={corrupted_bundle.summary['retrieval_hit_rate']:.3f}, Token F1={corrupted_bundle.summary['mean_token_f1']:.3f}")

    print("\n[Phục hồi] Tái tạo dữ liệu từ bản sao raw...")
    repaired_df = build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    write_csv(repaired_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, repaired_df.to_dict(orient="records"))
    print(f"  ✓ Đã phục hồi {len(repaired_df)} bản ghi")

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.quality_dir / "repaired_freshness_report.json",
    )
    print(f"  Quality Gate: {'✓ ĐẠT' if repaired_quality['success'] else '✗ KHÔNG ĐẠT'}")

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(f"  Chỉ số sau phục hồi: Hit Rate={repaired_bundle.summary['retrieval_hit_rate']:.3f}, Token F1={repaired_bundle.summary['mean_token_f1']:.3f}")

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║     BẢNG SO SÁNH 3 TRẠNG THÁI DỮ LIỆU                    ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print(f"│ Trạng thái      │ Hit Rate  │ Token F1  │ Quality       │")
    print("├─────────────────┼───────────┼───────────┼───────────────┤")
    baseline_quality = read_json(settings.paths.baseline_quality_report) if settings.paths.baseline_quality_report.exists() else {"success": True}
    print(f"│ Sạch (Baseline) │ {baseline_metrics['retrieval_hit_rate']:8.4f} │ {baseline_metrics['mean_token_f1']:8.4f} │ {'✓ PASS' if baseline_quality.get('success') else '✗ FAIL':13} │")
    print(f"│ Lỗi (Corrupted) │ {corrupted_bundle.summary['retrieval_hit_rate']:8.4f} │ {corrupted_bundle.summary['mean_token_f1']:8.4f} │ {'✓ PASS' if corrupted_quality['success'] else '✗ FAIL':13} │")
    print(f"│ Phục hồi (Repaired) │ {repaired_bundle.summary['retrieval_hit_rate']:8.4f} │ {repaired_bundle.summary['mean_token_f1']:8.4f} │ {'✓ PASS' if repaired_quality['success'] else '✗ FAIL':13} │")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"\n✅ Báo cáo đã lưu tại {settings.paths.comparison_report}")
