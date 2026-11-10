"""Work items: one folder per job posting under inbox/, turned into a review under applications/.

    inbox/<id>/posting.txt      the job posting text            (written by `fetch` / `add`)
    inbox/<id>/meta.json        where it came from              (written by `fetch` / `add`)
    inbox/<id>/analysis.json    Steps 1-4                       (written by Claude)
    inbox/<id>/tailoring.json   Step 5, only if score >= 65%    (written by Claude)

`build` validates, scores, runs the integrity checks and renders the final files.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import ROOT
from .config import Config
from .guard import check_draft
from .naming import base_name
from .profile import Profile
from .render_kit import render_kit
from .render_pdf import render_resume_pdf
from .render_report import render_report
from .resume import build_resume
from .schemas import analysis_schema, tailoring_schema, validate
from .scoring import band, weighted_score

INBOX = ROOT / "inbox"


# ------------------------------------------------------------------ inbox
def new_item(posting: str, source: str, meta: dict | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    hint = re.sub(r"[^a-z0-9]+", "-", (meta or {}).get("subject", "")[:40].lower()).strip("-")
    item_id = f"{stamp}-{hint}" if hint else stamp
    folder = INBOX / item_id
    i = 2
    while folder.exists():
        folder = INBOX / f"{item_id}-{i}"
        i += 1
    folder.mkdir(parents=True)
    (folder / "posting.txt").write_text(posting, encoding="utf-8")
    (folder / "meta.json").write_text(json.dumps(
        {"source": source, "created": datetime.now().isoformat(timespec="seconds"), "item_id": folder.name,
         **(meta or {})},
        indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


def list_items() -> list[Path]:
    if not INBOX.exists():
        return []
    return sorted(p for p in INBOX.iterdir() if (p / "posting.txt").exists())


def queued_gmail_uids() -> set[str]:
    uids = set()
    for item in list_items():
        meta = json.loads((item / "meta.json").read_text(encoding="utf-8"))
        if meta.get("gmail_uid"):
            uids.add(str(meta["gmail_uid"]))
    return uids


# ------------------------------------------------------------------ build
@dataclass
class Outcome:
    status: str                      # needs_analysis | invalid_analysis | needs_tailoring |
                                     # invalid_tailoring | integrity_issues | done
    score: float | None = None
    band: str = ""
    messages: list[str] = field(default_factory=list)
    folder: Path | None = None
    files: list[Path] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    title: str = ""
    company: str = ""
    decision: str = ""
    tailored: bool = False


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_folder(root: Path, name: str) -> Path:
    folder, i = root / name, 2
    while folder.exists():
        folder = root / f"{name}-{i}"
        i += 1
    folder.mkdir(parents=True)
    return folder


def build(item: Path, config: Config, profile: Profile, accept_issues: bool = False) -> Outcome:
    posting = (item / "posting.txt").read_text(encoding="utf-8")
    meta = _load(item / "meta.json") or {}

    analysis = _load(item / "analysis.json")
    if analysis is None:
        return Outcome("needs_analysis", meta=meta)
    errors = validate(analysis, analysis_schema())
    if errors:
        return Outcome("invalid_analysis", messages=errors, meta=meta)

    job = analysis["job"]
    score = weighted_score(analysis["scores"])
    label = band(score)
    evaluable = job.get("is_evaluable", True)
    if not evaluable:
        label = "Not evaluable"
    tailor = evaluable and score >= config.fit_threshold
    common = dict(score=score, band=label, meta=meta, title=job["title"], company=job["company"],
                  decision=analysis["recommendation"]["decision"], tailored=tailor)

    draft = resume = None
    issues: list[str] = []
    if tailor:
        draft = _load(item / "tailoring.json")
        if draft is None:
            return Outcome("needs_tailoring", **common)
        errors = validate(draft, tailoring_schema(profile))
        if errors:
            return Outcome("invalid_tailoring", messages=errors, **common)
        issues = check_draft(draft, profile.raw_text, posting, analysis)
        if issues and not accept_issues:
            return Outcome("integrity_issues", messages=issues, **common)
        resume = build_resume(profile, draft, config.max_bullets_per_role)

    # ---- render
    base = base_name(profile.full_name, job["title"], job["company"])
    folder = _unique_folder(config.output_dir, f"{datetime.now():%Y-%m-%d}_{base}")
    files: list[Path] = []
    report = folder / f"{base}_FitReport.md"
    report.write_text(render_report(
        analysis=analysis, score=score, band=label, threshold=config.fit_threshold, base=base,
        source=meta.get("source", "unknown"), resume=resume, draft=draft, issues=issues,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    ), encoding="utf-8")
    files.append(report)
    if resume is not None:
        pdf = folder / f"{base}.pdf"
        render_resume_pdf(resume, pdf, config.page_size)
        kit = folder / f"{base}_ApplicationKit.html"
        kit.write_text(render_kit(profile=profile, resume=resume, draft=draft, job=job, base=base),
                       encoding="utf-8")
        files += [pdf, kit]
    shutil.copy(item / "posting.txt", folder / "job_posting.txt")
    (folder / "analysis.json").write_text(json.dumps(
        {"meta": meta, "score": score, "band": label, "analysis": analysis,
         "tailoring": draft, "integrity_issues": issues}, indent=2, ensure_ascii=False), encoding="utf-8")

    return Outcome("done", messages=issues, folder=folder, files=files, **common)


def remove_item(item: Path) -> None:
    shutil.rmtree(item, ignore_errors=True)
