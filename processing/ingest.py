from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.io_utils import file_sha256, safe_name, utc_now
from ..core.models import BookRecord


def page_count(pdf_path: Path, cfg: dict[str, Any]) -> int:
    try:
        from pypdf import PdfReader  # type: ignore

        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        try:
            import fitz  # type: ignore

            with fitz.open(pdf_path) as document:
                return int(document.page_count)
        except Exception:
            pattern = str(cfg["pdf_page_regex"]).encode("ascii")
            return len(re.findall(pattern, pdf_path.read_bytes()))


def _book_id_for(pdf_path: Path, book_name: str, cfg: dict[str, Any]) -> str:
    configured_ids = cfg.get("book_ids") if isinstance(cfg.get("book_ids"), dict) else {}
    configured = configured_ids.get(pdf_path.name) or configured_ids.get(book_name) or configured_ids.get(f"{book_name}.pdf")
    return configured or safe_name(book_name, str(cfg.get("unknown_book_id", "untitled_book")))


def build_book_record(
    *,
    pdf_path: Path,
    output_root: Path,
    cfg: dict[str, Any],
    book_name: str | None = None,
    book_id: str | None = None,
) -> BookRecord:
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    resolved_name = (book_name or pdf_path.stem).strip() or pdf_path.stem
    resolved_id = (book_id or _book_id_for(pdf_path, resolved_name, cfg)).strip()
    book_name_safe = safe_name(resolved_name, resolved_id)
    output_dir = output_root / book_name_safe
    return BookRecord(
        book_id=resolved_id,
        book_name=resolved_name,
        source_pdf=str(pdf_path),
        output_dir=str(output_dir),
        page_count=page_count(pdf_path, cfg),
        file_size=pdf_path.stat().st_size,
        file_hash=file_sha256(pdf_path, int(cfg["hash_chunk_size"])),
        status=cfg["statuses"]["ready"],
        created_at=utc_now(cfg["timestamp_format"]),
        pipeline_version=cfg["pipeline_version"],
    )


def scan_books(input_dir: Path, output_root: Path, cfg: dict[str, Any]) -> list[BookRecord]:
    pattern = f"**/*{cfg['pdf_suffix']}" if bool(cfg["runtime"]["recursive"]) else f"*{cfg['pdf_suffix']}"
    books: list[BookRecord] = []
    for pdf_path in sorted(input_dir.glob(pattern)):
        if not pdf_path.is_file():
            continue
        books.append(build_book_record(pdf_path=pdf_path, output_root=output_root, cfg=cfg))
    return books


def scan_input_books(input_books: list[dict[str, str]], output_root: Path, cfg: dict[str, Any]) -> list[BookRecord]:
    books: list[BookRecord] = []
    for item in input_books:
        raw_path = item.get("path") or item.get("source_pdf") or item.get("address") or item.get("url")
        if not raw_path:
            raise ValueError(f"Missing book path in input book item: {item}")
        books.append(
            build_book_record(
                pdf_path=Path(raw_path),
                output_root=output_root,
                cfg=cfg,
                book_name=item.get("book_name") or item.get("name"),
                book_id=item.get("book_id"),
            )
        )
    return books
