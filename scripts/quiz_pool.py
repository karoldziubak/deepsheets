#!/usr/bin/env python3
"""
Quiz pool management: add, list, generate, and score quiz questions.

Usage:
    uv run scripts/quiz_pool.py list --chapter 3
    uv run scripts/quiz_pool.py add --chapter 3 --question "..." --correct "..." --wrong "A" "B" "C" --source-quote "..."
    uv run scripts/quiz_pool.py generate --chapter 3 --count 5
    uv run scripts/quiz_pool.py score --question-id 7 --user-answer "..."
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path


QUIZ_FILE = Path("state/quiz_pool.json")
STATE_FILE = Path("state/session_state.json")


def load_quiz_pool() -> list[dict]:
    if QUIZ_FILE.exists():
        return json.loads(QUIZ_FILE.read_text(encoding="utf-8"))
    return []


def save_quiz_pool(pool: list[dict]) -> None:
    QUIZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUIZ_FILE.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")


def update_quiz_count() -> None:
    pool = load_quiz_pool()
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        state["quiz_questions_generated"] = len(pool)
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_list(chapter: int) -> None:
    pool = load_quiz_pool()
    chapter_qs = [q for q in pool if q.get("chapter") == chapter]
    if not chapter_qs:
        print(f"No quiz questions for chapter {chapter}.")
        return
    print(f"Quiz pool for chapter {chapter} ({len(chapter_qs)} questions):\n")
    for q in chapter_qs:
        status = "✓" if q.get("answered_correctly") is True else ("✗" if q.get("answered_correctly") is False else "•")
        print(f"  [{status}] ID {q['id']}: {q['question'][:100]}...")
        if q.get("source_quote"):
            print(f"       📖 {q['source_quote'][:120]}...")


def cmd_add(chapter: int, question: str, correct: str, wrong: list[str], source_quote: str = "") -> None:
    pool = load_quiz_pool()
    new_id = max((q.get("id", 0) for q in pool), default=0) + 1

    entry = {
        "id": new_id,
        "chapter": chapter,
        "question": question,
        "correct_answer": correct.strip().lower(),
        "distractors": [w.strip() for w in wrong],
        "source_quote": source_quote or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "answered_correctly": None,
        "user_answer": None,
    }
    pool.append(entry)
    save_quiz_pool(pool)
    update_quiz_count()
    print(f"✅ Added question ID {new_id} to chapter {chapter} pool.")


def cmd_generate(chapter: int, count: int) -> None:
    pool = load_quiz_pool()
    chapter_qs = [q for q in pool if q.get("chapter") == chapter]
    unanswered = [q for q in chapter_qs if q.get("answered_correctly") is None]
    answered = [q for q in chapter_qs if q.get("answered_correctly") is not None]
    wrong = [q for q in answered if q.get("answered_correctly") is False]

    candidates = unanswered + wrong
    if len(candidates) < count:
        correct_qs = [q for q in answered if q.get("answered_correctly") is True]
        candidates += correct_qs

    selected = random.sample(candidates, min(count, len(candidates)))

    print(f"📝 Quiz – Chapter {chapter} ({len(selected)} questions):\n")
    for i, q in enumerate(selected, 1):
        options = [q["correct_answer"]] + q.get("distractors", [])
        random.shuffle(options)
        labels = ["A", "B", "C", "D"][: len(options)]
        print(f"{i}. {q['question']}")
        for label, opt in zip(labels, options):
            print(f"   {label}) {opt}")
        if q.get("source_quote"):
            print(f"   📖 Źródło: {q['source_quote']}")
        print()

    print("--- JSON ---")
    print(json.dumps(selected, indent=2, ensure_ascii=False))


def cmd_score(question_id: int, user_answer: str) -> None:
    pool = load_quiz_pool()
    for q in pool:
        if q.get("id") == question_id:
            is_correct = user_answer.strip().lower() == q["correct_answer"].strip().lower()
            q["answered_correctly"] = is_correct
            q["user_answer"] = user_answer.strip()
            save_quiz_pool(pool)
            update_quiz_count()

            if is_correct:
                print(f"✅ Correct! (ID {question_id})")
            else:
                print(f"❌ Incorrect. Correct answer: {q['correct_answer']} (ID {question_id})")
            if q.get("source_quote"):
                print(f"   📖 Źródło: {q['source_quote']}")
            return

    print(f"ERROR: Question ID {question_id} not found.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Quiz pool management.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List quiz questions")
    p_list.add_argument("--chapter", type=int, required=True)

    p_add = sub.add_parser("add", help="Add a quiz question")
    p_add.add_argument("--chapter", type=int, required=True)
    p_add.add_argument("--question", required=True)
    p_add.add_argument("--correct", required=True)
    p_add.add_argument("--wrong", nargs=3, required=True, metavar="DISTRACTOR")
    p_add.add_argument("--source-quote", default="", help="Citation from the chapter")

    p_gen = sub.add_parser("generate", help="Generate a quiz")
    p_gen.add_argument("--chapter", type=int, required=True)
    p_gen.add_argument("--count", type=int, default=5)

    p_score = sub.add_parser("score", help="Score an answer")
    p_score.add_argument("--question-id", type=int, required=True)
    p_score.add_argument("--user-answer", required=True)

    args = parser.parse_args()

    try:
        if args.command == "list":
            cmd_list(args.chapter)
        elif args.command == "add":
            cmd_add(args.chapter, args.question, args.correct, args.wrong, getattr(args, "source_quote", ""))
        elif args.command == "generate":
            cmd_generate(args.chapter, args.count)
        elif args.command == "score":
            cmd_score(args.question_id, args.user_answer)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
