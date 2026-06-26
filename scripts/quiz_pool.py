#!/usr/bin/env python3
"""
Per-book quiz pool management.

Usage:
    uv run scripts/quiz_pool.py list --book mybook --chapter 1
    uv run scripts/quiz_pool.py add --book mybook --chapter 1 --question "..." --correct "X" --wrong "A" "B" "C" --source-quote "..."
    uv run scripts/quiz_pool.py generate --book mybook --chapter 1 --count 5
    uv run scripts/quiz_pool.py score --book mybook --question-id 7 --user-answer "X"
"""
from __future__ import annotations

import argparse, json, random, sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("data")

def _qf(b): return DATA_DIR / b / "quiz_pool.json"
def _sf(b): return DATA_DIR / b / "session_state.json"

def load_pool(book): qf=_qf(book); return json.loads(qf.read_text(encoding="utf-8")) if qf.exists() else []
def save_pool(book,pool): qf=_qf(book); qf.parent.mkdir(parents=True,exist_ok=True); qf.write_text(json.dumps(pool,indent=2,ensure_ascii=False),encoding="utf-8")
def sync_count(book):
    pool=load_pool(book); sf=_sf(book)
    if sf.exists():
        s=json.loads(sf.read_text(encoding="utf-8")); s["quiz_questions_generated"]=len(pool); s["last_updated"]=datetime.now(timezone.utc).isoformat()
        sf.write_text(json.dumps(s,indent=2,ensure_ascii=False),encoding="utf-8")

def cmd_list(book,chapter):
    pool=load_pool(book); qs=[q for q in pool if q.get("chapter")==chapter]
    if not qs: print(f"No questions for {book} ch.{chapter}."); return
    print(f"Quiz: {book} ch.{chapter} ({len(qs)} Qs):\n")
    for q in qs:
        st="✓" if q.get("answered_correctly") is True else ("✗" if q.get("answered_correctly") is False else "•")
        print(f"  [{st}] ID {q['id']}: {q['question'][:100]}...")
        if q.get("source_quote"): print(f"       📖 {q['source_quote'][:120]}...")

def cmd_add(book,chapter,question,correct,wrong,source_quote=""):
    pool=load_pool(book); nid=max((q.get("id",0) for q in pool),default=0)+1
    pool.append({"id":nid,"chapter":chapter,"question":question,"correct_answer":correct.strip().lower(),"distractors":[w.strip() for w in wrong],"source_quote":source_quote or None,"created_at":datetime.now(timezone.utc).isoformat(),"answered_correctly":None,"user_answer":None})
    save_pool(book,pool); sync_count(book)
    print(f"✅ Added Q#{nid} to {book} ch.{chapter}.")

def cmd_generate(book,chapter,count):
    pool=load_pool(book); qs=[q for q in pool if q.get("chapter")==chapter]
    un=[q for q in qs if q.get("answered_correctly") is None]; wr=[q for q in qs if q.get("answered_correctly") is False]; ok=[q for q in qs if q.get("answered_correctly") is True]
    candidates=un+wr
    if len(candidates)<count: candidates+=ok
    sel=random.sample(candidates,min(count,len(candidates)))
    print(f"📝 Quiz – {book} ch.{chapter} ({len(sel)} Qs):\n")
    for i,q in enumerate(sel,1):
        opts=[q["correct_answer"]]+q.get("distractors",[]); random.shuffle(opts)
        print(f"{i}. {q['question']}")
        for l,o in zip("ABCD",opts): print(f"   {l}) {o}")
        if q.get("source_quote"): print(f"   📖 Źródło: {q['source_quote']}")
        print()
    print("--- JSON ---"); print(json.dumps(sel,indent=2,ensure_ascii=False))

def cmd_score(book,question_id,user_answer):
    pool=load_pool(book)
    for q in pool:
        if q.get("id")==question_id:
            ok=user_answer.strip().lower()==q["correct_answer"].strip().lower()
            q["answered_correctly"]=ok; q["user_answer"]=user_answer.strip()
            save_pool(book,pool); sync_count(book)
            print(f"{'✅' if ok else '❌'} {'Correct' if ok else 'Incorrect'}. Answer: {q['correct_answer']} (ID {question_id})")
            if q.get("source_quote"): print(f"   📖 Źródło: {q['source_quote']}")
            return
    print(f"ERROR: Q#{question_id} not found.")

def main():
    p=argparse.ArgumentParser(description="Per-book quiz pool management.")
    s=p.add_subparsers(dest="cmd",required=True)
    pl=s.add_parser("list"); pl.add_argument("--book",required=True); pl.add_argument("--chapter",type=int,required=True)
    pa=s.add_parser("add"); pa.add_argument("--book",required=True); pa.add_argument("--chapter",type=int,required=True); pa.add_argument("--question",required=True); pa.add_argument("--correct",required=True); pa.add_argument("--wrong",nargs=3,required=True,metavar="D"); pa.add_argument("--source-quote",default="")
    pg=s.add_parser("generate"); pg.add_argument("--book",required=True); pg.add_argument("--chapter",type=int,required=True); pg.add_argument("--count",type=int,default=5)
    ps=s.add_parser("score"); ps.add_argument("--book",required=True); ps.add_argument("--question-id",type=int,required=True); ps.add_argument("--user-answer",required=True)
    a=p.parse_args()
    try:
        if a.cmd=="list": cmd_list(a.book,a.chapter)
        elif a.cmd=="add": cmd_add(a.book,a.chapter,a.question,a.correct,a.wrong,getattr(a,"source_quote",""))
        elif a.cmd=="generate": cmd_generate(a.book,a.chapter,a.count)
        elif a.cmd=="score": cmd_score(a.book,a.question_id,a.user_answer)
    except Exception as e: print(f"❌ {e}"); sys.exit(1)

if __name__=="__main__": main()
