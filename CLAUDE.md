# AI Job Application Assistant

Users of this folder may not be technical: explain things plainly, avoid jargon, and say what a command will do before asking to run it.

- **Main command:** `/review-jobs` (procedure in `.claude/skills/review-jobs/SKILL.md`).
- **Python:** always use the virtual environment, `.venv/Scripts/python` on Windows or `.venv/bin/python` on macOS/Linux. If `.venv/` doesn't exist yet, create it first (`python -m venv .venv`, or `python3` on macOS) and install `requirements.txt` into it.
- **Commands:** `-m jobfit validate | fetch | add | list | schema | build | tracker setup | tracker sync`. The README's "Manual commands" section explains each one.
- **Master profile:** the file named by `profile_path` in `config.yaml` (normally `profile/master_profile.yaml`). It is the only source of truth about the user. When asked to fill it in from a resume, use only facts stated in that resume; leave the rest as `""`, then run `validate`.
- **Secrets:** never ask the user to paste passwords, app passwords or key files into the chat; they go in `.env` and `secrets/` by hand (see `docs/GETTING_STARTED.md`).
- **Setup help:** `docs/GETTING_STARTED.md` (step by step); **design:** `docs/HOW_IT_WORKS.md`.
