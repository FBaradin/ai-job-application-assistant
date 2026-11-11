"""CLI used by the /review-jobs command (Claude Code does the analysis; this does the rest).

  python -m jobfit validate              check the master profile
  python -m jobfit fetch                 pull new emails from the Gmail label into inbox/
  python -m jobfit add posting.txt       queue a posting saved as a text file
  python -m jobfit add https://...       queue a posting from a public web page
                                         (fetch and add skip postings that were already reviewed or
                                          queued; add --force to queue one anyway)
  python -m jobfit list                  show queued postings and what each one still needs
  python -m jobfit schema analysis|tailoring   print the JSON schema Claude must follow
  python -m jobfit build inbox/<id>      validate, score, check and render the review
  python -m jobfit tracker setup         create/format the Google Sheets job tracker
  python -m jobfit tracker sync          add every saved review and queued job to the tracker
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config, load_env
from .profile import Profile, ProfileError


def _summary(o) -> str:
    lines = [
        f"{o.title} — {o.company}",
        f"Job fit score: {o.score:.0f}% ({o.band})",
        f"Recommendation: {o.decision}",
        "Tailored resume and application kit attached." if o.tailored
        else "No resume generated. See the report for gaps and advice.",
    ]
    if o.messages:
        lines.append(f"REVIEW REQUIRED: {len(o.messages)} integrity item(s) flagged in the report.")
    lines.append(f"Folder: {o.folder.name}")
    return "\n".join(lines)


def _tracker(config: Config):
    """Open the Google Sheets tracker, or return None (with a one-line reason) if unavailable."""
    if not config.tracker_enabled:
        return None
    try:
        from .tracker import Tracker
        return Tracker()
    except Exception as e:  # noqa: BLE001 - the tracker must never block a review
        print(f"Tracker step skipped: {e}")
        return None


def _track_items(config: Config, items: list[Path]) -> None:
    if not items:
        return
    tr = _tracker(config)
    if tr is None:
        return
    from .tracker import track_inbox
    try:
        for item in items:
            track_inbox(tr, item)
        print(f"Tracker: {len(items)} job(s) added as Pending (awaiting review).")
    except Exception as e:  # noqa: BLE001
        print(f"Tracker step skipped: {e}")


def _known_postings(config: Config):
    from . import ROOT
    from .duplicates import known_postings
    from .pipeline import list_items
    return known_postings(config.output_dir, list_items(), ROOT)


def cmd_fetch(config: Config) -> int:
    from . import ROOT
    from .duplicates import describe, find_duplicate, remember
    from .gmail_client import Gmail
    from .job_text import email_to_postings
    from .pipeline import new_item, queued_gmail_uids

    queued, duplicates = [], 0
    known = _known_postings(config)
    with Gmail() as gm:
        messages = gm.unprocessed(config.source_label,
                                  [config.processed_label, config.error_label, config.duplicate_label],
                                  config.max_per_run, skip_uids=queued_gmail_uids())
        print(f"{len(messages)} new message(s) under '{config.source_label}'.")
        for m in messages:
            postings, unreadable = email_to_postings(m.subject, m.text, m.html)
            if len(postings) > 1:
                print(f"  email '{m.subject}' links to {len(postings)} job pages: each is queued separately.")
            for url in unreadable:
                print(f"  COULD NOT READ job link in email '{m.subject}': {url} "
                      f"(login wall or blocked; paste its text or save it to a file to review it).")
            new = 0
            for posting, source in postings:
                meta = {"gmail_uid": m.uid, "subject": m.subject, "date": m.date, "fetched_from": source}
                dup = find_duplicate(posting, meta, known)
                if dup:
                    duplicates += 1
                    what = source.removeprefix("email + ") if len(postings) > 1 else f"email '{m.subject}' ({m.date})"
                    print(f"  DUPLICATE, skipped: {what} is the {describe(*dup)}.")
                    continue
                item = new_item(posting, f"Gmail: {m.subject} ({m.date})", meta)
                remember(known, item, ROOT)
                queued.append(item)
                new += 1
                print(f"  queued {item.name}  ({len(posting)} chars, {source})")
            if not new:   # every job in this email was already reviewed or queued
                gm.add_label(m.uid, config.duplicate_label)
                print(f"  email '{m.subject}' labelled '{config.duplicate_label}' (nothing new in it).")
    if duplicates:
        print(f"Duplicates: {duplicates} posting(s) skipped, not queued for analysis.")
    _track_items(config, queued)
    return 0


def cmd_tracker(action: str, config: Config) -> int:
    tr = _tracker(config) if config.tracker_enabled else None
    if not config.tracker_enabled:
        print("Tracker is disabled in config.yaml (tracker.enabled).")
        return 2
    if tr is None:
        return 2
    if action == "setup":
        tr._ensure_layout(force=True)
        n = tr.refresh_formulas()
        print(f"Tracker layout applied ({n} row(s) refreshed): {tr.url}")
        return 0
    from .pipeline import list_items
    from .tracker import sync_all
    for line in sync_all(tr, config.output_dir, list_items()):
        print(f"  {line}")
    print(f"Tracker synced: {tr.url}")
    return 0


def cmd_add(target: str, config: Config, force: bool = False) -> int:
    from .duplicates import describe, find_duplicate
    from .job_text import fetch_url_text
    from .pipeline import new_item

    if target.startswith(("http://", "https://")):
        text = fetch_url_text(target)
        if not text:
            print("Could not fetch that page (login wall or blocked). Save the text to a file instead.",
                  file=sys.stderr)
            return 2
        source, meta = target, {"subject": target.split("/")[2]}
    else:
        path = Path(target)
        text, source, meta = path.read_text(encoding="utf-8"), f"file: {path.name}", {"subject": path.stem}
    dup = None if force else find_duplicate(text, {"source": source, **meta}, _known_postings(config))
    if dup:
        print(f"DUPLICATE, skipped: this is the {describe(*dup)}. Not queued "
              f"(use --force to review it again anyway).")
        return 0
    item = new_item(text, source, meta)
    print(f"queued {item}")
    _track_items(config, [item])
    return 0


def cmd_list(config: Config, profile: Profile) -> int:
    from .pipeline import list_items

    items = list_items()
    if not items:
        print("Inbox is empty.")
    for item in items:
        has_a = (item / "analysis.json").exists()
        has_t = (item / "tailoring.json").exists()
        print(f"{item.relative_to(item.parent.parent)}  analysis={'yes' if has_a else 'no'}  "
              f"tailoring={'yes' if has_t else 'no'}")
    return 0


def cmd_build(item: Path, config: Config, profile: Profile, accept_issues: bool) -> int:
    from .pipeline import build, remove_item

    item = item.resolve()
    o = build(item, config, profile, accept_issues=accept_issues)
    if o.score is not None:
        print(f"SCORE: {o.score:.1f}% ({o.band}) | threshold {config.fit_threshold}% | "
              f"tailor={'yes' if o.tailored else 'no'}")
    if o.status != "done":
        print(f"STATUS: {o.status}")
        for m in o.messages:
            print(f"  - {m}")
        hints = {
            "needs_analysis": "Write analysis.json (python -m jobfit schema analysis).",
            "invalid_analysis": "Fix analysis.json to match the schema.",
            "needs_tailoring": "Score is at/above threshold: write tailoring.json (python -m jobfit schema tailoring).",
            "invalid_tailoring": "Fix tailoring.json to match the schema (IDs and skills must come from the profile).",
            "integrity_issues": "Revise tailoring.json to resolve these, then build again "
                                "(after 2 revisions, use --accept-issues to list remaining items in the report).",
        }
        print(hints.get(o.status, ""))
        return 3

    print("STATUS: done")
    for f in o.files:
        print(f"  {f}")

    # Gmail bookkeeping + results email (best effort; the files are already saved)
    if o.meta.get("gmail_uid") or config.email_results:
        try:
            from .gmail_client import Gmail, send_results
            if o.meta.get("gmail_uid"):
                from .pipeline import queued_gmail_uids
                if str(o.meta["gmail_uid"]) in queued_gmail_uids(exclude=item):
                    print(f"Gmail: other jobs from this email are still queued; it is labelled "
                          f"'{config.processed_label}' after the last one is built.")
                else:
                    with Gmail() as gm:
                        gm.select(config.source_label)
                        gm.add_label(str(o.meta["gmail_uid"]), config.processed_label)
                    print(f"Gmail: labelled '{config.processed_label}'.")
            if config.email_results:
                msg_id = send_results(f"{o.score:.0f}% {o.band} — {o.title} @ {o.company}", _summary(o), o.files)
                print("Gmail: results emailed to you.")
                if config.results_label:
                    with Gmail() as gm:
                        n = gm.label_where(f"rfc822msgid:{msg_id.strip('<>')}", config.results_label,
                                           wait_seconds=60)
                    print(f"Gmail: results email labelled '{config.results_label}'." if n else
                          f"Gmail: results email not found yet; label '{config.results_label}' not applied.")
        except Exception as e:  # noqa: BLE001
            print(f"Gmail step skipped: {e}")

    tr = _tracker(config)
    if tr is not None:
        try:
            from .tracker import track_review
            analysis = json.loads((item / "analysis.json").read_text(encoding="utf-8"))
            posting = (item / "posting.txt").read_text(encoding="utf-8")
            res = track_review(tr, o.meta.get("item_id") or item.name, analysis, o.score, o.band, o.meta, posting)
            print(f"Tracker: row {res}.")
        except Exception as e:  # noqa: BLE001
            print(f"Tracker step skipped: {e}")
    remove_item(item)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="jobfit", description="Job-fit review and resume tailoring.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("fetch")
    a = sub.add_parser("add")
    a.add_argument("target")
    a.add_argument("--force", action="store_true", help="queue it even if it looks like a duplicate")
    sub.add_parser("list")
    s = sub.add_parser("schema")
    s.add_argument("which", choices=["analysis", "tailoring"])
    b = sub.add_parser("build")
    b.add_argument("item", type=Path)
    b.add_argument("--accept-issues", action="store_true")
    t = sub.add_parser("tracker", help="Google Sheets job tracker")
    t.add_argument("action", choices=["setup", "sync"])
    args = ap.parse_args(argv)

    load_env()
    config = Config.load()
    try:
        profile = Profile.load(config.profile_path)
    except ProfileError as e:
        print(e, file=sys.stderr)
        return 2

    if args.cmd == "validate":
        print(f"OK: {profile.full_name} — {len(profile.experience)} role(s), {len(profile.education)} "
              f"education, {len(profile.certifications)} certification(s), {len(profile.all_skills)} skills.")
        return 0
    if args.cmd == "fetch":
        return cmd_fetch(config)
    if args.cmd == "add":
        return cmd_add(args.target, config, args.force)
    if args.cmd == "tracker":
        return cmd_tracker(args.action, config)
    if args.cmd == "list":
        return cmd_list(config, profile)
    if args.cmd == "schema":
        from .schemas import analysis_schema, tailoring_schema
        schema = analysis_schema() if args.which == "analysis" else tailoring_schema(profile)
        print(json.dumps(schema, indent=1, ensure_ascii=False))
        return 0
    if args.cmd == "build":
        return cmd_build(args.item, config, profile, args.accept_issues)
    return 1


if __name__ == "__main__":
    sys.exit(main())
