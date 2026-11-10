"""Google Sheets job tracker.

One row per job posting, keyed by a hidden Tracker ID (the inbox item id).
The workflow fills the review columns; the Stage column belongs to you once a
job has been processed - the workflow only sets it to "Processed by Claude" when
it is still blank (job waiting in the inbox) and never overwrites your updates.
"Stage Met" is a formula: the number of the current stage (1-11).
"Status" is a formula: Pending / Open / Closed, looked up from the stage
(a blank stage - a job still waiting in the inbox - is Pending).

Auth: a Google Cloud service account (free, no billing) whose JSON key path is
in GOOGLE_SERVICE_ACCOUNT_FILE, with the sheet (GOOGLE_SHEET_ID) shared to its
e-mail address as Editor. See docs/GETTING_STARTED.md, part 6.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from . import ROOT

TAB = "Tracker"
LISTS_TAB = "Stages"

STAGE_STATUS = {  # stage -> process status, in stage order
    "Processed by Claude": "Pending",
    "Application not sent": "Closed",
    "Application sent": "Open",
    "First interview assigned": "Open",
    "Second interview assigned": "Open",
    "Third interview assigned": "Open",
    "Fourth interview assigned": "Open",
    "Fifth interview assigned": "Open",
    "Interview failed": "Closed",
    "Rejected before interview": "Closed",
    "Job offer received": "Closed",
}
STAGES = list(STAGE_STATUS)
INBOX_STAGE = ""                       # a job waiting in the inbox has no stage yet (status: Pending)
PROCESSED_STAGE = STAGES[0]
RENAMED_STAGES = {"Rejected": "Rejected before interview"}
OLD_INBOX_STAGES = ("", "Sitting in inbox")   # stages the workflow may still move forward

COLUMNS = [  # (header, width in pixels)
    ("Status", 90),
    ("Company", 150),
    ("Role", 200),
    ("Date Published", 105),
    ("Date Received", 105),
    ("Date Processed", 105),
    ("JobFit Score", 85),
    ("Recommendation", 130),
    ("Role Summary", 320),
    ("Job Link", 200),
    ("Key Requirements", 320),
    ("Strong Matches", 300),
    ("Partial Matches", 300),
    ("Missing Requirements", 300),
    ("Stage", 175),
    ("Stage Met", 80),
    ("Tracker ID", 60),
]
HEADERS = [c[0] for c in COLUMNS]
COL = {h: i for i, h in enumerate(HEADERS)}           # header -> 0-based index
WORKFLOW_COLS = HEADERS[COL["Company"]:COL["Stage"]]    # Company .. Missing Requirements
FROZEN_COLS = COL["Role"] + 1                           # Status, Company, Role stay visible


def _letter(i: int) -> str:
    return chr(ord("A") + i)


LAST = _letter(len(HEADERS) - 1)                        # "Q"
STATUS_L = _letter(COL["Status"])                       # "A"
STAGE_L = _letter(COL["Stage"])                         # "O"
MET_L = _letter(COL["Stage Met"])                       # "P"
FIRST_WORKFLOW_L = _letter(COL["Company"])              # "B"
LAST_WORKFLOW_L = _letter(COL["Missing Requirements"])  # "N"

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


class TrackerNotConfigured(RuntimeError):
    pass


# ------------------------------------------------------------------ row data
def job_link(meta: dict, posting: str = "") -> str:
    if meta.get("job_url"):
        return meta["job_url"]
    m = URL_RE.search(meta.get("fetched_from", "") or "")
    if m:
        return m.group(0)
    m = URL_RE.search(posting or "")
    if m:
        return m.group(0)
    src = meta.get("source", "")
    return src if src.startswith("http") else ""


def _lines(items: list[str]) -> str:
    return "\n".join(f"• {i}" for i in items if i)


def review_row(analysis: dict, score: float, label: str, meta: dict, posting: str,
               processed: str) -> dict:
    job, match = analysis["job"], analysis["match"]
    return {
        "Company": job.get("company", ""),
        "Role": job.get("title", ""),
        "Date Published": job.get("date_published", ""),
        "Date Received": meta.get("date", "") or (meta.get("created", "") or "")[:10],
        "Date Processed": processed,
        "JobFit Score": round(score, 1) if job.get("is_evaluable", True) else "",
        "Recommendation": (analysis["recommendation"]["decision"] if job.get("is_evaluable", True)
                           else "Not evaluable"),
        "Role Summary": analysis.get("role_summary", ""),
        "Job Link": job_link(meta, posting),
        "Key Requirements": _lines(analysis.get("key_requirements", [])),
        "Strong Matches": _lines([m["requirement"] for m in match.get("strong_matches", [])]),
        "Partial Matches": _lines([f'{m["requirement"]} (gap: {m["gap"]})' if m.get("gap")
                                   else m["requirement"] for m in match.get("partial_matches", [])]),
        "Missing Requirements": _lines([f'{m["requirement"]} [{m["importance"]}]'
                                        for m in match.get("missing_requirements", [])]),
    }


def inbox_row(meta: dict, posting: str) -> dict:
    return {
        "Company": "",
        "Role": "(awaiting review)",
        "Date Received": meta.get("date", "") or (meta.get("created", "") or "")[:10],
        "Job Link": job_link(meta, posting),
    }


def _cell(value) -> object:
    """Values are sent USER_ENTERED (so dates become real dates); keep text from
    being parsed as a formula or number by Sheets."""
    if isinstance(value, (int, float)):
        return value
    text = str(value or "")
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


# ------------------------------------------------------------------ sheet
class Tracker:
    def __init__(self):
        key_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
        sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
        if not key_file or not sheet_id:
            raise TrackerNotConfigured(
                "GOOGLE_SERVICE_ACCOUNT_FILE / GOOGLE_SHEET_ID not set in .env (see docs/GETTING_STARTED.md, part 6).")
        path = Path(key_file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise TrackerNotConfigured(f"Service account key not found: {path}")
        import gspread
        self._gspread = gspread
        # BackOffHTTPClient retries automatically on the per-minute quota (HTTP 429)
        self.gc = gspread.service_account(filename=str(path), http_client=gspread.BackOffHTTPClient)
        try:
            self.sh = self.gc.open_by_key(sheet_id)
        except gspread.exceptions.APIError as e:  # 403/404: not shared, wrong id, API off
            raise RuntimeError(
                f"Cannot open the Google Sheet ({e}). Check GOOGLE_SHEET_ID, that the Google Sheets API "
                f"is enabled, and that the sheet is shared as Editor with "
                f"{json.loads(path.read_text(encoding='utf-8')).get('client_email', 'the service account')}."
            ) from e
        self.ws = self._ensure_layout()

    # ---------------------------------------------------------- layout
    def _ensure_layout(self, force: bool = False):
        titles = [w.title for w in self.sh.worksheets()]
        created = False
        if TAB in titles:
            ws = self.sh.worksheet(TAB)
        elif len(titles) == 1 and not any(self.sh.sheet1.get_all_values()):
            ws = self.sh.sheet1                       # brand-new sheet: reuse "Sheet1"
            ws.update_title(TAB)
            created = True
        else:
            ws = self.sh.add_worksheet(TAB, rows=1000, cols=len(HEADERS), index=0)
            created = True
        if LISTS_TAB not in [w.title for w in self.sh.worksheets()]:
            lists = self.sh.add_worksheet(LISTS_TAB, rows=len(STAGES), cols=3)
            created = True
        else:
            lists = self.sh.worksheet(LISTS_TAB)
        if lists.row_count != len(STAGES) or lists.col_count != 3:   # A: stage, B: status, C: probe
            lists.resize(rows=len(STAGES), cols=3)
        lists.update(range_name=f"A1:B{len(STAGES)}", values=[[s, STAGE_STATUS[s]] for s in STAGES])
        self.sep = self._formula_separator(lists)

        header = ws.row_values(1)
        migrated = False
        if header and not created:
            migrated = self._insert_new_columns(ws, header)
            if migrated:
                header = ws.row_values(1)
            migrated = self._reorder_columns(ws, header) or migrated
        if migrated:
            header = ws.row_values(1)
        if header != HEADERS or created or force or migrated:
            if ws.col_count < len(HEADERS):
                ws.add_cols(len(HEADERS) - ws.col_count)
            ws.update(range_name=f"A1:{LAST}1", values=[HEADERS])
            self._format(ws, lists)
        return ws

    @staticmethod
    def _formula_separator(lists) -> str:
        """Formulas written through the API follow the spreadsheet's locale: ',' between
        arguments in e.g. English, ';' in locales with a decimal comma (es_ES, de_DE...).
        Probe once with a two-argument formula instead of guessing from the locale name."""
        lists.update(range_name="C1", values=[["=MAX(1,2)"]], value_input_option="USER_ENTERED")
        ok = lists.acell("C1").value == "2"
        lists.batch_clear(["C1"])
        return "," if ok else ";"

    def _insert_new_columns(self, ws, header: list[str]) -> bool:
        """Insert columns added to HEADERS since the sheet was created (e.g. Status), in
        place, so existing data stays aligned. Returns True if anything was inserted."""
        header = list(header)
        reqs = []
        for i, h in enumerate(HEADERS):
            if h in header or i + 1 >= len(HEADERS):
                continue
            nxt = HEADERS[i + 1]
            if i < len(header) and header[i] == nxt:     # the column after it sits where it should be
                reqs.append({"insertDimension": {"range": {"sheetId": ws.id, "dimension": "COLUMNS",
                                                           "startIndex": i, "endIndex": i + 1},
                                                 "inheritFromBefore": True}})
                header.insert(i, h)
        if reqs:
            self.sh.batch_update({"requests": reqs})
        return bool(reqs)

    def _reorder_columns(self, ws, header: list[str]) -> bool:
        """Move existing columns (with their data) into HEADERS order, e.g. Status to the front.
        Returns True if anything moved."""
        header = list(header)
        if sorted(header[:len(HEADERS)]) != sorted(HEADERS) or header[:len(HEADERS)] == HEADERS:
            return False
        # Unfreeze first: Sheets rejects moves that cut across frozen columns (_format re-freezes)
        reqs = [{"updateSheetProperties": {"properties": {"sheetId": ws.id,
                                                          "gridProperties": {"frozenColumnCount": 0}},
                                           "fields": "gridProperties.frozenColumnCount"}}]
        for i, h in enumerate(HEADERS):        # ascending: everything left of i is already in place
            j = header.index(h)
            if j == i:
                continue
            reqs.append({"moveDimension": {"source": {"sheetId": ws.id, "dimension": "COLUMNS",
                                                      "startIndex": j, "endIndex": j + 1},
                                           "destinationIndex": i}})
            header.insert(i, header.pop(j))
        self.sh.batch_update({"requests": reqs})
        return True

    def _met_formula(self, r: int) -> str:
        s = self.sep
        return f"=IFERROR(MATCH({STAGE_L}{r}{s}'{LISTS_TAB}'!$A:$A{s}0){s}\"\")"

    def _status_formula(self, r: int) -> str:
        s = self.sep
        return (f"=IF({STAGE_L}{r}=\"\"{s}\"Pending\"{s}"
                f"IFERROR(VLOOKUP({STAGE_L}{r}{s}'{LISTS_TAB}'!$A:$B{s}2{s}FALSE){s}\"\"))")

    def refresh_formulas(self) -> int:
        """Rewrite Stage Met and Status on every data row and rename retired stages
        (e.g. after the stage list changes). Returns the number of rows."""
        values = self.ws.get_all_values()
        n = len(values)
        if n < 2:
            return 0
        stages = []
        for row in values[1:]:
            st = row[COL["Stage"]] if len(row) > COL["Stage"] else ""
            st = "" if st == "Sitting in inbox" else RENAMED_STAGES.get(st, st)
            stages.append([st])
        self.ws.batch_update([
            {"range": f"{STAGE_L}2:{STAGE_L}{n}", "values": stages},
            {"range": f"{MET_L}2:{MET_L}{n}", "values": [[self._met_formula(r)] for r in range(2, n + 1)]},
            {"range": f"{STATUS_L}2:{STATUS_L}{n}", "values": [[self._status_formula(r)] for r in range(2, n + 1)]},
        ], value_input_option="USER_ENTERED")
        return n - 1

    def _format(self, ws, lists) -> None:
        sid, n = ws.id, len(HEADERS)
        rows = max(ws.row_count, 1000)

        def rng(c0, c1, r0=1, r1=rows):
            return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                    "startColumnIndex": c0, "endColumnIndex": c1}

        reqs = [
            {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1,
                                                                                       "frozenColumnCount": FROZEN_COLS}},
                                       "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
            {"repeatCell": {"range": rng(0, n, 0, 1), "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "backgroundColor": {"red": 0.16, "green": 0.27, "blue": 0.44},
                "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat(textFormat,backgroundColor,verticalAlignment,wrapStrategy)"}},
            {"repeatCell": {"range": rng(0, n), "cell": {"userEnteredFormat": {
                "verticalAlignment": "TOP", "wrapStrategy": "WRAP"}},
                "fields": "userEnteredFormat(verticalAlignment,wrapStrategy)"}},
            {"repeatCell": {"range": rng(COL["Job Link"], COL["Job Link"] + 1),
                            "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
            {"repeatCell": {"range": rng(COL["Date Published"], COL["Date Processed"] + 1),
                            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE",
                                                                            "pattern": "yyyy-mm-dd"}}},
                            "fields": "userEnteredFormat.numberFormat"}},
            {"repeatCell": {"range": rng(COL["JobFit Score"], COL["JobFit Score"] + 1),
                            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.0"},
                                                           "horizontalAlignment": "CENTER"}},
                            "fields": "userEnteredFormat(numberFormat,horizontalAlignment)"}},
            {"repeatCell": {"range": rng(COL["Stage Met"], COL["Stage Met"] + 1),
                            "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
                            "fields": "userEnteredFormat.horizontalAlignment"}},
            {"repeatCell": {"range": rng(COL["Status"], COL["Status"] + 1),
                            "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER"}},
                            "fields": "userEnteredFormat.horizontalAlignment"}},
            {"setDataValidation": {"range": rng(COL["Stage"], COL["Stage"] + 1), "rule": {
                "condition": {"type": "ONE_OF_RANGE",
                              "values": [{"userEnteredValue": f"='{LISTS_TAB}'!$A$1:$A${len(STAGES)}"}]},
                "strict": True, "showCustomUi": True}}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                                                     "startIndex": COL["Tracker ID"],
                                                     "endIndex": COL["Tracker ID"] + 1},
                                           "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
            {"updateSheetProperties": {"properties": {"sheetId": lists.id, "hidden": True}, "fields": "hidden"}},
            # A filter on the whole table: sorting from its header menu moves entire rows,
            # including the hidden Tracker ID, so rows stay matched to their jobs.
            {"setBasicFilter": {"filter": {"range": {"sheetId": sid, "startRowIndex": 0,
                                                     "startColumnIndex": 0, "endColumnIndex": n}}}},
        ]
        for i, (_, width) in enumerate(COLUMNS):
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": width}, "fields": "pixelSize"}})
        # Score colours (replace any earlier rules so re-running setup doesn't stack them)
        meta = self.sh.fetch_sheet_metadata({"fields": "sheets(properties.sheetId,conditionalFormats)"})
        existing = next((s.get("conditionalFormats", []) for s in meta["sheets"]
                         if s["properties"]["sheetId"] == sid), [])
        reqs += [{"deleteConditionalFormatRule": {"sheetId": sid, "index": 0}} for _ in existing]
        # Built-in number conditions (no formulas, so they work in any locale). Each rule is
        # inserted at index 0, so the final order is green, yellow, red - first match wins.
        score_rng = rng(COL["JobFit Score"], COL["JobFit Score"] + 1)
        for cond, value, color in (("NUMBER_LESS", "50", (0.96, 0.80, 0.80)),
                                   ("NUMBER_GREATER_THAN_EQ", "50", (1, 0.95, 0.80)),
                                   ("NUMBER_GREATER_THAN_EQ", "65", (0.85, 0.94, 0.83))):
            reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [score_rng],
                "booleanRule": {"condition": {"type": cond, "values": [{"userEnteredValue": value}]},
                                "format": {"backgroundColor": dict(zip(("red", "green", "blue"), color))}}}}})
        status_rng = rng(COL["Status"], COL["Status"] + 1)
        for text, color in (("Open", (0.85, 0.94, 0.83)), ("Pending", (1, 0.95, 0.80)),
                            ("Closed", (0.96, 0.80, 0.80))):
            reqs.append({"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [status_rng],
                "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": text}]},
                                "format": {"backgroundColor": dict(zip(("red", "green", "blue"), color)),
                                           "textFormat": {"bold": True}}}}}})
        self.sh.batch_update({"requests": reqs})

    # ---------------------------------------------------------- rows
    def _find(self, tracker_id: str, company: str = "", role: str = "") -> tuple[int | None, list[str]]:
        """Row for this job. Matches on the hidden Tracker ID, but if that row's company/role
        disagree with the job (e.g. the sheet was sorted without the hidden column), the
        company + role match wins and the ID on that row is corrected."""
        values = self.ws.get_all_values()

        def cell(row, h):
            return row[COL[h]] if len(row) > COL[h] else ""

        def same_job(row):
            return cell(row, "Company") == company and cell(row, "Role") == role

        by_id = next(((i, row) for i, row in enumerate(values[1:], start=2)
                      if cell(row, "Tracker ID") == tracker_id), None)
        if by_id and (not company or not cell(by_id[1], "Company") or same_job(by_id[1])):
            return by_id
        if company:
            hit = next(((i, row) for i, row in enumerate(values[1:], start=2) if same_job(row)), None)
            if hit:
                i, row = hit
                self.ws.update(range_name=f"{LAST}{i}", values=[[tracker_id]])
                if by_id and by_id[0] != i:       # the stale ID pointed at another job's row
                    self.ws.update(range_name=f"{LAST}{by_id[0]}", values=[[""]])
                return i, row
        return None, values

    def upsert(self, tracker_id: str, data: dict, stage: str) -> str:
        """Create or update a row. Returns 'added' or 'updated'.
        Workflow columns are only written when a value is given; Stage only moves
        forward from blank (job waiting in the inbox), never over a stage you set."""
        r, found = self._find(tracker_id, str(data.get("Company", "")), str(data.get("Role", "")))
        if r is None:
            r = max(len(found) + 1, 2)
            special = {"Status": self._status_formula(r), "Stage": stage,
                       "Stage Met": self._met_formula(r), "Tracker ID": tracker_id}
            row = [special[h] if h in special else _cell(data.get(h, "")) for h in HEADERS]
            self.ws.update(range_name=f"A{r}:{LAST}{r}", values=[row], value_input_option="USER_ENTERED")
            return "added"
        current = found + [""] * (len(HEADERS) - len(found))
        row = [_cell(data[h]) if h in data and data[h] != "" else current[COL[h]] for h in WORKFLOW_COLS]
        updates = [{"range": f"{FIRST_WORKFLOW_L}{r}:{LAST_WORKFLOW_L}{r}", "values": [row]}]
        if current[COL["Stage"]] in OLD_INBOX_STAGES and stage and stage != current[COL["Stage"]]:
            updates.append({"range": f"{STAGE_L}{r}", "values": [[stage]]})
        # Always rewrite the formulas so they track the current layout
        updates.append({"range": f"{MET_L}{r}", "values": [[self._met_formula(r)]]})
        updates.append({"range": f"{STATUS_L}{r}", "values": [[self._status_formula(r)]]})
        self.ws.batch_update(updates, value_input_option="USER_ENTERED")
        return "updated"

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sh.id}"


# ------------------------------------------------------------------ helpers used by the CLI
def track_inbox(tracker: Tracker, item: Path) -> str:
    meta = json.loads((item / "meta.json").read_text(encoding="utf-8"))
    posting = (item / "posting.txt").read_text(encoding="utf-8")
    return tracker.upsert(meta.get("item_id") or item.name, inbox_row(meta, posting), INBOX_STAGE)


def track_review(tracker: Tracker, tracker_id: str, analysis: dict, score: float, label: str,
                 meta: dict, posting: str, processed: str | None = None) -> str:
    row = review_row(analysis, score, label, meta, posting, processed or date.today().isoformat())
    return tracker.upsert(tracker_id, row, PROCESSED_STAGE)


def sync_all(tracker: Tracker, output_dir: Path, inbox_items: list[Path]) -> list[str]:
    """Backfill: every finished review under applications/ plus everything still queued."""
    log = []
    for saved in sorted(output_dir.glob("*/analysis.json")):
        data = json.loads(saved.read_text(encoding="utf-8"))
        meta = data.get("meta", {}) or {}
        folder = saved.parent
        posting_file = folder / "job_posting.txt"
        posting = posting_file.read_text(encoding="utf-8") if posting_file.exists() else ""
        processed = folder.name[:10] if re.match(r"\d{4}-\d{2}-\d{2}", folder.name) else ""
        tid = meta.get("item_id") or folder.name
        res = track_review(tracker, tid, data["analysis"], data["score"], data.get("band", ""), meta,
                           posting, processed)
        log.append(f"{res}: {data['analysis']['job']['company']} - {data['analysis']['job']['title']}")
    for item in inbox_items:
        res = track_inbox(tracker, item)
        log.append(f"{res}: inbox {item.name}")
    return log
