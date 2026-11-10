"""The fit report, in the Step 6 structure."""
from __future__ import annotations

from .config import WEIGHTS
from .resume import resume_markdown

LABELS = {
    "relevant_experience": "Relevant Experience",
    "skills_alignment": "Skills Alignment",
    "tools_technologies": "Tools / Technologies",
    "industry_context": "Industry Context",
    "soft_skills": "Soft Skills",
}


def _bullets(items) -> list[str]:
    return [f"- {i}" for i in items] if items else ["- _None identified._"]


def render_report(*, analysis: dict, score: float, band: str, threshold: int, base: str,
                  source: str, resume: dict | None, draft: dict | None,
                  issues: list[str], generated: str) -> str:
    job = analysis["job"]
    jd = analysis["jd_analysis"]
    m = analysis["match"]
    rec = analysis["recommendation"]
    tailored = resume is not None
    L: list[str] = [
        f"# Job Fit Review — {job['title']} at {job['company']}",
        "",
        f"**Score: {score:.0f}% ({band})** · Recommendation: **{rec['decision']}** · "
        f"{'Tailored resume generated' if tailored else f'No resume generated (below {threshold}%)'}",
        "",
        f"Location: {job.get('location') or 'n/a'} · Source: {source} · Generated: {generated}",
        "",
    ]
    if not job.get("is_evaluable", True):
        L += [f"> **Warning: the posting could not be fully evaluated.** {job.get('not_evaluable_reason', '')}", ""]

    L += ["## 1. Role Summary", "", analysis["role_summary"], ""]
    L += ["## 2. Key Job Requirements", ""] + [f"{i}. {r}" for i, r in enumerate(analysis["key_requirements"][:8], 1)] + [""]

    L += ["## 3. Profile Match Analysis", "", "### Strong Matches", ""]
    L += _bullets([f"**{x['requirement']}** — {x['evidence']}" for x in m["strong_matches"]])
    L += ["", "### Partial Matches", ""]
    L += _bullets([f"**{x['requirement']}** — {x['evidence']} _Gap: {x['gap']}_" for x in m["partial_matches"]])
    L += ["", "### Missing Requirements", ""]
    L += _bullets([f"**{x['requirement']}** ({x['importance']})" for x in m["missing_requirements"]])
    L += ["", "### Transferable Strengths", ""]
    L += _bullets([f"**{x['strength']}** — {x['why_it_matters']}" for x in m["transferable_strengths"]])

    L += ["", "## 4. Job Fit Score", "", f"**{score:.0f}% — {band}**", "",
          "| Dimension | Weight | Score | Weighted | Rationale |", "|---|---:|---:|---:|---|"]
    for key, weight in WEIGHTS.items():
        d = analysis["scores"][key]
        rationale = d["rationale"].replace("|", "/").replace("\n", " ")
        L.append(f"| {LABELS[key]} | {weight}% | {d['score']} | {d['score'] * weight / 100:.1f} | {rationale} |")
    L += [f"| **Total** | 100% | | **{score:.1f}** | |", "", analysis["score_explanation"], ""]

    L += ["## 5. Strategic Recommendation", "", f"**{rec['decision']}.** {rec['rationale']}", "",
          "**Key skill gaps**", ""] + _bullets(rec["key_skill_gaps"]) + [
          "", f"**Could applying still make sense?** {rec['could_still_apply']}", "",
          "**Experience that would increase compatibility in the future**", ""] + _bullets(rec["future_experience_to_build"])

    L += ["", "## 6. Tailored CV", ""]
    if tailored:
        L += [f"Ready-to-send PDF: `{base}.pdf` · Portal answers: `{base}_ApplicationKit.html`", "", "---", "",
              resume_markdown(resume), "---", ""]
    else:
        L += [f"_Not generated: the score is below the {threshold}% threshold._", ""]

    L += ["## 7. Change Log", ""]
    if tailored and draft:
        L += _bullets([f"**{c['change']}** — {c['reason']}" for c in draft.get("change_log", [])])
    else:
        L += ["_No resume changes (no tailored resume)._"]

    if tailored:
        L += ["", "## Integrity Check", ""]
        if issues:
            L += ["**Review before sending** — the automated check still flags these items "
                  "(numbers, tools or phrasing not traceable to your master profile):", ""] + _bullets(issues)
        else:
            L += ["Passed: every number and tool in the tailored text traces to the master profile, "
                  "skills are drawn only from your skill list, and no phrasing is copied from the posting."]

    L += ["", "## Appendix — Job Description Analysis (Step 1)", "",
          f"**Seniority:** {jd['seniority_level']}  ", f"**Industry context:** {jd['industry_context']}", "",
          "**Core responsibilities**", ""] + _bullets(jd["core_responsibilities"]) + [
          "", "**Required skills**", ""] + _bullets(jd["required_skills"]) + [
          "", "**Preferred skills**", ""] + _bullets(jd["preferred_skills"]) + [
          "", "**Tools / technologies**", ""] + _bullets(jd["tools_technologies"]) + [
          "", "**Soft skills emphasised**", ""] + _bullets(jd["soft_skills"]) + [
          "", "**Most critical requirements**", ""] + _bullets(jd["critical_requirements"]) + [""]
    return "\n".join(L)
