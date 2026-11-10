"""Turn an email (or a URL) into plain job-posting text."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

MIN_POSTING_CHARS = 1200
SKIP_URL = re.compile(r"unsubscribe|preferences|privacy|help|settings|/legal|mailto:|\.(png|jpg|gif)(\?|$)", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; jobfit/1.0)"}


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in text.splitlines()]
    out, blank = [], False
    for l in lines:
        if not l:
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(l)
            blank = False
    return "\n".join(out).strip()


def links(text: str, html: str) -> list[str]:
    urls: list[str] = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        urls += [a.get("href", "") for a in soup.find_all("a")]
    urls += re.findall(r"https?://[^\s<>\"')\]]+", text or "")
    seen = []
    for u in urls:
        if u.startswith("http") and not SKIP_URL.search(u) and u not in seen:
            seen.append(u)
    return seen


def fetch_url_text(url: str, timeout: int = 20) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
            return ""
        return html_to_text(resp.text)
    except requests.RequestException:
        return ""


def email_to_posting(subject: str, text: str, html: str, max_links: int = 3) -> tuple[str, str]:
    """Return (posting_text, source_description)."""
    body = (text or "").strip()
    if len(body) < 200 and html:
        body = html_to_text(html)
    posting = f"Email subject: {subject}\n\n{body}"
    source = "email body"
    if len(body) < MIN_POSTING_CHARS:
        for url in links(text, html)[:max_links]:
            page = fetch_url_text(url)
            if len(page) >= MIN_POSTING_CHARS:
                posting += f"\n\n--- Content fetched from {url} ---\n{page[:60000]}"
                source = f"email + {url}"
                break
    return posting, source
