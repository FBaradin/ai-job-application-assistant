"""Application kit: a self-contained HTML page with one-click copy for every portal field
(Workday, Greenhouse, Lever, iCIMS, SuccessFactors...)."""
from __future__ import annotations

from html import escape

from .profile import Profile, fmt_date, is_current


def _field(label: str, value: str, multiline: bool = False) -> str:
    value = (value or "").strip()
    if not value:
        return (f'<div class="row empty"><div class="lbl">{escape(label)}</div>'
                f'<div class="val muted">Not in master profile — fill manually</div></div>')
    cls = "val multi" if multiline else "val"
    count = f'<span class="count">{len(value)} chars</span>' if multiline else ""
    return (f'<div class="row"><div class="lbl">{escape(label)}{count}</div>'
            f'<div class="{cls}">{escape(value)}</div>'
            f'<button type="button" class="copy" aria-label="Copy {escape(label)}">Copy</button></div>')


def render_kit(*, profile: Profile, resume: dict, draft: dict, job: dict, base: str) -> str:
    p = profile.personal
    info = profile.application_info
    first = p.get("first_name") or profile.full_name.split(" ")[0]
    last = p.get("last_name") or " ".join(profile.full_name.split(" ")[1:])

    sec: list[str] = []
    sec.append("<h2>My Information</h2>" + "".join([
        _field("Legal first name", first), _field("Legal last name", last),
        _field("Email", p.get("email", "")), _field("Phone", p.get("phone", "")),
        _field("Address line 1", p.get("address_line", "")), _field("City", p.get("city", "")),
        _field("State / Province", p.get("state", "")), _field("Postal code", str(p.get("postal_code", ""))),
        _field("Country", p.get("country", "")),
        _field("LinkedIn", p.get("linkedin", "")), _field("Website", p.get("website", "")),
        _field("GitHub", p.get("github", "")),
    ]))

    exp_by_id = profile.by_id("experience")
    exp_html = ["<h2>My Experience</h2>",
                '<p class="hint">Most recent first, with roles at the same company together. Role descriptions are your tailored bullets.</p>']
    for i, e in enumerate(resume["experience"], 1):
        src = exp_by_id[e["id"]]
        desc = "\n".join(f"• {b}" for b in e["bullets"])
        exp_html.append(f'<div class="card"><h3>Work Experience {i}</h3>' + "".join([
            _field("Job title", e["title"]), _field("Company", e["company"]),
            _field("Location", e["location"]),
            _field("I currently work here", "Yes" if is_current(src.get("end")) else "No"),
            _field("From (MM/YYYY)", fmt_date(src.get("start"), "portal")),
            _field("To (MM/YYYY)", "" if is_current(src.get("end")) else fmt_date(src.get("end"), "portal")),
            _field("Role description", desc, multiline=True),
        ]) + "</div>")
    # Roles omitted from the tailored resume are still listed: portals often require full history.
    omitted = [e for e in profile.experience if e["id"] not in {x["id"] for x in resume["experience"]}]
    for e in omitted:
        desc = "\n".join(f"• {b}" for b in e.get("bullets") or [])
        exp_html.append('<div class="card"><h3>Additional role (not on tailored resume)</h3>' + "".join([
            _field("Job title", e.get("title", "")), _field("Company", e.get("company", "")),
            _field("Location", e.get("location", "")),
            _field("From (MM/YYYY)", fmt_date(e.get("start"), "portal")),
            _field("To (MM/YYYY)", fmt_date(e.get("end"), "portal")),
            _field("Role description", desc, multiline=True),
        ]) + "</div>")
    sec.append("".join(exp_html))

    edu_html = ["<h2>Education</h2>"]
    for i, e in enumerate(profile.education, 1):
        edu_html.append(f'<div class="card"><h3>Education {i}</h3>' + "".join([
            _field("School or university", e.get("institution", "")),
            _field("Degree", e.get("degree", "")), _field("Field of study", e.get("field", "")),
            _field("From (YYYY)", (e.get("start") or "")[:4]), _field("To (actual or expected, YYYY)", (e.get("end") or "")[:4]),
            _field("Overall result (GPA)", str(e.get("gpa") or "")),
        ]) + "</div>")
    sec.append("".join(edu_html))

    if profile.certifications:
        c_html = ["<h2>Certifications</h2>"]
        for c in profile.certifications:
            c_html.append('<div class="card">' + "".join([
                _field("Certification", c.get("name", "")), _field("Issued by", c.get("issuer", "")),
                _field("Issued date (MM/YYYY)", fmt_date(c.get("issued"), "portal")),
                _field("Expiration date", fmt_date(c.get("expires"), "portal")),
                _field("Credential ID", str(c.get("credential_id") or "")),
                _field("Credential URL", c.get("url", "")),
            ]) + "</div>")
        sec.append("".join(c_html))

    if profile.languages:
        sec.append("<h2>Languages</h2>" + "".join(
            _field(l.get("language", ""), l.get("proficiency", "")) for l in profile.languages))

    skills = [s for _, items in resume["skills"] if _ != "Languages" for s in items]
    others = [s for s in profile.all_skills if s not in skills]
    chips = "".join(f'<button type="button" class="chip">{escape(s)}</button>' for s in skills + others)
    sec.append("<h2>Skills</h2>"
               '<p class="hint">Most relevant first. Click a skill to copy it (Workday adds skills one at a time).</p>'
               f'<div class="chips">{chips}</div>' + _field("All skills, comma-separated", ", ".join(skills + others)))

    q_html = ["<h2>Application Questions</h2>"]
    for label, key in (("Work authorization", "work_authorization"),
                       ("Will you now or in the future require sponsorship?", "requires_sponsorship"),
                       ("Willing to relocate?", "willing_to_relocate"), ("Notice period", "notice_period"),
                       ("Desired salary", "desired_salary"), ("Earliest start date", "earliest_start_date"),
                       ("Pronouns", "pronouns")):
        q_html.append(_field(label, str(info.get(key) or "")))
    for a in draft.get("application_answers", []):
        q_html.append(_field(a["question"], a["answer"], multiline=True))
    q_html.append('<p class="hint">Voluntary disclosures (gender, ethnicity, veteran, disability) are '
                  'intentionally not stored — answer them yourself on each portal.</p>')
    sec.append("".join(q_html))

    sec.append("<h2>Files</h2>" + _field("Resume file to upload", f"{base}.pdf"))

    title = f"{job.get('title', '')} — {job.get('company', '')}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Application Kit — {escape(title)}</title>
<style>
:root{{--bg:#f6f6f4;--card:#fff;--text:#1c1c1c;--muted:#6b6b6b;--line:#e2e2dd;--accent:#2f5d8a;--ok:#2e7d4f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161616;--card:#202020;--text:#ececec;--muted:#9a9a9a;--line:#333;--accent:#7fb0e0;--ok:#6fcf97}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:860px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:22px;margin:0 0 4px}}
h2{{font-size:17px;margin:32px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}}h3{{font-size:14px;margin:0 0 8px;color:var(--muted);font-weight:600}}
.sub,.hint,.muted{{color:var(--muted)}}.hint{{font-size:13px;margin:0 0 10px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0}}
.row{{display:grid;grid-template-columns:200px 1fr auto;gap:10px;align-items:start;padding:7px 0;border-bottom:1px dashed var(--line)}}
.row:last-child{{border-bottom:0}}.lbl{{font-size:13px;color:var(--muted)}}.count{{display:block;font-size:11px}}
.val{{white-space:pre-wrap;word-break:break-word}}.val.multi{{font-size:14px}}
button{{font:inherit;cursor:pointer}}.copy{{border:1px solid var(--line);background:var(--card);color:var(--accent);border-radius:6px;padding:3px 10px;font-size:13px}}
.copy.done,.chip.done{{color:var(--ok);border-color:var(--ok)}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}}.chip{{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:3px 10px;font-size:13px}}
@media (max-width:600px){{.row{{grid-template-columns:1fr auto}}.lbl{{grid-column:1/-1}}}}
</style></head><body><main>
<h1>Application Kit</h1><p class="sub">{escape(title)} · {escape(profile.full_name)}</p>
{''.join(sec)}
</main>
<script>
function copyText(t,el){{const done=()=>{{el.classList.add('done');const o=el.textContent;if(el.classList.contains('copy'))el.textContent='Copied';setTimeout(()=>{{el.classList.remove('done');if(el.classList.contains('copy'))el.textContent=o}},1200)}};
if(navigator.clipboard&&window.isSecureContext){{navigator.clipboard.writeText(t).then(done,()=>fallback(t,done))}}else fallback(t,done)}}
function fallback(t,done){{const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{{document.execCommand('copy');done()}}catch(e){{}}a.remove()}}
document.querySelectorAll('.copy').forEach(b=>b.addEventListener('click',()=>copyText(b.parentElement.querySelector('.val').textContent,b)));
document.querySelectorAll('.chip').forEach(b=>b.addEventListener('click',()=>copyText(b.textContent,b)));
</script></body></html>
"""
