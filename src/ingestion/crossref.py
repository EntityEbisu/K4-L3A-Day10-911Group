from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


_JATS_RE = re.compile(r"</?jats:[^>]+>|<jats:[^>]+/>", re.IGNORECASE)
_TAG_RE = re.compile(r"</?[^>]+>")


def strip_jats(value: str) -> str:
    cleaned = _JATS_RE.sub(" ", value or "")
    cleaned = _TAG_RE.sub(" ", cleaned)
    return normalize_whitespace(cleaned)


def _date_from_parts(date_parts: list | None) -> str:
    if not date_parts:
        return ""
    year = date_parts[0]
    month = date_parts[1] if len(date_parts) >= 2 else 1
    day = date_parts[2] if len(date_parts) >= 3 else 1
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_published(item: dict) -> str:
    for key in ("published", "published-print", "issued", "published-online"):
        parts = item.get(key, {}).get("date-parts") if isinstance(item.get(key), dict) else None
        if parts:
            formatted = _date_from_parts(parts[0])
            if formatted:
                return formatted
    created = item.get("created", {})
    if isinstance(created, dict):
        date_time = created.get("date-time") or ""
        if date_time:
            return date_time[:10]
        parts = created.get("date-parts")
        if parts:
            return _date_from_parts(parts[0])
    return ""


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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records = []
    items = payload.get("message", {}).get("items", [])

    for item in items:
        try:
            doi = (item.get("DOI") or "").lower()
            title = strip_jats(item.get("title", [""])[0] if item.get("title") else "")
            if not doi or not title:
                continue

            summary = strip_jats(item.get("abstract") or "")
            authors = []
            for author in item.get("author", []) or []:
                name_parts = [author.get("given") or "", author.get("family") or ""]
                name = normalize_whitespace(" ".join(name_parts))
                if name:
                    authors.append(name)

            subjects = item.get("subject") or []
            categories = [strip_jats(str(s)) for s in subjects if s]
            primary_category = categories[0] if categories else "Unclassified"
            published_date = _extract_published(item)
            updated_date = ""
            if isinstance(item.get("created"), dict):
                updated_date = (item["created"].get("date-time") or "")[:10]
            if item.get("updated"):
                updated_date = str(item["updated"])[:10]

            abs_url = item.get("URL") or ""
            pdf_url = ""
            links = item.get("link") or []
            if isinstance(links, list) and links:
                pdf_url = links[0].get("URL") or ""

            records.append(
                PaperRecord(
                    paper_id=doi,
                    title=title,
                    summary=summary,
                    authors=authors,
                    categories=categories,
                    primary_category=primary_category,
                    published=published_date,
                    updated=updated_date,
                    abs_url=abs_url,
                    pdf_url=pdf_url,
                    comment=item.get("note") or "",
                )
            )
        except Exception:
            continue
    return records


def _persist_records(settings: Settings, records: list[PaperRecord]) -> None:
    write_json(
        settings.paths.raw_records_json,
        [
            {
                "paper_id": r.paper_id,
                "title": r.title,
                "summary": r.summary,
                "authors": r.authors,
                "categories": r.categories,
                "primary_category": r.primary_category,
                "published": r.published,
                "updated": r.updated,
                "abs_url": r.abs_url,
                "pdf_url": r.pdf_url,
                "comment": r.comment,
            }
            for r in records
        ],
    )


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    if not settings.refresh_source and settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    url = "https://api.crossref.org/works"
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                payload = response.json()
                write_json(settings.paths.raw_api_response, payload)
                records = parse_crossref_payload(payload)
                _persist_records(settings, records)
                return records
            if response.status_code in (429, 503) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            last_error = RuntimeError(f"Crossref HTTP {response.status_code}")
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)

    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    if settings.paths.raw_api_response.exists():
        records = parse_crossref_payload(read_json(settings.paths.raw_api_response))
        _persist_records(settings, records)
        return records
    raise RuntimeError(f"Failed to fetch Crossref data: {last_error}")


def load_raw_records(path: Path) -> list[PaperRecord]:
    data = read_json(path)
    return [
        PaperRecord(
            paper_id=item["paper_id"],
            title=item["title"],
            summary=item["summary"],
            authors=item["authors"],
            categories=item["categories"],
            primary_category=item.get("primary_category", "Unclassified"),
            published=item["published"],
            updated=item.get("updated", ""),
            abs_url=item.get("abs_url", ""),
            pdf_url=item.get("pdf_url", ""),
            comment=item.get("comment", ""),
        )
        for item in data
    ]
