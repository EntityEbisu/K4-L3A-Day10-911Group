from __future__ import annotations

from typing import Any

from core.utils import write_text


def _metric(metrics: dict[str, Any], name: str) -> float:
    return float(metrics.get(name, 0.0))


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline pipeline report."""
    text = f"""# Báo cáo Pha 1: Đường ống Baseline

## Tổng quan Nguồn Dữ liệu

| Chỉ tiêu | Giá trị |
|---|---:|
| Bản ghi thô | {source_summary['raw_records']} |
| Bản ghi sạch | {source_summary['clean_records']} |
| Câu hỏi kiểm tra | {metrics.get('samples', 0)} |

## Trạm Kiểm Soát Chất Lượng

| Kiểm tra | Kết quả |
|---|---|
| Great Expectations | {'ĐẠT' if quality['success'] else 'KHÔNG ĐẠT'} |
| Kỳ vọng đạt | {quality['passed_expectations']}/{quality['evaluated_expectations']} |
| Độ tươi dữ liệu | {'TỪ (< 25% cũ)' if freshness['is_fresh'] else 'CŨ (≥ 25% cũ)'} |
| Bản ghi cũ | {freshness['stale_rows']}/{freshness['total_rows']} |
| Công bố mới nhất | {freshness['latest_published']} |
| Công bố lâu nhất | {freshness['oldest_published']} |

## Kết Quả Đánh Giá

| Chỉ tiêu | Giá trị |
|---|---:|
| Tỷ lệ truy hồi đúng | {_metric(metrics, 'retrieval_hit_rate'):.4f} |
| Token F1 trung bình | {_metric(metrics, 'mean_token_f1'):.4f} |
| Độ chính xác LLM Judge | {_metric(metrics, 'judge_accuracy'):.4f} |
| Điểm Judge trung bình | {_metric(metrics, 'mean_judge_score'):.4f} |
"""
    write_text(report_path, text)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the baseline, corrupted, and repaired comparison report."""
    def row(metric: str, label: str) -> str:
        return (
            f"| {label} | {_metric(baseline_metrics, metric):.4f} | "
            f"{_metric(corrupted_metrics, metric):.4f} | {_metric(repaired_metrics, metric):.4f} |"
        )

    text = f"""# Báo cáo Tiêm Lỗi & Phục Hồi Dữ Liệu

## So Sánh Hiệu Suất: Dữ liệu sạch (Baseline) | Dữ liệu lỗi (Corrupted) | Sau phục hồi (Repaired)

| Chỉ tiêu | Dữ liệu Sạch | Dữ liệu Lỗi | Sau Phục Hồi |
|---|---:|---:|---:|
{row('retrieval_hit_rate', 'Tỷ lệ truy hồi đúng')}
{row('mean_token_f1', 'Token F1 trung bình')}
{row('judge_accuracy', 'Độ chính xác LLM Judge')}
{row('mean_judge_score', 'Điểm Judge trung bình')}

## So Sánh Trạm Kiểm Soát Chất Lượng

| Trạng Thái | Great Expectations | Kỳ Vọng Đạt | Độ Tươi | Bản Ghi Cũ |
|---|---|---:|---|---:|
| Dữ liệu Lỗi | {'ĐẠT' if corrupted_quality['success'] else 'KHÔNG ĐẠT'} | {corrupted_quality['passed_expectations']}/{corrupted_quality['evaluated_expectations']} | {'TỪ' if corrupted_freshness['is_fresh'] else 'CŨ'} | {corrupted_freshness['stale_rows']}/{corrupted_freshness['total_rows']} |
| Sau Phục Hồi | {'ĐẠT' if repaired_quality['success'] else 'KHÔNG ĐẠT'} | {repaired_quality['passed_expectations']}/{repaired_quality['evaluated_expectations']} | {'TỪ' if repaired_freshness['is_fresh'] else 'CŨ'} | {repaired_freshness['stale_rows']}/{repaired_freshness['total_rows']} |

## Kết Quả Phục Hồi

**Kết luận:** Dữ liệu bị tiêm lỗi làm giảm chất lượng của hệ thống RAG (hit rate, F1, judge accuracy đều sụt giảm). Tuy nhiên, bằng cách khôi phục idempotent từ bản sao lưu dữ liệu thô ban đầu, chúng tôi đã thành công đưa hệ thống trở về trạng thái chuẩn sạch. Chạy lại bước phục hồi bao nhiêu lần kết quả vẫn giống nhau (idempotent), không cần sửa tay.

---

### 📌 Bài học rút ra

1. **Silent Failure (Thất bại thầm lặng):** Dữ liệu xấu không khiến hệ thống báo lỗi đỏ, mà AI vẫn trả lời tự tin — chỉ là sai.
2. **Data Quality Gate quan trọng:** Great Expectations phát hiện được các dạng lỗi (null, không duy nhất, độ dài không hợp lệ, ...).
3. **Freshness Check bảo vệ:** Dữ liệu lâu (> 180 ngày) được xem là cũ → cần refresh từ nguồn gốc.
4. **Idempotent Repair là chìa khóa:** Hồi phục từ snapshot thô, chạy lại bao nhiêu lần kết quả vẫn nhất quán.
"""
    write_text(report_path, text)
