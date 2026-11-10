# AI Job Application Assistant

Put job postings under a Gmail label (or paste a link or the text), open this folder in Claude Code and type **`/review-jobs`**. Claude reviews each posting against your master profile the way a senior HR talent-fit analyst would and scores the fit. For good matches (65% or higher), it also builds a tailored Harvard-style resume and a copy-paste kit for Workday and similar portals.

It costs nothing beyond your Claude plan: there's no API key and no paid service. The analysis runs inside your Claude Code session; small Python scripts do everything else.

**New here? Start with [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**, a step-by-step guide for Windows and macOS that needs no programming knowledge.
For how it works under the hood (each script, the data flow, and how to rebuild it), see [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

```
/review-jobs
   │
   ├─ jobfit fetch ............ pulls new emails from Gmail label "Job Opportunities" into inbox/
   │
   ├─ Claude (per posting) .... Steps 1-4: job analysis → profile match → 5 dimension scores
   ├─ jobfit build ............ weighted score (40/25/15/10/10) → below 65%: report only
   ├─ Claude .................. Step 5: tailored resume draft
   ├─ jobfit build ............ schema + integrity checks → Claude revises if flagged → render
   │
   └─ applications/2026-01-15_SeniorDataAnalyst_AcmeLogistics/
         JaneDoe_SeniorDataAnalyst_AcmeLogistics.pdf                  ← resume (Harvard, ATS-ready)
         JaneDoe_SeniorDataAnalyst_AcmeLogistics_ApplicationKit.html  ← portal fields with Copy buttons
         JaneDoe_SeniorDataAnalyst_AcmeLogistics_FitReport.md         ← the full review (7 sections)
         analysis.json, job_posting.txt                               ← raw data, for traceability
```

When a review is finished, the Gmail message is tagged `Job Opportunities/Processed` so it's never reviewed twice. The results are emailed back to you (subject starts with `[JobFit]`), added to an optional Google Sheets tracker, and committed to Git if this folder is a Git repository with a remote.

## Using it

Open this folder in VS Code with Claude Code and type:

| You type | What happens |
|---|---|
| `/review-jobs` | Reviews every new email under the Gmail label |
| `/review-jobs samples/sample_posting.txt` | Reviews a posting saved as a text file |
| `/review-jobs https://company.com/careers/123` | Reviews a public job page |
| `/review-jobs` followed by the pasted posting text | Reviews the pasted text |

You can also just say "review my new job emails".

## How it stops fabrication

Your master profile is the only source of truth, and that rule is enforced in code as well as in the instructions:

| What | How it's enforced |
|---|---|
| Employers, titles, dates, degrees, certifications | Copied from the master profile by code. Claude only picks which ones to include, by ID. |
| Skills | Must be values from your skill list; anything else fails schema validation. |
| Metrics | Every number in the tailored text must also appear in your master profile. |
| Tools | No tool named in the posting may appear in the resume unless your profile mentions it. |
| Copying the job description | Any 8+ word phrase taken from the posting is flagged. |
| Score threshold | The weighted total is computed by code from the five dimension scores, never by Claude. |

Flagged drafts are revised (up to 2 times). Anything still flagged is listed under **Integrity Check** in the report.

## Setup in brief

The full walkthrough is in [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md). In short:

1. **Install** Python 3.10+, VS Code and the Claude Code extension (Claude Pro plan or higher). On Windows, also install Git for Windows.
2. **Fill in** [profile/master_profile.yaml](profile/master_profile.yaml) with everything you can back up. [profile/example_profile.yaml](profile/example_profile.yaml) shows a complete fictional example.
3. **Run** `/review-jobs samples/sample_posting.txt`. The first run creates the Python environment (`.venv`) automatically.
4. *Optional:* **Gmail.** Create the label `Job Opportunities` and a Google app password, then copy `.env.example` to `.env` and fill in your address and the app password.
5. *Optional:* **Google Sheets tracker.** Create a free Google Cloud service account, share a sheet with it, add its key path and the sheet ID to `.env`, then run `tracker setup`.

Without `.env`, everything still works for files, URLs and pasted text; only the Gmail and tracker steps are skipped. `.env`, `secrets/` and `inbox/` are git-ignored.

## Customising

- **[config.yaml](config.yaml):** the 65% threshold, which profile file to use, label names, page size (`letter`/`A4`), max bullets per role, and the results-email and tracker switches.
- **[prompts/analysis.md](prompts/analysis.md)** and **[prompts/tailoring.md](prompts/tailoring.md):** the analyst's instructions that Claude follows.
- **[.claude/skills/review-jobs/SKILL.md](.claude/skills/review-jobs/SKILL.md):** the `/review-jobs` procedure.
- **Score weights** (40/25/15/10/10) are in [jobfit/config.py](jobfit/config.py).

## Manual commands

Use `.venv\Scripts\python` on Windows or `.venv/bin/python` on macOS in place of `python` below. You can also just ask Claude to run them.

```bash
python -m jobfit validate                  # check the master profile
python -m jobfit fetch                     # queue new Gmail postings into inbox/
python -m jobfit add <file-or-url>         # queue one posting
python -m jobfit list                      # what's queued
python -m jobfit schema analysis           # JSON schema for Steps 1-4
python -m jobfit schema tailoring          # JSON schema for Step 5 (built from your profile)
python -m jobfit build inbox/<id>          # validate, score, check, render
python -m jobfit tracker setup             # create/format the Google Sheets tracker
python -m jobfit tracker sync              # add all saved reviews and queued jobs to it
```

## License

[MIT](LICENSE)
