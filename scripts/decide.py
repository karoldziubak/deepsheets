#!/usr/bin/env python3
"""
Given session state, decide the next action for the reading session.

Usage:
    uv run scripts/decide.py --book overthinking_book
    uv run scripts/decide.py                # scans all data/*/

Output: JSON with recommended action.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path("data")


def decide(state: dict) -> dict:
    themes = state.get("themes", [])
    quiz_count = state.get("quiz_questions_generated", 0)

    gap_themes = [t for t in themes if t.get("covered") and not t.get("user_understands")]
    if gap_themes:
        return {
            "action": "ask_followup",
            "theme": gap_themes[0]["name"],
            "reason": f"gap: '{gap_themes[0].get('gap', 'unknown')}'",
        }

    uncovered = [t for t in themes if not t.get("covered")]
    if uncovered:
        return {
            "action": "next_theme",
            "theme": uncovered[0]["name"],
            "reason": f"not yet discussed",
        }

    if quiz_count >= 5:
        return {"action": "suggest_quiz", "reason": f"{quiz_count} questions ready"}
    if quiz_count < 3:
        return {"action": "exploratory", "reason": "few quiz questions"}
    return {"action": "nothing", "reason": "all covered"}


def main():
    parser = argparse.ArgumentParser(description="Decide next action based on session state.")
    parser.add_argument("--book", type=str, default=None, help="Book slug")
    args = parser.parse_args()

    books = [args.book] if args.book else [
        d.name for d in DATA_DIR.iterdir() if d.is_dir()
    ]
    results = {}
    for book in books:
        state_file = DATA_DIR / book / "session_state.json"
        if not state_file.exists():
            results[book] = {"action": "no_state", "reason": "no session_state.json yet"}
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            results[book] = decide(state)
        except Exception as e:
            results[book] = {"error": str(e)}

    if len(results) == 1:
        print(json.dumps(list(results.values())[0], indent=2, ensure_ascii=False))
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
