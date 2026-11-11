"""Turn an email (or a URL) into plain job-posting text."""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

MIN_POSTING_CHARS = 1200
SKIP_URL = re.compile(r"unsubscribe|preferences|privacy|help|settings|/legal|mailto:|\.(png|jpg|gif)(\?|$)", re.I)
# Links that look like a single job page: jobs/careers paths or a known job board / applicant system.
JOB_URL = re.compile(r"/jobs?/|/careers?/|/positions?/|/openings?/|/vacanc|/requisition|/empleos?/|"
                     r"greenhouse\.io|lever\.co|myworkdayjobs\.com|smartrecruiters\.com|ashbyhq\.com|"
                     r"workable\.com|bamboohr\.com|icims\.com|csod\.com|recruitee\.com|teamtailor\.com|"
                     r"[?&](gh_jid|jobid|job_id|jobId)=", re.I)
HEADERS ={"User-Agent": "Mozilla/5.0 (compatible; jobfit/1.0)"}


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


def is_job_link(url: str) -> bool:
    return bool(JOB_URL.search(url))


def email_to_postings(subject: str, text: str, html: str,
                      max_links: int = 3, max_jobs: int = 10) -> tuple[list[tuple[str, str]], list[str]]:
    """Turn one email into postings: ([(posting_text, source_description), ...], unreadable_job_links).

    * The email body is the posting when it is long enough on its own.
    * Otherwise, when the email holds links that look like job pages (jobs/careers paths or a known
      job board), each one that loads becomes its own posting, so an email listing several jobs
      gives several reviews (up to `max_jobs`). Links that do not load are returned separately.
    * With no job-looking links, the first of the other links that loads is used (up to `max_links`).
    * If nothing loads, the short email body is returned so it can still be reviewed (or marked
      not evaluable).
    """
    body = (text or "").strip()
    if len(body) < 200 and html:
        body = html_to_text(html)
    header = f"Email subject: {subject}\n\n{body}"
    if len(body) >= MIN_POSTING_CHARS:
        return [(header, "email body")], []

    urls = links(text, html)
    job_urls = [u for u in urls if is_job_link(u)][:max_jobs]
    postings, unreadable = [], []
    for url in job_urls or urls[:max_links]:
        page = fetch_url_text(url)
        if len(page) >= MIN_POSTING_CHARS:
            postings.append((f"{header}\n\n--- Content fetched from {url} ---\n{page[:60000]}",
                             f"email + {url}"))
            if not job_urls:
                break
        elif job_urls:
            unreadable.append(url)
    return postings or [(header, "email body")], unreadable
