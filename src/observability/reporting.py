from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.utils import write_text


METRIC_LABELS = {
    "samples": "So cau hoi",
    "retrieval_hit_rate": "Retrieval Hit Rate",
    "mean_token_f1": "Mean Token F1",
    "judge_accuracy": "LLM Judge Accuracy",
    "mean_judge_score": "Mean LLM Judge Score",
}

# Cac chi so luon hien thi 4 chu so thap phan cho dong nhat giua cac trang thai.
# (statistics.mean co the tra ve int khi chia het, vi du mean([5,5]) == 5.)
NUMERIC_METRICS = frozenset(
    {"retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"}
)


def _fmt(value: Any) -> str:
    """Dinh dang gia tri cho bang markdown."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "Co" if value else "Khong"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _fmt_metric(key: str, value: Any) -> str:
    """Dinh dang chi so so; ep ve float de tranh lech dinh dang int/float."""
    if key in NUMERIC_METRICS and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.4f}"
    return _fmt(value)


def _metric_rows(metrics: dict[str, Any]) -> list[str]:
    """Tao cac dong bang chi so, bo qua khoi ragas long nhau."""
    rows: list[str] = []
    for key, label in METRIC_LABELS.items():
        if key in metrics:
            rows.append(f"| {label} | {_fmt_metric(key, metrics[key])} |")
    return rows


def _quality_section(quality: dict[str, Any]) -> list[str]:
    """Bang ket qua 4 hang rao chat luong + danh sach loi neu co."""
    lines = [
        "## 3. Data Quality Gate (Great Expectations 1.x)",
        "",
        f"- Ket qua tong: **{'DAT' if quality.get('success') else 'KHONG DAT'}**",
        f"- So expectation dat: {quality.get('expectations_passed')}/"
        f"{quality.get('expectations_total')}",
        "",
        "| Expectation | Cot | Ket qua |",
        "| :--- | :--- | :--- |",
    ]
    for item in quality.get("expectation_results", []):
        status = "dat" if item.get("success") else "**KHONG DAT**"
        lines.append(f"| `{item.get('rule') or item.get('expectation')}` | "
                     f"{item.get('column') or '-'} | {status} |")

    failures = quality.get("failures") or []
    if failures:
        lines += ["", "**Chi tiet loi phat hien:**", ""]
        for item in failures:
            detail = []
            if item.get("unexpected_count") is not None:
                detail.append(f"unexpected={item['unexpected_count']}")
            if item.get("observed_value") is not None:
                detail.append(f"observed={item['observed_value']}")
            sample = item.get("sample_unexpected")
            if sample:
                detail.append(f"sample={sample}")
            lines.append(
                f"- `{item.get('rule')}` (cot `{item.get('column') or '-'}`): "
                f"{', '.join(detail) if detail else 'khong dat'}"
            )
    lines.append("")
    return lines


def _freshness_section(freshness: dict[str, Any], threshold_days: int = 180) -> list[str]:
    lines = [
        "## 4. Freshness SLA",
        "",
        f"- Bai moi nhat: {_fmt(freshness.get('latest_published'))}",
        f"- Bai cu nhat: {_fmt(freshness.get('oldest_published'))}",
        f"- So bai qua han (>{threshold_days} ngay): "
        f"{freshness.get('stale_rows')}/{freshness.get('total_rows')}",
        f"- Ti le qua han: {_fmt(freshness.get('stale_ratio'))} (nguong cho phep 0.25)",
        f"- Trang thai: **{'TUOI (is_fresh=True)' if freshness.get('is_fresh') else 'DA MOC - CAN CAP NHAT (is_fresh=False)'}**",
        "",
    ]
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    generated_at = datetime.now(UTC).isoformat()

    lines = [
        "# Phase 1 - Baseline Data Pipeline & RAG Report",
        "",
        f"> Sinh tu dong luc: `{generated_at}`",
        "",
        "## 1. Nguon du lieu (Data Lineage)",
        "",
        "| Thong tin | Gia tri |",
        "| :--- | :--- |",
        f"| Nguon API | {_fmt(source_summary.get('source_api'))} |",
        f"| Truy van | `{_fmt(source_summary.get('source_query'))}` |",
        f"| Bo loc | `{_fmt(source_summary.get('source_filter'))}` |",
        f"| Cach lay du lieu | {_fmt(source_summary.get('lineage_mode'))} |",
        f"| Raw response | `{_fmt(source_summary.get('raw_response_path'))}` |",
        f"| Raw records | `{_fmt(source_summary.get('raw_records_path'))}` |",
        f"| Ban ghi tho | {_fmt(source_summary.get('raw_record_count'))} |",
        f"| Dong sach | {_fmt(source_summary.get('clean_rows'))} |",
        f"| Dong bi loai | {_fmt(source_summary.get('dropped_rows'))} |",
        f"| Collection | `{_fmt(source_summary.get('collection_name'))}` |",
        f"| Embedding model | `{_fmt(source_summary.get('embedding_model'))}` |",
        "",
        "## 2. Chi so Baseline",
        "",
        "| Chi so | Gia tri |",
        "| :--- | :--- |",
        *_metric_rows(metrics),
        "",
    ]

    lines += _quality_section(quality)
    lines += _freshness_section(freshness)

    ragas = metrics.get("ragas")
    lines += ["## 5. Ragas (tuy chon)", ""]
    if isinstance(ragas, dict) and ragas.get("skipped"):
        lines.append(f"- Bo qua: {ragas['skipped']}")
    elif isinstance(ragas, dict) and ragas.get("error"):
        lines.append(f"- Loi: {ragas['error']}")
    else:
        lines.append(f"- `{ragas}`")
    lines += ["", "## 6. Ket luan", ""]

    hit_rate = metrics.get("retrieval_hit_rate")
    fresh = freshness.get("is_fresh")
    gate = quality.get("success")
    lines.append(
        f"- Baseline dat hit rate **{_fmt(hit_rate)}** tren "
        f"{_fmt(metrics.get('samples'))} cau hoi benchmark."
    )
    lines.append(
        f"- Data quality gate: **{'dat' if gate else 'khong dat'}**; "
        f"du lieu **{'con tuoi' if fresh else 'da moc'}**."
    )
    lines.append(
        "- Cac chi so nay la moc so sanh (baseline) cho hai pha tiep theo: "
        "tien loi du lieu (corruption) va phuc hoi (repair)."
    )
    lines.append("")

    write_text(Path(report_path), "\n".join(lines))


CORRUPTION_LABELS = {
    "baseline": "Baseline (sach)",
    "corrupted": "Corrupted (tien loi)",
    "repaired": "Repaired (phuc hoi)",
}


def _comparison_table(
    metric_rows: list[tuple[str, dict[str, Any]]],
    keys: tuple[str, ...],
) -> list[str]:
    header = "| Chi so | " + " | ".join(name for name, _ in metric_rows) + " |"
    divider = "| :--- | " + " | ".join(":---" for _ in metric_rows) + " |"
    lines = [header, divider]
    for key in keys:
        label = METRIC_LABELS.get(key, key)
        cells = " | ".join(_fmt_metric(key, metrics.get(key)) for _, metrics in metric_rows)
        lines.append(f"| {label} | {cells} |")
    return lines


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
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    generated_at = datetime.now(UTC).isoformat()
    metric_rows = [
        (CORRUPTION_LABELS["baseline"], baseline_metrics),
        (CORRUPTION_LABELS["corrupted"], corrupted_metrics),
        (CORRUPTION_LABELS["repaired"], repaired_metrics),
    ]

    lines = [
        "# Corruption & Repair - Bao Cao Doi Chieu 3 Trang Thai",
        "",
        f"> Sinh tu dong luc: `{generated_at}`",
        "",
        "## 1. Bang so sanh chi so",
        "",
        *_comparison_table(
            metric_rows,
            (
                "samples",
                "retrieval_hit_rate",
                "mean_token_f1",
                "judge_accuracy",
                "mean_judge_score",
            ),
        ),
        "",
        "## 2. Muc do suy giam (Degradation)",
        "",
        "| Chi so | Baseline | Corrupted | Chenh lech | Muc giam |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy"):
        base = baseline_metrics.get(key)
        corrupt = corrupted_metrics.get(key)
        if isinstance(base, (int, float)) and isinstance(corrupt, (int, float)):
            delta = corrupt - base
            drop = (delta / base * 100.0) if base else 0.0
            lines.append(
                f"| {METRIC_LABELS.get(key, key)} | {_fmt_metric(key, base)} "
                f"| {_fmt_metric(key, corrupt)} | "
                f"{delta:+.4f} | {drop:+.1f}% |"
            )

    lines += ["", "## 3. Phuc hoi (Repair)", ""]
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy"):
        base = baseline_metrics.get(key)
        repaired = repaired_metrics.get(key)
        if isinstance(base, (int, float)) and isinstance(repaired, (int, float)):
            regained = ((repaired - base) / base * 100.0) if base else 0.0
            lines.append(
                f"- {METRIC_LABELS.get(key, key)}: {_fmt_metric(key, repaired)} "
                f"so voi baseline {_fmt_metric(key, base)} ({regained:+.1f}%)"
            )

    lines += ["", "## 4. Chat luong du lieu sau tien loi / phuc hoi", ""]
    for label, quality, freshness in (
        ("Corrupted", corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_quality, repaired_freshness),
    ):
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"- Quality gate: **{'dat' if quality.get('success') else 'khong dat'}** "
                     f"({quality.get('expectations_passed')}/{quality.get('expectations_total')})")
        lines.append(f"- So loi phat hien: {len(quality.get('failures') or [])}")
        lines.append(f"- Freshness: stale {freshness.get('stale_rows')}/"
                     f"{freshness.get('total_rows')}, "
                     f"is_fresh={_fmt(freshness.get('is_fresh'))}")
        lines.append("")

    lines += [
        "## 5. Ket luan",
        "",
        "- Tien loi du lieu lam suy giam ro ret chat luong cau tra loi cua RAG.",
        "- Co che Idempotent Repair phuc hoi du lieu tu raw snapshot, dua chi so tro lai "
        "muc xap xi baseline.",
        "",
    ]

    write_text(Path(report_path), "\n".join(lines))
