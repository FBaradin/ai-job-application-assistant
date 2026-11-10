"""Gmail over IMAP/SMTP with an app password.

Gmail exposes each label as an IMAP folder and supports the X-GM-LABELS
extension, so we can read a label and mark messages processed by adding
another label - no Google Cloud project or OAuth consent screen needed.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import make_msgid, parsedate_to_datetime
from pathlib import Path

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SELF_PREFIX = "[JobFit]"


@dataclass
class JobEmail:
    uid: str
    subject: str
    sender: str
    date: str
    text: str
    html: str


def _quote(mailbox: str) -> str:
    return '"' + mailbox.replace("\\", "\\\\").replace('"', '\\"') + '"'


def credentials() -> tuple[str, str]:
    addr = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not addr or not pw:
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set: add them to the .env file (see docs/GETTING_STARTED.md, part 5).")
    return addr, pw


class Gmail:
    def __init__(self):
        self.address, self._pw = credentials()
        self.imap: imaplib.IMAP4_SSL | None = None

    def __enter__(self):
        self.imap = imaplib.IMAP4_SSL(IMAP_HOST)
        self.imap.login(self.address, self._pw)
        return self

    def __exit__(self, *exc):
        try:
            self.imap.logout()
        except Exception:
            pass

    def select(self, label: str) -> None:
        typ, _ = self.imap.select(_quote(label))
        if typ != "OK":
            raise RuntimeError(f'Gmail label "{label}" not found. Create it or fix gmail.source_label in config.yaml.')

    def unprocessed(self, label: str, skip_labels: list[str], limit: int,
                    skip_uids: set[str] | None = None) -> list[JobEmail]:
        self.select(label)
        typ, data = self.imap.uid("SEARCH", None, "ALL")
        uids = data[0].split() if data and data[0] else []
        found: list[JobEmail] = []
        for uid in uids:
            uid = uid.decode()
            if skip_uids and uid in skip_uids:
                continue  # already queued in inbox/
            typ, meta = self.imap.uid("FETCH", uid, "(X-GM-LABELS)")
            labels_blob = b" ".join(x if isinstance(x, bytes) else b" ".join(x) for x in meta if x).decode(
                "utf-8", "replace")
            if any(self._has_label(labels_blob, s) for s in skip_labels):
                continue
            msg = self._fetch(uid)
            if msg.subject.startswith(SELF_PREFIX):
                continue  # our own results email
            found.append(msg)
            if len(found) >= limit:
                break
        return found

    @staticmethod
    def _has_label(blob: str, label: str) -> bool:
        return f'"{label}"' in blob or re.search(r"[ (]" + re.escape(label) + r"[ )]", blob) is not None

    def _fetch(self, uid: str) -> JobEmail:
        typ, data = self.imap.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK: don't mark as read
        raw = next(part[1] for part in data if isinstance(part, tuple))
        msg = email.message_from_bytes(raw, policy=default_policy)
        text = html = ""
        for part in msg.walk():
            if part.get_content_maintype() == "multipart" or part.get_filename():
                continue
            ctype = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                continue
            if ctype == "text/plain" and not text:
                text = content
            elif ctype == "text/html" and not html:
                html = content
        try:
            date = parsedate_to_datetime(msg["Date"]).strftime("%Y-%m-%d")
        except Exception:
            date = ""
        return JobEmail(uid=uid, subject=str(msg["Subject"] or ""), sender=str(msg["From"] or ""),
                        date=date, text=text, html=html)

    def add_label(self, uid: str, label: str) -> None:
        self.imap.create(_quote(label))  # no-op error if it already exists
        self.imap.uid("STORE", uid, "+X-GM-LABELS", f"({_quote(label)})")

    def select_all_mail(self) -> None:
        """Select Gmail's All Mail folder, found by its \\All flag (its name is localised)."""
        typ, boxes = self.imap.list()
        for line in boxes or []:
            text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
            if "\\All" in text:
                name = text.rsplit(' "/" ', 1)[-1].strip()
                if self.imap.select(name if name.startswith('"') else _quote(name))[0] == "OK":
                    return
        raise RuntimeError("Could not find Gmail's All Mail folder over IMAP.")

    def label_where(self, gmail_query: str, label: str, wait_seconds: int = 0) -> int:
        """Apply `label` to every message matching a Gmail search query. Returns the count.
        Retries for up to `wait_seconds` (a just-sent message can take a few seconds to appear)."""
        deadline = time.time() + wait_seconds
        while True:
            self.select_all_mail()
            typ, data = self.imap.uid("SEARCH", "X-GM-RAW", _quote(gmail_query))
            uids = data[0].split() if typ == "OK" and data and data[0] else []
            if uids or time.time() >= deadline:
                break
            time.sleep(3)
        for uid in uids:
            self.add_label(uid.decode(), label)
        return len(uids)


def send_results(subject: str, body: str, attachments: list[Path]) -> str:
    """Email the results to yourself. Returns the Message-ID (used to label the message)."""
    addr, pw = credentials()
    msg = EmailMessage()
    msg["From"] = addr
    msg["To"] = addr
    msg["Subject"] = f"{SELF_PREFIX} {subject}"
    msg["Message-ID"] = make_msgid(domain=addr.split("@")[-1])
    msg.set_content(body)
    for path in attachments:
        subtype = {"pdf": ("application", "pdf"), "html": ("text", "html"),
                   "md": ("text", "markdown")}.get(path.suffix.lstrip("."), ("application", "octet-stream"))
        msg.add_attachment(path.read_bytes(), maintype=subtype[0], subtype=subtype[1], filename=path.name)
    with smtplib.SMTP_SSL(SMTP_HOST, 465) as s:
        s.login(addr, pw)
        s.send_message(msg)
    return msg["Message-ID"]
