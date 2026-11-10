"""Merge the model's tailoring draft with facts from the master profile."""
from __future__ import annotations

import re

from .profile import Profile, fmt_date, is_current

SECTION_TITLES = {
    "summary": "Summary",
    "experience": "Experience",
    "education": "Education",
    "certifications": "Certifications",
    "skills": "Skills",
    "projects": "Projects",
}


def _sort_key_recent(item: dict) -> tuple:
    end = "9999-99" if is_current(item.get("end")) else (item.get("end") or "")
    return (end, item.get("start") or "")


def _company_key(item: dict) -> str:
    return " ".join(str(item.get("company") or "").lower().split())


def _degree_line(degree, field) -> str:
    """'Degree, Field', but without the field when the degree already says it
    ('Bachelor of Biosystems Engineering' + 'Engineering' -> just the degree)."""
    degree, field = str(degree or "").strip(), str(field or "").strip()
    words = lambda t: set(re.findall(r"[a-z0-9]+", t.lower()))  # noqa: E731
    if degree and field and words(field) <= words(degree):
        return degree
    return ", ".join(x for x in (degree, field) if x)


def group_by_company(roles: list[dict]) -> list[dict]:
    """Most recent first, with every role at the same company kept together (newest role first).
    Companies are ordered by their most recent role. Sets `continued` on each role that follows
    another role at the same company, so renderers print the company heading only once."""
    roles = sorted(roles, key=_sort_key_recent, reverse=True)
    order = list(dict.fromkeys(_company_key(r) for r in roles))
    roles = sorted(roles, key=lambda r: order.index(_company_key(r)))  # stable: keeps recency within a company
    for i, r in enumerate(roles):
        r["continued"] = i > 0 and _company_key(roles[i - 1]) == _company_key(r)
    return roles


def short_url(url) -> str:
    """Visible link text: no scheme, no 'www.', no trailing slash (github.com/user)."""
    return re.sub(r"^(https?://)?(www\.)?", "", str(url or "").strip()).rstrip("/")


def full_url(url) -> str:
    url = str(url or "").strip()
    return url if not url or re.match(r"^(https?://|mailto:)", url) else "https://" + url


def build_resume(profile: Profile, draft: dict, max_bullets: int) -> dict:
    p = profile.personal
    # (visible text, link target). Links are printed as visible text so ATS parsers read them.
    contact = [(text, href) for text, href in (
        (profile.location_line(), ""),
        (p.get("phone"), ""),
        (p.get("email"), f"mailto:{p.get('email')}"),
        (short_url(p.get("linkedin")), full_url(p.get("linkedin"))),
        (short_url(p.get("github")), full_url(p.get("github"))),
        (short_url(p.get("website")), full_url(p.get("website"))),
    ) if text]

    exp_by_id = profile.by_id("experience")
    experience = []
    for entry in draft.get("experience", []):
        src = exp_by_id.get(entry.get("experience_id"))
        if not src or any(e["id"] == src["id"] for e in experience):
            continue
        experience.append({
            "id": src["id"],
            "company": src.get("company", ""),
            "location": src.get("location", ""),
            "title": src.get("title", ""),
            "start": src.get("start", ""),
            "end": src.get("end", ""),
            "dates": " – ".join(x for x in (fmt_date(src.get("start")), fmt_date(src.get("end"))) if x),
            "bullets": [b.strip() for b in entry.get("bullets", []) if b.strip()][:max_bullets],
        })
    # Harvard style: reverse-chronological, roles at the same company grouped under one heading;
    # relevance is expressed through bullet order.
    experience = group_by_company(experience)

    edu_by_id = profile.by_id("education")
    edu_ids = draft.get("education_ids") or [e["id"] for e in profile.education]
    education = []
    for eid in dict.fromkeys(edu_ids):
        src = edu_by_id.get(eid)
        if not src:
            continue
        degree = _degree_line(src.get("degree"), src.get("field"))
        if src.get("honors"):
            degree += f", {src['honors']}"
        education.append({
            "institution": src.get("institution", ""),
            "location": src.get("location", ""),
            "degree": degree,
            "dates": fmt_date(src.get("end")) or fmt_date(src.get("start")),
            "details": ([f"GPA: {src['gpa']}"] if src.get("gpa") else []) + list(src.get("details") or []),
        })

    cert_by_id = profile.by_id("certifications")
    certifications = []
    for cid in dict.fromkeys(draft.get("certification_ids") or []):
        src = cert_by_id.get(cid)
        if src:
            certifications.append({
                "name": src.get("name", ""),
                "issuer": src.get("issuer", ""),
                "date": fmt_date(src.get("issued")),
            })

    proj_by_id = profile.by_id("projects")
    projects = []
    for entry in draft.get("projects", []) or []:
        src = proj_by_id.get(entry.get("project_id"))
        if src:
            projects.append({
                "name": src.get("name", ""),
                "date": fmt_date(src.get("date")),
                "url": short_url(src.get("url")),
                "href": full_url(src.get("url")),
                "bullets": [b for b in entry.get("bullets", []) if b.strip()][:max_bullets],
            })

    allowed = set(profile.all_skills)
    skill_lines = []
    for group in draft.get("skill_groups", []):
        items = [s for s in dict.fromkeys(group.get("items", [])) if s in allowed]
        if items:
            skill_lines.append((group.get("label", "Skills").strip() or "Skills", items))
    if draft.get("include_languages") and profile.languages:
        langs = [f"{l.get('language')} ({l.get('proficiency')})" if l.get("proficiency") else l.get("language")
                 for l in profile.languages]
        skill_lines.append(("Languages", langs))

    order = [s for s in dict.fromkeys(draft.get("section_order") or []) if s in SECTION_TITLES]
    for s in ("summary", "experience", "education", "certifications", "projects", "skills"):
        if s not in order:
            order.append(s)

    return {
        "name": profile.full_name,
        "contact": contact,
        "summary": draft.get("summary", "").strip(),
        "experience": experience,
        "education": education,
        "certifications": certifications,
        "projects": projects,
        "skills": skill_lines,
        "section_order": order,
    }


def resume_markdown(r: dict) -> str:
    out = [f"**{r['name']}**", "", " | ".join(text for text, _ in r["contact"]), ""]
    for section in r["section_order"]:
        block = _md_section(r, section)
        if block:
            out += [f"**{SECTION_TITLES[section].upper()}**", ""] + block + [""]
    return "\n".join(out).strip() + "\n"


def _md_section(r: dict, section: str) -> list[str]:
    lines: list[str] = []
    if section == "summary" and r["summary"]:
        lines.append(r["summary"])
    elif section == "experience":
        for e in r["experience"]:
            if not e.get("continued"):
                lines.append(f"**{e['company']}** — {e['location']}  ")
            lines.append(f"*{e['title']}* | {e['dates']}")
            lines += [f"- {b}" for b in e["bullets"]] + [""]
    elif section == "education":
        for e in r["education"]:
            lines.append(f"**{e['institution']}** — {e['location']}  ")
            lines.append(f"*{e['degree']}* | {e['dates']}")
            lines += [f"- {d}" for d in e["details"]] + [""]
    elif section == "certifications":
        lines += [f"- {c['name']}" + (f", {c['issuer']}" if c["issuer"] else "") +
                  (f" ({c['date']})" if c["date"] else "") for c in r["certifications"]]
    elif section == "projects":
        for p in r["projects"]:
            lines.append(f"**{p['name']}**" + (f" | {p['date']}" if p["date"] else "") + ("  " if p["url"] else ""))
            if p["url"]:
                lines.append(p["url"])
            lines += [f"- {b}" for b in p["bullets"]] + [""]
    elif section == "skills":
        lines += [f"- **{label}:** {', '.join(items)}" for label, items in r["skills"]]
    while lines and lines[-1] == "":
        lines.pop()
    return lines
