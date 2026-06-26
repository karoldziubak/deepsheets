#!/usr/bin/env python3
"""
Given session state, decide the next action for the reading session.

Usage:
    uv run scripts/decide.py
    uv run scripts/decide.py --state state/session_state.json

Output: JSON with recommended action.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STATE_FILE = Path("state/session_state.json")


def decide(state: dict) -> dict:
    themes = state.get("themes", [])
    quiz_count = state.get("quiz_questions_generated", 0)

    gap_themes = [t for t in themes if t.get("covered") and not t.get("user_understands")]
    if gap_themes:
        return {
            "action": "ask_followup",
            "theme": gap_themes[0]["name"],
            "reason": f"user has a gap on '{gap_themes[0]['name']}': {gap_themes[0].get('gap', 'unknown')}",
        }

    uncovered = [t for t in themes if not t.get("covered")]
    if uncovered:
        return {
            "action": "next_theme",
            "theme": uncovered[0]["name"],
            "reason": f"theme '{uncovered[0]['name']}' not yet discussed",
        }

    if quiz_count >= 5:
        return {
            "action": "suggest_quiz",
            "theme": None,
            "reason": f"all themes covered, {quiz_count} quiz questions ready",
        }

    if quiz_count < 3:
        return {
            "action": "exploratory",
            "theme": None,
            "reason": "all themes covered but only few quiz questions – explore deeper",
        }

    return {"action": "nothing", "theme": None, "reason": "all themes covered, quiz pool growing"}


def main():
    parser = argparse.ArgumentParser(description="Decide next action based on session state.")
    parser.add_argument("--state", type=Path, default=STATE_FILE, help="Path to session_state.json")
    args = parser.parse_args()

    if not args.state.exists():
        print(json.dumps({"action": "exploratory", "theme": None, "reason": "no state file yet – start exploring"}))
        return

    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        decision = decide(state)
        print(json.dumps(decision, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
