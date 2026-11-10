"""Deterministic integrity checks on a tailored resume draft.

The model is instructed not to fabricate; these checks verify it:
  1. Every number in the draft must exist in the master profile.
  2. No tool/technology named in the job posting may appear in the draft
     unless the master profile also mentions it.
  3. No long phrase (8+ words) may be copied from the job posting.
Skills, employers, titles, dates, degrees and certifications cannot be
fabricated at all: they are enum-locked or copied from the profile in code.
"""
from __future__ import annotations

import re

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD_RE = re.compile(r"[a-z0-9+#]+")
SHINGLE = 8


def _draft_texts(draft: dict) -> list[str]:
    texts = [draft.get("summary", "")]
    for e in draft.get("experience", []):
        texts += e.get("bullets", [])
    for p in draft.get("projects", []) or []:
        texts += p.get("bullets", [])
    for a in draft.get("application_answers", []):
        texts.append(a.get("answer", ""))
    return [t for t in texts if t]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(text)}


def _contains_term(haystack_lower: str, term: str) -> bool:
    t = term.lower().strip()
    if not t:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", haystack_lower) is not None


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = WORD_RE.findall(text.lower())
    return {tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def check_draft(draft: dict, master_text: str, job_text: str, analysis: dict) -> list[str]:
    issues: list[str] = []
    master_lower = master_text.lower()
    master_numbers = _numbers(master_text)
    texts = _draft_texts(draft)
    draft_lower = "\n".join(texts).lower()

    # 1. numbers
    for text in texts:
        for n in sorted(_numbers(text) - master_numbers):
            issues.append(f'Number "{n}" does not appear in the master profile: "{text[:120]}"')

    # 2. tools from the posting that the profile doesn't have
    tools = analysis.get("jd_analysis", {}).get("tools_technologies", [])
    for tool in tools:
        if len(tool.split()) > 4:
            continue
        if _contains_term(draft_lower, tool) and not _contains_term(master_lower, tool):
            issues.append(f'Tool/technology "{tool}" is used in the draft but is not in the master profile')

    # 3. copied phrasing
    jd_shingles = _shingles(job_text)
    for text in texts:
        copied = _shingles(text) & jd_shingles
        if copied:
            phrase = " ".join(sorted(copied)[0])
            issues.append(f'Phrase copied from the job posting ("{phrase}..."): "{text[:120]}"')

    # de-duplicate, keep order
    return list(dict.fromkeys(issues))
