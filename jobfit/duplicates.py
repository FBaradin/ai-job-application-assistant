"""Spot job postings that were already reviewed, are already queued, or appear twice in one batch.

Two postings are treated as the same job when either
  * they point to the same job page (same URL once tracking/language parameters are removed), or
  * their text is at least SIMILARITY alike (word 5-gram Jaccard similarity).

Containment ("one text is inside the other") is deliberately not used: two careers pages that
failed to load share all their menu text, and different jobs from one company share the same
"About us" and benefits blocks. Measured on real postings, different jobs score below 0.5 and
re-sent copies of the same job score near 1.0.

Reviews marked "Not evaluable" are ignored: the posting text never loaded, so a new copy of
that job deserves a real review.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SIMILARITY = 0.80
MIN_SHINGLES = 5          # texts shorter than this are not compared on wording
_SHINGLE = 5
_IGNORED_PARAMS = re.compile(r"^(utm_.*|lang|locale|hl|ref|refid|trk|trackingid|source|src|gh_src|lipi|from|"
                             r"refer(r)?er|origin|campaign|mc_.*|fbclid|gclid)$", re.I)
_FETCHED = re.compile(r"^--- Content fetched from (\S+) ---$", re.M)


@dataclass
class Known:
    where: str            # shown to the user, e.g. "applications/2026-11-09_DataEngineerII_BostonScientific"
    detail: str           # e.g. "reviewed 2026-11-09: 50% Weak fit" or "waiting in the inbox"
    url: str
    words: frozenset


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    if not parts.netloc:
        return ""
    host = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parts.path)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not _IGNORED_PARAMS.match(k)))
    return urlunsplit(("https", host, path, query, ""))


def job_url(meta: dict, posting: str) -> str:
    """The job page the posting came from: an `add`ed URL, or the page `fetch` followed from the email."""
    candidates = []
    fetched_from = str(meta.get("fetched_from", ""))
    if fetched_from.startswith("email + "):
        candidates.append(fetched_from[len("email + "):])
    source = str(meta.get("source", ""))
    if source.startswith(("http://", "https://")):
        candidates.append(source)
    candidates += _FETCHED.findall(posting or "")
    for c in candidates:
        if norm := normalize_url(c):
            return norm
    return ""


def shingles(text: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return frozenset(" ".join(words[i:i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1))


def similarity(a: frozenset, b: frozenset) -> float:
    if len(a) < MIN_SHINGLES or len(b) < MIN_SHINGLES:
        return 0.0
    return len(a & b) / len(a | b)


def _rel(p: Path, root: Path | None) -> str:
    try:
        return p.relative_to(root).as_posix() if root else p.as_posix()
    except ValueError:
        return p.as_posix()


def _queued(item: Path, root: Path | None) -> Known:
    posting = (item / "posting.txt").read_text(encoding="utf-8")
    meta_file = item / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    return Known(_rel(item, root), "waiting in the inbox", job_url(meta, posting), shingles(posting))


def known_postings(output_dir: Path, inbox_items: list[Path], root: Path | None = None) -> list[Known]:
    """Every saved review (except "Not evaluable" ones) plus every job waiting in the inbox."""
    known: list[Known] = []
    for saved in sorted(output_dir.glob("*/analysis.json")):
        try:
            data = json.loads(saved.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("band") == "Not evaluable":
            continue
        posting_file = saved.parent / "job_posting.txt"
        posting = posting_file.read_text(encoding="utf-8") if posting_file.exists() else ""
        meta = data.get("meta", {}) or {}
        score = data.get("score")
        reviewed = saved.parent.name[:10] if re.match(r"\d{4}-\d{2}-\d{2}", saved.parent.name) else ""
        detail = f"reviewed {reviewed}".strip() + (f": {score:.0f}% {data.get('band', '')}" if score is not None else "")
        known.append(Known(_rel(saved.parent, root), detail, job_url(meta, posting), shingles(posting)))
    known += [_queued(item, root) for item in inbox_items]
    return known


def find_duplicate(posting: str, meta: dict, known: list[Known]) -> tuple[Known, str] | None:
    """Return (the matching posting, why) or None."""
    url = job_url(meta, posting)
    if url:
        for k in known:
            if k.url == url:
                return k, "same job link"
    words = shingles(posting)
    best, best_sim = None, 0.0
    for k in known:
        sim = similarity(words, k.words)
        if sim > best_sim:
            best, best_sim = k, sim
    if best is not None and best_sim >= SIMILARITY:
        return best, f"{best_sim:.0%} identical text"
    return None


def remember(known: list[Known], item: Path, root: Path | None = None) -> None:
    """Add a just-queued item so later postings in the same batch are compared with it."""
    known.append(_queued(item, root))


def describe(match: Known, why: str) -> str:
    return f"same posting as {match.where} ({match.detail}; {why})"
