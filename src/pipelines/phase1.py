from __future__ import annotations

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.embeddings import CustomOpenAIEmbeddings
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm


def main() -> None:
    settings = load_settings()
    require_llm_credentials(settings)

    print("[Phase 1] Bắt đầu chạy baseline pipeline...")

    # Verify custom API connectivity
    print("[Phase 1] Kiểm tra kết nối API...")
    try:
        embeddings = CustomOpenAIEmbeddings(settings)
        test_embedding = embeddings.embed_query("test")
        if not test_embedding or len(test_embedding) == 0:
            raise ValueError("Embedding model returned empty vector")
        print(f"  [OK] Ket noi embedding thanh cong (vector size: {len(test_embedding)})")
    except Exception as exc:
        print(f"  ✗ Lỗi embedding: {exc}")
        raise

    try:
        llm = build_llm(settings)
        llm.invoke("Xin chào")
        print(f"  ✓ Kết nối LLM thành công")
    except Exception as exc:
        print(f"  ✗ Lỗi LLM: {exc}")
        raise

    run_date = now_utc()

    print("[Phase 1] Bước 1/8: Lấy hoặc tải raw records...")
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        try:
            records = fetch_source_records(settings)
        except Exception as exc:
            if settings.paths.raw_records_json.exists():
                print(f"  ⚠ Lấy dữ liệu từ API thất bại ({exc}), sử dụng bản sao local")
                records = load_raw_records(settings.paths.raw_records_json)
            else:
                raise
    else:
        records = load_raw_records(settings.paths.raw_records_json)
    print(f"  ✓ Đã tải {len(records)} bản ghi")

    print("[Phase 1] Bước 2/8: Làm sạch dữ liệu...")
    df_clean = build_clean_dataframe(records, run_date)
    print(f"  ✓ Đã làm sạch {len(df_clean)} bản ghi")

    print("[Phase 1] Bước 3/8: Lưu dữ liệu làm sạch...")
    write_csv(df_clean, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df_clean.to_dict(orient="records"))
    print(f"  ✓ Đã lưu tại {settings.paths.clean_csv}")

    print("[Phase 1] Bước 4/8: Xây dựng bộ test...")
    existing = read_json(settings.paths.eval_testset) if settings.paths.eval_testset.exists() else []
    needs_refresh = (
        settings.refresh_test_set
        or not existing
        or not str(existing[0].get("question", "")).startswith("Tóm tắt")
        and "tác giả" not in str(existing[0].get("question", "")).lower()
    )
    if needs_refresh:
        test_set = build_test_set(df_clean, settings.paths.eval_testset)
    else:
        test_set = existing
    print(f"  ✓ Đã tạo {len(test_set)} câu hỏi test")

    print("[Phase 1] Bước 5/8: Xây dựng chỉ mục ChromaDB...")
    index = LocalEmbeddingIndex.build(df_clean, settings, settings.paths.embeddings_json)
    print(f"  ✓ Đã lập chỉ mục {len(df_clean)} tài liệu trong collection '{index.collection_name}'")

    print("[Phase 1] Bước 6/8: Kiểm định chất lượng dữ liệu...")
    quality = run_data_quality_checks(df_clean, settings, "baseline")
    freshness = build_freshness_report(df_clean, settings, settings.paths.freshness_report)
    quality_status = "✓ ĐẠT" if quality['success'] else "✗ KHÔNG ĐẠT"
    freshness_status = "✓ Tươi" if freshness['is_fresh'] else "✗ Cũ"
    print(f"  Quality Gate: {quality_status}, Độ tươi: {freshness_status}")

    print("[Phase 1] Bước 7/8: Đánh giá baseline...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"  ✓ Chỉ số: Hit Rate={bundle.summary['retrieval_hit_rate']:.3f}, Token F1={bundle.summary['mean_token_f1']:.3f}")

    print("[Phase 1] Bước 8/8: Tạo báo cáo...")
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary={"raw_records": len(records), "clean_records": len(df_clean)},
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    print(f"  ✓ Báo cáo đã lưu tại {settings.paths.baseline_report}")

    print("[Phase 1] ✅ Baseline pipeline hoàn tất")
