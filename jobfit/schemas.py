"""JSON schemas for the two analysis outputs Claude writes during /review-jobs.

The tailoring schema is built from the master profile: experience, education,
certification and project IDs and every skill are enums, so a draft that
names anything not in the profile fails validation.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

from .config import WEIGHTS
from .profile import Profile


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required if required is not None else list(props),
        "additionalProperties": False,
    }


STR = {"type": "string"}
STR_LIST = {"type": "array", "items": STR}


def analysis_schema() -> dict:
    dim = _obj({"score": {"type": "integer"}, "rationale": STR})
    return _obj({
        "job": _obj({
            "title": STR,
            "company": STR,
            "location": STR,
            "date_published": {
                "type": "string", "pattern": r"^(\d{4}-\d{2}-\d{2})?$",
                "description": "Posting date as YYYY-MM-DD if the posting states it (convert relative dates such "
                               "as '3 days ago' using the email/fetch date); empty string if unknown.",
            },
            "is_evaluable": {"type": "boolean"},
            "not_evaluable_reason": STR,
        }),
        "jd_analysis": _obj({
            "core_responsibilities": STR_LIST,
            "required_skills": STR_LIST,
            "preferred_skills": STR_LIST,
            "tools_technologies": {
                "type": "array", "items": STR,
                "description": "Named tools, platforms, languages, frameworks or methodologies, one short term each.",
            },
            "industry_context": STR,
            "seniority_level": STR,
            "soft_skills": STR_LIST,
            "critical_requirements": STR_LIST,
        }),
        "role_summary": STR,
        "key_requirements": {"type": "array", "items": STR, "description": "Top 8 requirements."},
        "match": _obj({
            "strong_matches": {"type": "array", "items": _obj({"requirement": STR, "evidence": STR})},
            "partial_matches": {"type": "array", "items": _obj({"requirement": STR, "evidence": STR, "gap": STR})},
            "missing_requirements": {"type": "array", "items": _obj({
                "requirement": STR,
                "importance": {"type": "string", "enum": ["critical", "important", "nice-to-have"]},
            })},
            "transferable_strengths": {"type": "array", "items": _obj({"strength": STR, "why_it_matters": STR})},
        }),
        "scores": _obj({k: dim for k in WEIGHTS}),
        "score_explanation": STR,
        "recommendation": _obj({
            "decision": {"type": "string", "enum": ["Apply", "Apply with caution", "Do not apply"]},
            "rationale": STR,
            "key_skill_gaps": STR_LIST,
            "could_still_apply": STR,
            "future_experience_to_build": STR_LIST,
        }),
    })


def tailoring_schema(profile: Profile) -> dict:
    def enum_list(values: list[str]) -> dict:
        return {"type": "array", "items": {"type": "string", "enum": values}}

    sections = ["summary", "experience", "education", "skills"]
    props: dict = {
        "summary": STR,
        "experience": {"type": "array", "items": _obj({
            "experience_id": {"type": "string", "enum": [e["id"] for e in profile.experience]},
            "bullets": STR_LIST,
        })},
        "skill_groups": {"type": "array", "items": _obj({
            "label": STR,
            "items": enum_list(profile.all_skills),
        })},
    }
    if profile.education:
        props["education_ids"] = enum_list([e["id"] for e in profile.education])
    if profile.certifications:
        props["certification_ids"] = enum_list([c["id"] for c in profile.certifications])
        sections.append("certifications")
    if profile.projects:
        props["projects"] = {"type": "array", "items": _obj({
            "project_id": {"type": "string", "enum": [p["id"] for p in profile.projects]},
            "bullets": STR_LIST,
        })}
        sections.append("projects")
    if profile.languages:
        props["include_languages"] = {"type": "boolean"}
    props["section_order"] = enum_list(sections)
    props["application_answers"] = {"type": "array", "items": _obj({"question": STR, "answer": STR})}
    props["change_log"] = {"type": "array", "items": _obj({"change": STR, "reason": STR})}
    return _obj(props)


def validate(data: dict, schema: dict) -> list[str]:
    """Return human-readable schema violations (empty list = valid)."""
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in errors]
