from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


# Endpoint cong khai cua Crossref Metadata API.
CROSSREF_ENDPOINT = "https://api.crossref.org/works"

# Cac status code duoc coi la "tam thoi" -> nen retry truoc khi chuyen sang snapshot offline.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30
# Crossref khuyen khich gui User-Agent kem lien he de duoc uu tien phuc vu.
USER_AGENT = "day10-data-observability-lab/0.1 (mailto:student@example.edu)"

# Xoa the HTML/JATS XML rac (vi du <jats:p>, </jats:p>, <italic>, ...).
TAG_PATTERN = re.compile(r"<[^>]+>")


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


def _first_text(value: Any) -> str:
    """Lay chuoi dau tien tu field Crossref (thuong la list hoac str)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        return _first_text(value.get("value") or value.get("name") or value.get("URL"))
    return str(value)


def _clean_text(value: Any) -> str:
    """Bo the JATS/HTML, giai ma HTML entity va chuan hoa khoang trang."""
    text = _first_text(value)
    if not text:
        return ""
    # Chay 2 luot: xu ly ca truong hop the bi escape (&lt;jats:p&gt;) lan the tho.
    for _ in range(2):
        text = TAG_PATTERN.sub(" ", text)
        text = html.unescape(text)
    # Bo khoang trang mo coi truoc dau cau do buoc xoa the o tren de lai
    # (vi du "world .</jats:p>" -> "world ." -> "world.").
    text = re.sub(r"\s+([,.;:!?%)\]}])", r"\1", text)
    return normalize_whitespace(text)


def _normalize_doi(value: Any) -> str:
    """Chuan hoa DOI: bo tien to URL, bo khoang trang thua."""
    doi = _clean_text(value)
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip().strip("/")


def _iso_date(value: Any) -> str:
    """Parse ngay Crossref sang ISO 8601 (YYYY-MM-DD)."""
    if isinstance(value, dict):
        # Dang pho bien: {"date-parts": [[2026, 5, 20]]}
        date_parts = value.get("date-parts")
        if isinstance(date_parts, (list, tuple)) and date_parts:
            parts = date_parts[0]
            if isinstance(parts, (list, tuple)) and parts:
                numbers: list[int] = []
                for part in parts[:3]:
                    try:
                        numbers.append(int(part))
                    except (TypeError, ValueError):
                        break
                if numbers:
                    year = numbers[0]
                    month = numbers[1] if len(numbers) > 1 else 1
                    day = numbers[2] if len(numbers) > 2 else 1
                    return f"{year:04d}-{month:02d}-{day:02d}"
        # Dang ISO day du: {"date-time": "2026-05-20T10:00:00Z"}
        return _iso_date(value.get("date-time"))
    if isinstance(value, (list, tuple)):
        for item in value:
            parsed = _iso_date(item)
            if parsed:
                return parsed
        return ""
    if isinstance(value, str):
        candidate = value.strip()
        if len(candidate) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", candidate):
            return candidate[:10]
    return ""


def _first_date(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        parsed = _iso_date(item.get(key))
        if parsed:
            return parsed
    return ""


def _parse_authors(value: Any) -> list[str]:
    """Chuan hoa danh sach tac gia Crossref thanh ["Given Family", ...]."""
    if not isinstance(value, (list, tuple)):
        return []

    authors: list[str] = []
    for author in value:
        if isinstance(author, str):
            name = normalize_whitespace(author)
        elif isinstance(author, dict):
            given = normalize_whitespace(str(author.get("given") or ""))
            family = normalize_whitespace(str(author.get("family") or ""))
            name = normalize_whitespace(f"{given} {family}") or normalize_whitespace(
                str(author.get("name") or "")
            )
        else:
            name = ""
        if name and name not in authors:
            authors.append(name)
    return authors


def _parse_categories(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        value = [value] if value else []
    categories: list[str] = []
    for subject in value:
        label = _clean_text(subject)
        if label and label not in categories:
            categories.append(label)
    return categories


def _parse_pdf_url(item: dict, fallback: str) -> str:
    """Uu tien link PDF day du trong `link`, neu khong co thi dung URL truy cap."""
    links = item.get("link")
    if isinstance(links, (list, tuple)):
        for link in links:
            if not isinstance(link, dict):
                continue
            url = _first_text(link.get("URL"))
            content_type = _first_text(link.get("content-type")).lower()
            if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
                return url
    return fallback


def _parse_item(item: Any) -> PaperRecord | None:
    """Boc tach 1 phan tu Crossref thanh PaperRecord, tra ve None neu khong hop le."""
    if not isinstance(item, dict):
        return None

    paper_id = _normalize_doi(item.get("DOI"))
    title = _clean_text(item.get("title"))
    # Khong co DOI hoac title thi khong the dinh danh/tim kiem -> bo record.
    if not paper_id or not title:
        return None

    summary = _clean_text(item.get("abstract"))
    authors = _parse_authors(item.get("author"))
    categories = _parse_categories(item.get("subject"))

    # `published` uu tien published > issued > created; `updated` lay moc created gan nhat.
    published = _first_date(item, ("published", "issued", "created"))
    updated = _first_date(item, ("created", "indexed", "deposited")) or published

    abs_url = _first_text(item.get("URL")) or f"https://doi.org/{paper_id}"
    if not abs_url.startswith("http"):
        abs_url = f"https://doi.org/{paper_id}"

    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=summary,
        authors=authors,
        categories=categories,
        primary_category=categories[0] if categories else "",
        published=published,
        updated=updated,
        abs_url=abs_url,
        pdf_url=_parse_pdf_url(item, abs_url),
        comment=f"Crossref record {paper_id}",
    )


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Luong xu ly:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text (bo the JATS/HTML) va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    if not isinstance(payload, dict):
        return []

    message = payload.get("message")
    if not isinstance(message, dict):
        return []

    items = message.get("items")
    if not isinstance(items, (list, tuple)):
        return []

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        record = _parse_item(item)
        if record is None or record.paper_id in seen_ids:
            continue
        seen_ids.add(record.paper_id)
        records.append(record)
    return records


def _request_payload(settings: Settings) -> dict:
    """Goi Crossref API voi retry cho cac status code tam thoi (429/503/...)."""
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        # Giu response gon va on dinh de luu raw artifact.
        "select": "DOI,title,abstract,author,subject,published,created,URL,link",
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_ENDPOINT,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:  # mat mang, DNS loi, timeout...
            last_error = exc
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code not in RETRYABLE_STATUS:
                # 4xx khac (vi du 400 do filter sai) thi retry la vo nghia.
                response.raise_for_status()
            last_error = requests.HTTPError(f"Crossref tra ve HTTP {response.status_code}")

        if attempt < MAX_ATTEMPTS:
            # Backoff luy tien: 1.5s, 3s... de khong dap them vao API dang qua tai.
            time.sleep(1.5 * attempt)

    raise RuntimeError(f"Khong the goi Crossref API sau {MAX_ATTEMPTS} lan thu: {last_error}")


def _records_to_payload(records: list[PaperRecord]) -> list[dict[str, Any]]:
    return [
        {
            "paper_id": record.paper_id,
            "title": record.title,
            "summary": record.summary,
            "authors": list(record.authors),
            "categories": list(record.categories),
            "primary_category": record.primary_category,
            "published": record.published,
            "updated": record.updated,
            "abs_url": record.abs_url,
            "pdf_url": record.pdf_url,
            "comment": record.comment,
        }
        for record in records
    ]


def _load_snapshot(path: Path, reason: str) -> dict:
    """Doc snapshot offline; bao loi ro rang neu snapshot khong ton tai."""
    if not path.exists():
        raise RuntimeError(
            f"{reason} Va khong tim thay snapshot offline tai {path}. "
            "Hay chay lai khi co mang hoac bo sung file snapshot."
        )
    print(f"[crossref] {reason} -> Dung snapshot offline: {path}")
    return read_json(path)


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    Co che Cuu ho Offline (Dual-Mode):
    - Neu `settings.refresh_source` = False va snapshot da ton tai: dung luon snapshot
      (khong goi mang), giup pipeline chay on dinh trong phong lab.
    - Neu phai goi API: retry cac status 429/503..., khi that bai hoac response rong
      thi tu dong chuyen sang snapshot `data/raw/crossref_response.json`.
    Luon ghi 2 raw artifact de bao toan data lineage.
    """
    snapshot_path = settings.paths.raw_api_response

    # --- Mode 1: uu tien snapshot co san khi khong yeu cau refresh ---
    if not settings.refresh_source and snapshot_path.exists():
        payload = read_json(snapshot_path)
        print(f"[crossref] Dung snapshot offline: {snapshot_path}")
    else:
        # --- Mode 2: goi API that, that bai thi cuu ho bang snapshot ---
        try:
            payload = _request_payload(settings)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            payload = _load_snapshot(snapshot_path, f"Goi Crossref API that bai ({exc}).")
        else:
            records = parse_crossref_payload(payload)
            if records:
                # Luu raw response nguyen ban truoc khi bien doi (raw preservation).
                write_json(snapshot_path, payload)
            else:
                payload = _load_snapshot(snapshot_path, "Crossref API tra ve 0 record hop le.")

    records = parse_crossref_payload(payload)
    if not records:
        raise RuntimeError(
            f"Khong parse duoc PaperRecord nao tu {snapshot_path}. Kiem tra lai dinh dang payload."
        )

    write_json(settings.paths.raw_records_json, _records_to_payload(records))
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`.

    Ho tro ca 2 dinh dang:
    - List record da parse (data/raw/crossref_records.json).
    - Payload Crossref tho co `message.items` (data/raw/crossref_response.json),
      phuc vu co che Idempotent Repair tu raw snapshot.
    """
    payload = read_json(path)

    if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
        return parse_crossref_payload(payload)

    if not isinstance(payload, (list, tuple)):
        raise ValueError(f"Snapshot {path} khong phai list record hay Crossref payload.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        paper_id = _normalize_doi(row.get("paper_id") or row.get("DOI"))
        title = _clean_text(row.get("title"))
        if not paper_id or not title or paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        authors = row.get("authors")
        if not isinstance(authors, (list, tuple)):
            authors = _parse_authors(row.get("author"))
        authors = [normalize_whitespace(str(author)) for author in authors if str(author).strip()]

        categories = row.get("categories")
        if not isinstance(categories, (list, tuple)):
            categories = _parse_categories(row.get("subject"))
        categories = [normalize_whitespace(str(item)) for item in categories if str(item).strip()]

        published = _iso_date(row.get("published")) or _first_date(row, ("published", "issued", "created"))
        updated = _iso_date(row.get("updated")) or _first_date(
            row, ("created", "indexed", "deposited")
        ) or published

        abs_url = str(row.get("abs_url") or "").strip() or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=_clean_text(row.get("summary") or row.get("abstract")),
                authors=authors,
                categories=categories,
                primary_category=str(
                    row.get("primary_category") or (categories[0] if categories else "")
                ),
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=str(row.get("pdf_url") or "").strip() or abs_url,
                comment=str(row.get("comment") or f"Crossref record {paper_id}"),
            )
        )

    return records
