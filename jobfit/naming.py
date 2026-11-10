from __future__ import annotations

import re
import unicodedata


def _part(text: str, limit: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"(?<=[A-Za-z])['’](?=[A-Za-z])", "", text)  # Moody's -> Moodys, not MoodyS
    words = re.findall(r"[A-Za-z0-9]+", text)
    joined = "".join(w[:1].upper() + w[1:] for w in words)
    return joined[:limit] or "Unknown"


def base_name(full_name: str, job_title: str, company: str) -> str:
    """Name_JobPosition_CompanyName, e.g. JaneDoe_SeniorDataAnalyst_AcmeLogistics."""
    return f"{_part(full_name)}_{_part(job_title)}_{_part(company)}"


def folder_name(date: str, job_title: str, company: str) -> str:
    """Output folder: date_JobPosition_CompanyName, e.g. 2026-01-15_SeniorDataAnalyst_AcmeLogistics."""
    return f"{date}_{_part(job_title)}_{_part(company)}"
