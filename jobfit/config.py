from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import ROOT

WEIGHTS = {
    "relevant_experience": 40,
    "skills_alignment": 25,
    "tools_technologies": 15,
    "industry_context": 10,
    "soft_skills": 10,
}


def load_env(path: Path | None = None) -> None:
    """Load KEY=value lines from the git-ignored .env file into the environment (if present)."""
    import os
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    fit_threshold: int = 65
    profile_path: Path = ROOT / "profile" / "master_profile.yaml"
    output_dir: Path = ROOT / "applications"
    page_size: str = "letter"
    max_bullets_per_role: int = 6
    source_label: str = "Job Opportunities"
    processed_label: str = "Job Opportunities/Processed"
    error_label: str = "Job Opportunities/Error"
    max_per_run: int = 5
    email_results: bool = True
    results_label: str = "Job Opportunities/JobFit"
    tracker_enabled: bool = True
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or ROOT / "config.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        resume = data.get("resume", {}) or {}
        gmail = data.get("gmail", {}) or {}
        notify = data.get("notify", {}) or {}
        c = cls(raw=data)
        c.fit_threshold = int(data.get("fit_threshold", c.fit_threshold))
        c.profile_path = ROOT / data.get("profile_path", "profile/master_profile.yaml")
        c.output_dir = ROOT / data.get("output_dir", "applications")
        c.page_size = resume.get("page_size", c.page_size)
        c.max_bullets_per_role = int(resume.get("max_bullets_per_role", c.max_bullets_per_role))
        c.source_label = gmail.get("source_label", c.source_label)
        c.processed_label = gmail.get("processed_label", c.processed_label)
        c.error_label = gmail.get("error_label", c.error_label)
        c.max_per_run = int(gmail.get("max_per_run", c.max_per_run))
        c.email_results = bool(notify.get("email_results", c.email_results))
        c.results_label = str(notify.get("results_label", c.results_label) or "")
        tracker = data.get("tracker", {}) or {}
        c.tracker_enabled = bool(tracker.get("enabled", c.tracker_enabled))
        return c
