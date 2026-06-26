#!/usr/bin/env python3
"""
Initialize session state for a chapter — no API calls, local only.

Usage:
    uv run scripts/pre_analyze.py chapters/<book>/rozdzial_03.md
    uv run scripts/pre_analyze.py chapters/<book>/rozdzial_03.md --force

Creates state/session_state.json with chapter metadata and an empty
themes[] array. Copilot extracts and fills themes during conversation.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path("state")
STATE_FILE = STATE_DIR / "session_state.json"


def init_state(chapter_path: Path, force: bool = False) -> dict:
    if STATE_FILE.exists() and not force:
        existing = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if existing.get("themes"):
            print("[pre_analyze] Themes already exist. Use --force to reset.")
            return existing

    chapter_text = chapter_path.read_text(encoding="utf-8")
    print(f"[pre_analyze] Chapter: {chapter_path.name}")
    print(f"[pre_analyze] Size: {len(chapter_text):,} chars")
    print("[pre_analyze] Themes will be extracted by Copilot during session.")

    state = {
        "book": chapter_path.parent.name,
        "chapter_name": chapter_path.stem,
        "chapter_file": str(chapter_path),
        "themes": [],
        "quiz_questions_generated": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[pre_analyze] Template saved -> {STATE_FILE}")
    return state


def main():
    parser = argparse.ArgumentParser(
        description="Initialize session state for a chapter."
    )
    parser.add_argument("chapter", type=Path, help="Path to chapter .md file")
    parser.add_argument("--force", action="store_true", help="Reset even if cached")
    args = parser.parse_args()

    if not args.chapter.exists():
        print(f"ERROR: File not found: {args.chapter}")
        sys.exit(1)

    try:
        state = init_state(args.chapter, force=args.force)
        theme_count = len(state.get("themes", []))
        if theme_count:
            print(f"\n{theme_count} existing themes:")
            for i, t in enumerate(state["themes"], 1):
                print(f"  {i}. {t['name']}")
        else:
            print("\nNo themes yet - Copilot fills them during session.")
    except Exception as e:
        print(f"\nFailed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
