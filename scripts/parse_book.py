#!/usr/bin/env python3
"""
Parse PDF/EPUB books into per-chapter Markdown files.

Usage:
    uv run scripts/parse_book.py path/to/book.pdf
    uv run scripts/parse_book.py path/to/book.epub
    uv run scripts/parse_book.py path/to/book.pdf --chapter 3
    uv run scripts/parse_book.py path/to/book.pdf --list-chapters

Fallback chain (PDF):
    1. LlamaParse API – cloud, ~$0.003/page, best layout parsing (default)
    2. PyMuPDF – fast local text extraction (text-based PDFs)
    3. HITL – manual chapter ranges (like YouTube timestamps)
    (Marker local ML available via --strategy marker)

Output: data/<book_slug>/chapters/rozdzial_01.md, rozdział_02.md, ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = Path("data")
MARKER_CMD = "marker"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[-\s]+", "_", name)
    return name[:80]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_pdf(filepath: Path) -> bool:
    return filepath.suffix.lower() == ".pdf"


def is_epub(filepath: Path) -> bool:
    return filepath.suffix.lower() == ".epub"


class LlamaParseKeyMissingError(RuntimeError):
    """Raised when no LlamaParse API key is configured."""


def _get_llama_api_key() -> str | None:
    """Return the LlamaParse API key from env/.env, or None if missing or still a placeholder."""
    from dotenv import load_dotenv

    load_dotenv()
    key = (os.getenv("LLAMA_PARSE_API_KEY", "") or os.getenv("LLAMA_CLOUD_API_KEY", "")).strip()
    if not key or key == "llx-your-key-here":
        return None
    return key


# ---------------------------------------------------------------------------
# Chapter splitting
# ---------------------------------------------------------------------------
_ACADEMIC_SECTION = re.compile(
    r"^\s*(?:\d+[\.\s]+)?(?:Abstract|Introduction|Related\s*Work|Background"
    r"|Method(?:ology)?|Experiments?|Results?|Discussion|Conclusion|Future\s*Work"
    r"|References|Appendix|Acknowledgments?|Supplementary\s*Material)(?:\s*\d*)\s*$",
    re.IGNORECASE,
)

_NUMBERED_SECTION = re.compile(r"^\s*\d+[\.\s]+\w{3,}")


def split_markdown_by_headings(md_text: str, book_slug: str) -> list[Path]:
    """Split text into chapters by Markdown headings, academic sections, or numbered sections."""
    lines = md_text.splitlines()
    chapters: list[tuple[str, list[str]]] = []
    current_title = "frontmatter"
    current_lines: list[str] = []

    def _is_heading(line: str) -> bool:
        if line.startswith("# ") or line.startswith("## "):
            return True
        return bool(_ACADEMIC_SECTION.match(line))

    for line in lines:
        if _is_heading(line):
            if current_lines:
                chapters.append((current_title, current_lines))
            current_title = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chapters.append((current_title, current_lines))

    # If only frontmatter found (no headings), retry with numbered sections
    if len(chapters) <= 1:
        chapters = []
        current_title = "frontmatter"
        current_lines = []
        for line in lines:
            if _NUMBERED_SECTION.match(line) and not _ACADEMIC_SECTION.match(line):
                if current_lines:
                    chapters.append((current_title, current_lines))
                current_title = line.strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            chapters.append((current_title, current_lines))

    # Merge tiny chapters (just a heading, no real content) into the previous one
    merged: list[tuple[str, list[str]]] = []
    for title, ch_lines in chapters:
        body = [l for l in ch_lines if not _is_heading(l)]
        body_text = "\n".join(body).strip()
        if len(body_text) < 200 and merged:
            merged[-1][1].extend(ch_lines)
        else:
            merged.append((title, ch_lines))
    chapters = merged

    # Still no split — single chapter
    if len(chapters) <= 1 and not any(t != "frontmatter" for t, _ in chapters):
        return [_write_chapter("rozdzial_01", md_text, book_slug)]

    output_dir = ensure_dir(DATA_DIR / book_slug / "chapters")
    files: list[Path] = []
    for i, (title, chapter_lines) in enumerate(chapters, start=1):
        chapter_text = "\n".join(chapter_lines).strip()
        if not chapter_text:
            continue
        fname = f"rozdzial_{i:02d}"
        files.append(_write_chapter(fname, chapter_text, book_slug))

    return files


def _write_chapter(name: str, text: str, book_slug: str) -> Path:
    output_dir = ensure_dir(DATA_DIR / book_slug / "chapters")
    out = output_dir / f"{name}.md"
    out.write_text(text, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------
def parse_pdf_marker(pdf_path: Path, book_slug: str) -> list[Path]:
    """Parse PDF using Marker (local ML) via marker_single CLI."""
    import shutil

    output_dir = DATA_DIR / book_slug / "chapters"
    ensure_dir(output_dir)

    # marker-pdf >=1.0 uses `marker_single` CLI, not `python -m marker`
    marker_exe = shutil.which("marker_single")
    if marker_exe is None:
        marker_exe = str(Path(sys.executable).parent / "marker_single")
        if sys.platform == "win32":
            marker_exe += ".exe"

    cmd = [
        marker_exe,
        str(pdf_path),
        "--output_format", "markdown",
        "--output_dir", str(output_dir / "_marker_output"),
    ]
    print(f"[marker] Running: {' '.join(cmd)}")
    print("[marker] ⏳ Processing PDF — this may take a few minutes for large files...")
    import time
    start = time.time()

    # Stream output in real-time so the user sees progress
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    last_line_time = start
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"  {line}")
            last_line_time = time.time()
        elif time.time() - last_line_time > 15:
            print("  .", end="", flush=True)
            last_line_time = time.time()
    proc.wait()
    elapsed = time.time() - start
    print(f"\n[marker] ✅ Done in {elapsed:.0f}s")

    if proc.returncode != 0:
        raise RuntimeError(f"Marker failed with code {proc.returncode}")

    marker_out = output_dir / "_marker_output"
    md_files = sorted(marker_out.rglob("*.md"))
    if not md_files:
        raise RuntimeError(f"Marker produced no .md files in {marker_out}")

    full_text = "\n\n".join(f.read_text(encoding="utf-8") for f in md_files)
    return split_markdown_by_headings(full_text, book_slug)


def parse_pdf_llama(pdf_path: Path, book_slug: str) -> list[Path]:
    """Parse PDF using LlamaParse (LlamaCloud unified SDK). Caches raw output locally."""
    from llama_cloud import APIConnectionError, AuthenticationError, LlamaCloud

    cache_file = DATA_DIR / book_slug / "_llama_raw.md"

    # Reuse cached raw output if available (no API call)
    if cache_file.exists():
        print(f"[llamaparse] Using cached output: {cache_file}")
        full_text = cache_file.read_text(encoding="utf-8")
        return split_markdown_by_headings(full_text, book_slug)

    api_key = _get_llama_api_key()
    if api_key is None:
        raise LlamaParseKeyMissingError(
            "LLAMA_PARSE_API_KEY not set — add it to .env (see .env.example); "
            "get a key at https://cloud.llamaindex.ai"
        )

    try:
        client = LlamaCloud(api_key=api_key)
        print(f"[llamaparse] Uploading {pdf_path.name}...")
        uploaded = client.files.create(file=str(pdf_path), purpose="parse")

        tier = os.getenv("LLAMA_PARSE_TIER", "cost_effective")
        print(f"[llamaparse] Parsing with tier='{tier}' (this may take a minute)...")
        result = client.parsing.parse(
            file_id=uploaded.id,
            tier=tier,  # type: ignore[arg-type]
            version="latest",
            expand=["markdown"],
        )
    except AuthenticationError as e:
        raise RuntimeError(
            "LlamaParse rejected the API key (401 Unauthorized). "
            "Check LLAMA_PARSE_API_KEY in .env — get a valid key at https://cloud.llamaindex.ai"
        ) from e
    except APIConnectionError as e:
        raise RuntimeError(
            "Could not reach the LlamaCloud API (network problem?). "
            "Check your internet connection and try again."
        ) from e

    markdown = result.markdown
    if markdown is None or not markdown.pages:
        raise RuntimeError("LlamaParse returned no markdown output")
    full_text = "\n\n".join(page.markdown for page in markdown.pages if page.markdown)

    # Cache raw output so we can re-split without paying again
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(full_text, encoding="utf-8")
    print(f"[llamaparse] Raw output cached: {cache_file}")

    return split_markdown_by_headings(full_text, book_slug)


def parse_pdf_hitl(pdf_path: Path, book_slug: str) -> list[Path]:
    import fitz

    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    print(f"\n[hitl] PDF has {total_pages} pages.")
    print("[hitl] Define chapters as page ranges:")
    print("        Format: '1-12, 13-28, 29-45'")
    print("        Or press Enter to treat the whole book as one chapter.\n")

    raw = input("  Page ranges → ").strip()

    if not raw:
        full_text = "\n\n".join(doc[i].get_text() for i in range(total_pages))
        doc.close()
        return [_write_chapter("rozdzial_01", full_text, book_slug)]

    ranges = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ranges.append((int(a.strip()) - 1, int(b.strip())))
        else:
            p = int(part)
            ranges.append((p - 1, p))

    doc.close()
    chapters: list[Path] = []
    for i, (start, end) in enumerate(ranges, start=1):
        text = "\n\n".join(doc[j].get_text() for j in range(start, min(end, total_pages)))
        if text.strip():
            chapters.append(_write_chapter(f"rozdzial_{i:02d}", text, book_slug))

    return chapters


def parse_pdf_pymupdf(pdf_path: Path, book_slug: str) -> list[Path]:
    """Fast PDF text extraction via PyMuPDF. Works for text-based PDFs."""
    import fitz

    doc = fitz.open(str(pdf_path))
    pages = doc.page_count
    full_text = "\n\n".join(doc[i].get_text() for i in range(pages))
    doc.close()

    if len(full_text.strip()) < 100:
        raise RuntimeError(f"PyMuPDF extracted only {len(full_text)} chars — likely a scanned PDF")
    print(f"[pymupdf] Extracted {len(full_text):,} chars from {pages} pages in ~1s")
    return split_markdown_by_headings(full_text, book_slug)


def parse_pdf(pdf_path: Path, book_slug: str, strategy: str = "auto") -> list[Path]:
    """Parse PDF with selected strategy.

    Args:
        strategy: "auto" (smart fallback), "pymupdf", "marker", "llama", "hitl"
    """
    # --- Forced parser ---
    if strategy == "pymupdf":
        return parse_pdf_pymupdf(pdf_path, book_slug)
    if strategy == "marker":
        return parse_pdf_marker(pdf_path, book_slug)
    if strategy == "llama":
        return parse_pdf_llama(pdf_path, book_slug)
    if strategy == "hitl":
        return parse_pdf_hitl(pdf_path, book_slug)

    # --- Auto: smart fallback chain ---
    # Chain 1: LlamaParse (cloud API, best layout parsing)
    try:
        print("[parse] Trying LlamaParse (cloud API)...")
        return parse_pdf_llama(pdf_path, book_slug)
    except LlamaParseKeyMissingError as e:
        print(f"[parse] LlamaParse skipped: {e}")
    except Exception as e:
        print(f"[parse] LlamaParse failed: {e}")

    # Chain 2: PyMuPDF (instant for text PDFs, fails for scans)
    try:
        print("[parse] Trying PyMuPDF (fast)...")
        return parse_pdf_pymupdf(pdf_path, book_slug)
    except Exception as e:
        print(f"[parse] PyMuPDF failed: {e}")

    # Chain 3: HITL
    print("[parse] Falling back to HITL (manual page ranges).")
    return parse_pdf_hitl(pdf_path, book_slug)


# ---------------------------------------------------------------------------
# EPUB parsing
# ---------------------------------------------------------------------------
def parse_epub(epub_path: Path, book_slug: str) -> list[Path]:
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(str(epub_path))
    chapters: list[Path] = []
    seen_files: set[str] = set()
    chapter_num = 0

    def _flatten_toc(items: list) -> list[epub.Link]:
        links: list[epub.Link] = []
        for item in items:
            if isinstance(item, tuple):
                section, children = item
                if isinstance(section, epub.Link):
                    links.append(section)
                links.extend(_flatten_toc(children))
            elif isinstance(item, epub.Link):
                links.append(item)
        return links

    all_links = _flatten_toc(book.toc)

    if all_links:
        for link in all_links:
            base_file = link.href.split("#")[0]
            if base_file in seen_files:
                continue
            seen_files.add(base_file)

            doc = book.get_item_with_href(link.href)
            if doc:
                soup = BeautifulSoup(doc.get_content(), "html.parser")
                text = soup.get_text("\n", strip=True)
                if text.strip():
                    chapter_num += 1
                    fname = f"rozdzial_{chapter_num:02d}"
                    chapters.append(_write_chapter(fname, text, book_slug))

    if not chapters:
        for item in book.get_items():
            if item.get_type() == 9:
                chapter_num += 1
                soup = BeautifulSoup(item.get_content(), "html.parser")
                text = soup.get_text("\n", strip=True)
                if text.strip():
                    fname = f"rozdzial_{chapter_num:02d}"
                    chapters.append(_write_chapter(fname, text, book_slug))

    if not chapters:
        raise RuntimeError("No chapters extracted from EPUB. The file may be DRM-protected.")

    return chapters


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Parse PDF/EPUB books into per-chapter Markdown.")
    parser.add_argument("file", type=Path, help="Path to PDF or EPUB file")
    parser.add_argument("--chapter", type=int, default=None, help="Parse only a specific chapter number")
    parser.add_argument("--list-chapters", action="store_true", help="List existing chapter files for this book")
    parser.add_argument(
        "--strategy",
        choices=["auto", "pymupdf", "marker", "llama", "hitl"],
        default="auto",
        help="PDF parsing strategy (default: auto = LlamaParse → PyMuPDF → HITL)",
    )
    args = parser.parse_args()

    book_path = args.file.resolve()
    if not book_path.exists():
        print(f"ERROR: File not found: {book_path}")
        sys.exit(1)

    book_slug = slugify(book_path.stem)

    if args.list_chapters:
        ch_dir = DATA_DIR / book_slug / "chapters"
        if ch_dir.exists():
            for f in sorted(ch_dir.glob("*.md")):
                print(f"  {f.name}")
        else:
            print(f"  No chapters found for '{book_slug}'.")
        return

    # Early validation: PDFs use LlamaParse (needs an API key unless raw output is cached)
    if is_pdf(book_path) and args.strategy in ("auto", "llama"):
        llama_cache = DATA_DIR / book_slug / "_llama_raw.md"
        if not llama_cache.exists() and _get_llama_api_key() is None:
            if args.strategy == "llama":
                print("\n❌ LlamaParse API key is missing — cannot run --strategy llama.\n")
                print("   How to fix:")
                print("     1. Get a key at https://cloud.llamaindex.ai")
                print("     2. Copy .env.example to .env and set:")
                print("        LLAMA_PARSE_API_KEY=llx-...")
                sys.exit(1)
            print(
                "⚠️  LLAMA_PARSE_API_KEY not set — skipping LlamaParse, "
                "falling back to local parsers (PyMuPDF).\n"
                "   To enable cloud parsing: copy .env.example to .env and set LLAMA_PARSE_API_KEY."
            )

    print(f"📖 Parsing: {book_path.name}")
    print(f"   Output:  {DATA_DIR / book_slug / 'chapters'}/\n")

    try:
        if is_pdf(book_path):
            chapter_files = parse_pdf(book_path, book_slug, strategy=args.strategy)
        elif is_epub(book_path):
            chapter_files = parse_epub(book_path, book_slug)
        else:
            print(f"ERROR: Unsupported format: {book_path.suffix}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Parsing failed: {e}")
        sys.exit(1)

    if args.chapter is not None:
        idx = args.chapter - 1
        if 0 <= idx < len(chapter_files):
            chapter_files = [chapter_files[idx]]
        else:
            print(f"ERROR: Chapter {args.chapter} not found (only {len(chapter_files)} chapters).")
            sys.exit(1)

    print(f"\n✅ Done! {len(chapter_files)} chapter(s) written:")
    for f in chapter_files:
        size_kb = f.stat().st_size / 1024
        print(f"   {f} ({size_kb:.1f} KB)")

    meta = {
        "book": book_path.stem,
        "book_slug": book_slug,
        "source_file": str(book_path),
        "format": "pdf" if is_pdf(book_path) else "epub",
        "chapters": [f.name for f in chapter_files],
        "chapter_count": len(chapter_files),
    }
    meta_path = DATA_DIR / book_slug / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   Meta:  {meta_path}")


if __name__ == "__main__":
    main()
