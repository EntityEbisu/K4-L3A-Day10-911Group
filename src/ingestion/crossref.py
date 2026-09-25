from __future__ import annotations

from dataclasses import asdict, dataclass
import html
import json
import logging
from pathlib import Path
import re
from typing import Any

import requests

from core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_text(text: str) -> str:
    if not text:
        return ""
    # Strip HTML / JATS XML tags (e.g. <jats:p>, </jats:p>, <jats:title>, etc.)
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return " ".join(cleaned.split()).strip()


def _clean_title(title_obj: Any) -> str:
    if isinstance(title_obj, list):
        raw = title_obj[0] if title_obj else ""
    else:
        raw = str(title_obj or "")
    raw = html.unescape(raw)
    return " ".join(raw.split()).strip()


def _parse_authors(author_list: Any) -> list[str]:
    if not isinstance(author_list, list):
        return []
    authors = []
    for a in author_list:
        if isinstance(a, dict):
            given = a.get("given", "").strip()
            family = a.get("family", "").strip()
            name = f"{given} {family}".strip()
            if not name:
                name = a.get("name", "").strip()
            if name:
                authors.append(name)
        elif isinstance(a, str) and a.strip():
            authors.append(a.strip())
    return authors


def _parse_date(date_obj: Any) -> str:
    if not date_obj:
        return ""
    if isinstance(date_obj, dict):
        if "date-parts" in date_obj and date_obj["date-parts"]:
            parts = date_obj["date-parts"][0]
            if len(parts) >= 3:
                return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            if len(parts) == 2:
                return f"{int(parts[0]):04d}-{int(parts[1]):02d}-01"
            if len(parts) == 1:
                return f"{int(parts[0]):04d}-01-01"
        if "date-time" in date_obj and isinstance(date_obj["date-time"], str):
            dt_str = date_obj["date-time"].strip()
            return dt_str.split("T")[0] if "T" in dt_str else dt_str
    elif isinstance(date_obj, str):
        dt_str = date_obj.strip()
        return dt_str.split("T")[0] if "T" in dt_str else dt_str
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thành danh sách PaperRecord.

    Bóc tách và chuẩn hóa:
    - paper_id: DOI chuẩn hóa
    - title: Chuẩn hóa khoảng trắng và unescape HTML
    - summary: Loại bỏ thẻ XML/HTML rác (JATS XML tags)
    - authors: Ghép họ và tên
    - categories: Danh sách subject
    - published: Định dạng ngày ISO 8601 (YYYY-MM-DD)
    """
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = str(item.get("DOI") or item.get("id") or "").strip()
        if not doi:
            continue

        title = _clean_title(item.get("title", ""))
        summary = _clean_text(item.get("abstract", ""))
        authors = _parse_authors(item.get("author", []))
        categories = [c.strip() for c in item.get("subject", []) if isinstance(c, str) and c.strip()]
        primary_category = categories[0] if categories else ""
        published = _parse_date(item.get("published"))
        updated = _parse_date(item.get("created")) or published

        abs_url = str(item.get("URL") or (f"https://doi.org/{doi}" if doi else "")).strip()

        # Tìm pdf_url nếu có trong link list
        pdf_url = ""
        for link in item.get("link", []):
            if isinstance(link, dict) and "pdf" in link.get("content-type", "").lower():
                pdf_url = link.get("URL", "").strip()
                break
        if not pdf_url:
            pdf_url = abs_url

        comment = f"Crossref record {doi}".strip()

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def _load_snapshot_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi Crossref API hoặc dùng Offline Snapshot (Dual-Mode) để lấy và lưu dữ liệu.

    1. Nếu refresh_source=True, thử kết nối Crossref API với query và filter.
    2. Nếu dính mã lỗi 429, 503 hoặc mất mạng, tự động kích hoạt fallback sang snapshot local.
    3. Lưu raw response vào settings.paths.raw_api_response.
    4. Parse payload thành list PaperRecord.
    5. Lưu records vào settings.paths.raw_records_json.
    """
    raw_response_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    payload: dict | None = None

    if settings.refresh_source:
        api_url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "Day10DataObservability/1.0 (mailto:student@vinuni.edu.vn)",
        }

        try:
            logger.info("Connecting to Crossref API: %s with params: %s", api_url, params)
            response = requests.get(api_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                payload = response.json()
                raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                with open(raw_response_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                logger.info("Successfully fetched data from Crossref API.")
            elif response.status_code in {429, 503}:
                logger.warning(
                    "Crossref API returned HTTP %s (Rate limit / Service unavailable). Activating offline fallback.",
                    response.status_code,
                )
            else:
                logger.warning("Crossref API returned HTTP %s. Activating offline fallback.", response.status_code)
        except Exception as e:
            logger.warning("Network connection failed (%s). Activating offline fallback.", e)

    # Offline Fallback (Dual-Mode): Nếu chưa lấy được từ API, nạp từ snapshot local
    if payload is None:
        if raw_response_path.exists():
            payload = _load_snapshot_payload(raw_response_path)
        else:
            # Tìm snapshot dự phòng tại data/raw/crossref_response.json
            fallback_path = settings.paths.project_dir / "data" / "raw" / "crossref_response.json"
            if fallback_path.exists():
                payload = _load_snapshot_payload(fallback_path)
            else:
                raise RuntimeError(
                    f"Cannot fetch from API and no offline snapshot found at {raw_response_path} or {fallback_path}"
                )

    # Parse payload thành PaperRecord
    records = parse_crossref_payload(payload)

    # Lưu parsed records vào raw_records_json để bảo toàn lineage
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    records_data = [asdict(r) for r in records]
    with open(raw_records_path, "w", encoding="utf-8") as f:
        json.dump(records_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và ánh xạ thành danh sách `PaperRecord`."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [PaperRecord(**item) for item in data]
