"""Load and validate the master profile (the single source of truth)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ProfileError(ValueError):
    pass


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"


def _norm_date(value) -> str:
    """YAML may parse 2021-03 as a string and 2021-03-01 as a date; normalise to text."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    return str(value).strip()


def _is_blank(value) -> bool:
    """True for an empty template slot. An "id" alone doesn't count as content."""
    if isinstance(value, dict):
        return all(_is_blank(v) for k, v in value.items() if k != "id")
    if isinstance(value, list):
        return all(_is_blank(v) for v in value)
    return value is None or str(value).strip() == ""


def fmt_date(value: str, style: str = "resume") -> str:
    """'2021-03' -> 'Mar 2021' (resume) or '03/2021' (portal). 'present' passes through."""
    value = _norm_date(value)
    if not value:
        return ""
    if value.lower() in {"present", "current", "now"}:
        return "Present" if style == "resume" else ""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", value)
    if m:
        year, month = m.group(1), int(m.group(2))
        return f"{MONTHS[month - 1]} {year}" if style == "resume" else f"{month:02d}/{year}"
    return value  # free text such as "2019" or "Expected May 2026"


def is_current(value) -> bool:
    return _norm_date(value).lower() in {"present", "current", "now"}


class Profile:
    def __init__(self, data: dict, raw_text: str):
        self.data = data
        self.raw_text = raw_text
        self._assign_ids()

    @classmethod
    def load(cls, path: Path) -> "Profile":
        if not path.exists():
            raise ProfileError(f"Master profile not found: {path}")
        raw = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
            problem = str(getattr(e, "problem", e))
            tip = ("\n  Tip: wrap any value that contains a colon in quotes, e.g. "
                   'name: "Microsoft Certified: Azure Data Fundamentals"') if "mapping values" in problem else ""
            raise ProfileError(f"Master profile is not valid YAML{where}: {problem}.{tip}") from e
        profile = cls(data, raw)
        profile.validate()
        return profile

    # ------------------------------------------------------------------ ids
    def _assign_ids(self) -> None:
        for key, label_field in (
            ("experience", "company"),
            ("education", "institution"),
            ("certifications", "name"),
            ("projects", "name"),
        ):
            seen: set[str] = set()
            # Skip fully blank template slots (every field empty) so a half-finished profile still loads.
            items = [i for i in (self.data.get(key) or []) if isinstance(i, dict) and not _is_blank(i)]
            self.data[key] = items
            for i, item in enumerate(items, 1):
                item_id = str(item.get("id") or f"{_slug(item.get(label_field, key))}-{i}")
                while item_id in seen:
                    item_id = f"{item_id}-{i}"
                seen.add(item_id)
                item["id"] = item_id
                for dk in ("start", "end", "issued", "expires", "date"):
                    if dk in item:
                        item[dk] = _norm_date(item[dk])

    # ------------------------------------------------------------ validate
    def validate(self) -> None:
        problems = []
        personal = self.personal
        for f in ("full_name", "email"):
            if not personal.get(f):
                problems.append(f"personal.{f} is required")
        if not self.experience:
            problems.append("at least one experience entry is required")
        for e in self.experience:
            for f in ("title", "company", "start"):
                if not e.get(f):
                    problems.append(f"experience '{e['id']}' is missing '{f}'")
        for e in self.education:
            if not e.get("institution"):
                problems.append(f"education '{e['id']}' is missing 'institution'")
        if not self.all_skills:
            problems.append("skills: list at least one skill")
        raw_skills = self.data.get("skills") or {}
        groups = {"skills": raw_skills} if isinstance(raw_skills, list) else raw_skills
        for group, items in (groups.items() if isinstance(groups, dict) else []):
            if items is not None and not isinstance(items, list):
                problems.append(f"skills.{group}: must be a list of items (one '- item' per line)")
                continue
            for s in items or []:
                if not isinstance(s, (str, int, float)):
                    problems.append(f"skills.{group}: each item must be plain text (one '- item' per line), "
                                    f"got {s!r}. For sub-groups, make each one its own key under skills:")
                elif isinstance(s, str) and s.rstrip().endswith(","):
                    problems.append(f"skills.{group}: '{s}' ends with a comma (one skill per line, no commas)")
        if problems:
            raise ProfileError("Master profile problems:\n  - " + "\n  - ".join(problems))

    # ------------------------------------------------------------ accessors
    @property
    def personal(self) -> dict:
        return self.data.get("personal") or {}

    @property
    def full_name(self) -> str:
        return self.personal.get("full_name", "")

    @property
    def experience(self) -> list[dict]:
        return self.data.get("experience") or []

    @property
    def education(self) -> list[dict]:
        return self.data.get("education") or []

    @property
    def certifications(self) -> list[dict]:
        return self.data.get("certifications") or []

    @property
    def projects(self) -> list[dict]:
        return self.data.get("projects") or []

    @property
    def languages(self) -> list[dict]:
        return [l for l in self.data.get("languages") or [] if isinstance(l, dict) and not _is_blank(l)]

    @property
    def application_info(self) -> dict:
        return self.data.get("application_info") or {}

    @property
    def skill_groups(self) -> dict[str, list[str]]:
        skills = self.data.get("skills") or {}
        def clean(items) -> list[str]:  # blank template lines ("") are not skills
            return [str(s).strip() for s in (items or []) if not _is_blank(s)]
        if isinstance(skills, list):
            return {"skills": clean(skills)}
        return {str(k): clean(v) for k, v in skills.items() if isinstance(v, list) or v is None}

    @property
    def all_skills(self) -> list[str]:
        out: list[str] = []
        for items in self.skill_groups.values():
            for s in items:
                if s not in out:
                    out.append(s)
        return out

    def by_id(self, key: str) -> dict[str, dict]:
        return {item["id"]: item for item in self.data.get(key) or []}

    def location_line(self) -> str:
        p = self.personal
        return ", ".join(x for x in (p.get("city"), p.get("state")) if x) or p.get("country", "")

    def as_prompt_text(self) -> str:
        """The profile exactly as the model should see it (ids included)."""
        return yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True, width=120)
