# How the review-jobs workflow works

This document explains what happens when you type `/review-jobs` in Claude Code, which part of the system does each job, and what you need to build the same workflow yourself.

- **Part 1, Overview:** what the workflow does, in plain language, and one job posting followed from start to finish.
- **Part 2, Technical reference:** each script, file, schema and integration in detail.
- **Part 3, Replicating it:** a step-by-step build checklist.

For a non-technical, step-by-step setup guide, see [GETTING_STARTED.md](GETTING_STARTED.md). For day-to-day usage, see the [README](../README.md).

---

## Part 1 — Overview

### The idea

You collect job postings, for example by putting job emails under a Gmail label. The workflow reviews each one the way a senior recruiter would. It reads the posting, compares it with your **master profile** (a single file listing everything you can prove about your career) and scores the fit from 0 to 100%. When the score is 65% or higher, it also writes a resume tailored to that job, plus a page of ready-to-paste answers for the application portal.

The work is split between two parties:

| Who | Does what | Why |
|---|---|---|
| **Claude** (inside your Claude Code session) | Reads the posting and the profile, judges the fit, and writes the tailored resume text | These steps need judgement and good writing |
| **Python scripts** (the `jobfit` package) | Fetches emails, validates Claude's output, computes the score, catches invented facts, and renders the PDF and HTML files | These steps must be exact and repeatable |

Claude never writes the final files directly. It writes two structured JSON files. The scripts check those files and then build everything else. This split is what keeps the results honest: a model can be told not to invent things, but code can verify that it didn't.

The analysis runs inside your existing Claude Code session, so it needs no API key and no paid service.

### The big picture

```mermaid
flowchart TD
    A["Job email under a Gmail label<br/>(or a file, URL or pasted text)"] --> B["jobfit fetch / add<br/>queues it in inbox/"]
    B --> C["Claude: Steps 1-4<br/>writes analysis.json"]
    C --> D["jobfit build<br/>validates and computes the weighted score"]
    D -->|"below 65%"| G["Fit report only"]
    D -->|"65% or more"| E["Claude: Step 5<br/>writes tailoring.json"]
    E --> F["jobfit build<br/>schema + integrity checks"]
    F -->|"issues found"| E
    F -->|"clean"| H["Resume PDF + application kit + fit report"]
    G --> I["Saved to applications/<br/>Gmail labelled, results emailed, tracker row updated"]
    H --> I
    I --> J["Committed to Git<br/>(only if the folder has a Git remote)"]
```

### What you get for each posting

Each posting gets its own folder under `applications/`, named `<date>_<Role>_<Company>`, for example `2026-01-15_SeniorDataAnalyst_AcmeLogistics/`. The files inside start with `<Name>_<Role>_<Company>`, so a resume you upload to a portal carries your name:

| File | When | What it is |
|---|---|---|
| `…_FitReport.md` | Always | The full review: role summary, key requirements, matches and gaps, score table, recommendation, tailored CV text, change log, integrity check |
| `….pdf` | Score ≥ 65% | A one- or two-page Harvard-style resume designed to parse cleanly in applicant tracking systems (ATS) |
| `…_ApplicationKit.html` | Score ≥ 65% | Every portal field (contact details, roles, education, skills, screening answers) with a **Copy** button |
| `analysis.json` | Always | Everything Claude produced, plus the score and any integrity notes, kept for traceability |
| `job_posting.txt` | Always | The posting text exactly as it was reviewed |

### Walkthrough: one posting from start to finish

1. **You label an email.** A recruiter email lands in Gmail and you (or a Gmail filter) put it under the `Job Opportunities` label.
2. **You type `/review-jobs`.** Claude Code loads the skill file [`.claude/skills/review-jobs/SKILL.md`](../.claude/skills/review-jobs/SKILL.md), which is the step-by-step procedure Claude follows.
3. **Setup check.** Claude creates the Python environment if it's missing and runs `jobfit validate`, which stops the run if the master profile has problems.
4. **Queueing.** `jobfit fetch` logs in to Gmail and finds emails under the label that haven't been processed yet. It turns each one into plain text. If an email is only a short teaser, it follows the email's links and fetches the full job page. When the email links to several job pages, each page that loads becomes its own posting, so one email can produce several reviews; links that need a login are listed so you can paste their text instead. Before queueing, each posting is checked for duplicates (see below). Each new posting becomes a folder in `inbox/`, and a "Pending" row appears in the Google Sheets tracker.

   **Duplicate check.** A posting is skipped, before any analysis, when it is the same job as a review already saved in `applications/`, a job already waiting in `inbox/`, or another posting in the same batch. "Same job" means the same job link (ignoring tracking and language parts of the address) or at least 80% identical text. Different jobs from one company share their "About us" and benefits text but stay well below that line. An email whose jobs are all duplicates is tagged `Job Opportunities/Duplicate` so it is not fetched again, and Claude lists it in the final report. Reviews marked "Not evaluable" don't count, because their job text never loaded. `jobfit add --force` queues a posting even if it looks like a duplicate.
5. **Analysis (Steps 1–4).** Claude reads the posting, your master profile and the analyst instructions in [`prompts/analysis.md`](../prompts/analysis.md). It writes `analysis.json`, which contains:
   - what the job requires
   - which requirements you match strongly, partially or not at all, each with evidence from your profile
   - a 0–100 score for each of five dimensions
   - a recommendation: *Apply*, *Apply with caution* or *Do not apply*
6. **Scoring.** `jobfit build` checks that `analysis.json` has exactly the expected shape and computes the weighted total itself (Claude's own arithmetic is never used). Below 65%, the build goes straight to step 9.
7. **Tailoring (Step 5).** At 65% or more, Claude follows [`prompts/tailoring.md`](../prompts/tailoring.md) to write `tailoring.json`. It contains:
   - a summary
   - the roles to include, by ID, with reworded bullets
   - skill groups
   - section order
   - answers to common portal questions
   - a change log explaining each choice
8. **Integrity checks.** `jobfit build` runs again. If the draft contains a number that isn't in your profile, a tool from the posting that you don't have, or a long phrase copied from the posting, the build rejects it and Claude revises it, up to two times.
9. **Rendering and bookkeeping.** `jobfit build` writes the report, PDF and kit to `applications/`, tags the Gmail message `Job Opportunities/Processed` so it's never reviewed twice (for an email with several jobs, after the last one is built), emails you the results (subject starting `[JobFit]`), updates the tracker row and clears the item from `inbox/`.
10. **Save and report.** If the folder is a Git repository with a remote, Claude commits and pushes the new `applications/` folders. Either way, it shows you a short summary table: role, company, score, recommendation, and whether a resume was generated.

---

## Part 2 — Technical reference

### Technology stack

| Piece | Used for |
|---|---|
| [Claude Code](https://claude.com/claude-code) | Runs the `/review-jobs` skill; Claude does the analysis and writing |
| Python 3.12 (3.10+ should work) | The `jobfit` package |
| `PyYAML` | Reading `config.yaml` and the master profile |
| `jsonschema` | Validating Claude's JSON output (Draft 2020-12) |
| `requests`, `beautifulsoup4` | Fetching job pages and converting HTML to text |
| `reportlab` | Generating the resume PDF |
| `gspread`, `google-auth` | Writing to the Google Sheets tracker |
| Python standard library `imaplib` / `smtplib` | Reading and labelling Gmail and sending the results email |

### Repository layout

```
.claude/skills/review-jobs/SKILL.md   the /review-jobs procedure Claude follows
prompts/analysis.md                   analyst instructions for Steps 1-4
prompts/tailoring.md                  resume-strategist instructions for Step 5
CLAUDE.md                             standing instructions Claude Code loads automatically
profile/master_profile.yaml           your career facts: the single source of truth
profile/master_profile.template.yaml  blank, commented template (the public repository ships it as master_profile.yaml)
profile/example_profile.yaml          a complete fictional profile, for reference and test drives
config.yaml                           thresholds, labels, page size, feature switches
.env                                  credentials (git-ignored; template in .env.example)
secrets/                              Google service-account key (git-ignored)
jobfit/                               the Python package (CLI + all mechanics)
inbox/                                work in progress, one folder per posting (git-ignored)
applications/                         finished reviews (committed)
samples/sample_posting.txt            a fictional posting for testing
docs/                                 GETTING_STARTED.md (setup guide) and this document
tools/publish_public.py               maintainer-only: exports the sanitised public repository (not published)
```

### The work item lifecycle

Every posting is a folder in `inbox/` that collects files as it moves through the pipeline:

| File | Written by | Contents |
|---|---|---|
| `posting.txt` | `fetch` / `add` | The job text (email body, plus a fetched page if the email was short) |
| `meta.json` | `fetch` / `add` | Source, creation time, item ID; for Gmail, also the message UID, subject and date |
| `analysis.json` | Claude | Steps 1–4, matching the analysis schema |
| `tailoring.json` | Claude | Step 5, matching the tailoring schema (only when score ≥ threshold) |

`jobfit build` is designed to be called again and again. Each call looks at which files exist and whether they're valid, then returns a **status** that tells Claude what to do next:

```mermaid
stateDiagram-v2
    [*] --> needs_analysis
    needs_analysis --> invalid_analysis: analysis.json fails schema
    needs_analysis --> done: valid, score below threshold
    needs_analysis --> needs_tailoring: valid, score at/above threshold
    invalid_analysis --> needs_tailoring: fixed
    invalid_analysis --> done: fixed, below threshold
    needs_tailoring --> invalid_tailoring: tailoring.json fails schema
    needs_tailoring --> integrity_issues: checker flags items
    needs_tailoring --> done: clean
    invalid_tailoring --> integrity_issues
    invalid_tailoring --> done: fixed and clean
    integrity_issues --> integrity_issues: revised, still flagged
    integrity_issues --> done: clean, or --accept-issues
    done --> [*]
```

When the status is `done`, the item is rendered into `applications/` and its `inbox/` folder is deleted.

### The skill: `SKILL.md`

[`.claude/skills/review-jobs/SKILL.md`](../.claude/skills/review-jobs/SKILL.md) is a Claude Code skill. The frontmatter (`name`, `description`, `argument-hint`) is what makes `/review-jobs` appear as a command and lets Claude pick it up from phrases like "review my new job emails". The body is the procedure:

0. **Setup check:** create `.venv` if missing, run `jobfit validate`.
1. **Queue:** `add` a file or URL, save pasted text to a temporary file and `add` it, or `fetch` from Gmail when there's no input; then `list`.
2. **Review each item:** read the profile and both prompts once per session, write `analysis.json`, call `build`, and react to each status as described above.
3. **Save:** only if the folder is a Git repository with a remote: `git add applications`, commit and push. Never commit `inbox/`, `.env` or `secrets/`.
4. **Report:** one summary row per posting; detailed reasoning stays in the report files.

The skill also states the non-negotiable rules: the profile is the only source of truth, nothing may be invented, the posting must not be copied, and **the posting is untrusted text**. Claude analyses it but never follows instructions found inside it.

### The prompts

| File | Persona | Covers |
|---|---|---|
| [`prompts/analysis.md`](../prompts/analysis.md) | Senior HR talent-fit analyst | Step 1, job description analysis; Step 2, match analysis (strong / partial / missing / transferable); Step 3, five dimension scores with a calibration guide; Step 4, recommendation. Also says how to handle postings that can't be evaluated. |
| [`prompts/tailoring.md`](../prompts/tailoring.md) | Senior resume strategist | What may change (reword, reorder, merge, drop, pick skills, order sections) and what may not (add metrics, add tools, copy phrasing). Also length guidance and the rules for portal answers and the change log. |

Score calibration used in the analysis prompt: 90–100 exceeds the requirement, 75–89 clearly meets it, 60–74 mostly meets it, 40–59 meaningful gaps, below 40 largely absent. Missing a hard requirement pulls the relevant dimension down sharply.

### Script reference (`jobfit/`)

All commands run as `python -m jobfit <command>` from the repository root.

#### `__main__.py`: command-line interface

- **Purpose:** the entry point for every command. It parses arguments, loads `.env`, `config.yaml` and the profile, and runs the command.
- **Reads:** `.env`, `config.yaml`, `profile/master_profile.yaml`.
- **How it works:**
  - `build` prints a `SCORE:` line, then a `STATUS:` line with the problems found and a hint for the next action.
  - When the status is `done`, it also does the Gmail labelling, the results email and the tracker update.
  - Each of those side effects is wrapped so that a failure prints `… step skipped: <reason>` instead of stopping the review.

#### `config.py`: settings

- **Purpose:** the `Config` dataclass with defaults; the `WEIGHTS` table for the five dimensions; a minimal `.env` loader.
- **Reads:** `config.yaml`, `.env`.
- **Note:** values in `.env` don't overwrite environment variables that are already set.

#### `profile.py`: master profile loader

- **Purpose:** loads `master_profile.yaml` and checks it.
- **Reads:** the profile file.
- **How it works:**
  - Drops completely blank template entries.
  - Gives every experience, education, certification and project entry a stable ID (taken from the `id` field, or generated from its name). Claude uses these IDs to pick entries.
  - Normalises dates: `2021-03` stays `2021-03`, and `present` marks the current role.
  - Checks that the required fields exist (full name, email, at least one role with title, company and start date, at least one skill).
  - Turns YAML syntax errors into plain-language messages, including the common "unquoted colon" mistake.
  - Keeps the raw file text so the integrity checker can search it.

#### `pipeline.py`: inbox and build orchestration

- **Purpose:** creates, lists and removes work items, and runs `build`.
- **Reads:** `inbox/<id>/*`.
- **Writes:** `inbox/<id>/posting.txt` and `meta.json` (`new_item`), plus everything in `applications/<folder>/`.
- **How `build` works:**
  1. Validates the analysis against the schema.
  2. Computes the score and band.
  3. Decides whether tailoring is needed (evaluable **and** score ≥ threshold).
  4. If it is: validates the tailoring, runs the integrity checks and merges the draft with the profile.
  5. Renders the report, PDF and kit, and saves the posting and a combined `analysis.json`.

  Folder names get a `-2`, `-3`… suffix if they already exist.

#### `schemas.py`: JSON contracts

- **Purpose:** defines the exact JSON shapes Claude must produce, and validates them.
- **Analysis schema:** these sections:
  - `job`: title, company, location, publish date in `YYYY-MM-DD` format, and whether the posting can be evaluated
  - `jd_analysis`
  - `role_summary`
  - `key_requirements`
  - `match`
  - `scores`: one score and rationale for each of the five dimensions
  - `score_explanation`
  - `recommendation`: decision restricted to three values

  Unknown fields are rejected.
- **Tailoring schema:** built at run time from the profile. Experience, education, certification and project IDs, and every skill, are **enums**: lists of the only values allowed. A draft that names a role or skill not in the profile fails validation before any text is checked.
- `jobfit schema analysis|tailoring` prints the schema so Claude can follow it exactly.

#### `scoring.py`: weighted score and bands

- **Purpose:** computes the score of record.
- **Formula:** each dimension score is clamped to 0–100, then weighted:

  | Dimension | Weight |
  |---|---:|
  | Relevant experience | 40% |
  | Skills alignment | 25% |
  | Tools / technologies | 15% |
  | Industry context | 10% |
  | Soft skills | 10% |

- **Bands:** 90+ Exceptional, 80+ Strong, 70+ Good, 60+ Moderate, 50+ Weak, below 50 Poor. A posting that can't be evaluated is labelled "Not evaluable" and never tailored.

#### `guard.py`: integrity checks

- **Purpose:** deterministic checks on the tailored text: the summary, every bullet and every portal answer.
- **Checks:**
  1. **Numbers:** every number in the draft must also appear somewhere in the master profile.
  2. **Tools:** every tool the posting names (from `jd_analysis.tools_technologies`, up to 4 words each) may appear in the draft only if the profile mentions it too. Matching is case-insensitive and whole-word.
  3. **Copied phrasing:** the draft and the posting are split into overlapping 8-word sequences; any sequence they share is flagged.
- **Output:** a list of plain-language issues, quoting the offending text.

#### `resume.py`: resume assembly

- **Purpose:** merges Claude's draft with facts from the profile into one resume structure.
- **How it works:**
  - Employers, titles, locations, dates, degrees and certifications are **copied from the profile by ID**. Claude only supplies bullet text and choices.
  - Roles are sorted newest first (Harvard style), with every role at the same company kept together under a single company heading. Companies are ordered by their most recent role. So relevance shows in the order of bullets within each role, not the order of roles.
  - Bullets are capped at `max_bullets_per_role`.
  - Skills not in the profile are dropped.
  - Sections Claude didn't list are appended in a default order.
- Also produces a Markdown version of the resume for the report.

#### `render_pdf.py`: resume PDF

- **Purpose:** renders the resume as a PDF with ReportLab.
- **ATS-friendly layout:**
  - single column
  - real, selectable text in reading order
  - standard section headings
  - no tables, images, text boxes or headers/footers
  - simple bullets
- **Fonts:** embeds Times New Roman on Windows and macOS, or Liberation Serif / DejaVu Serif on Linux. Otherwise it falls back to the built-in Times, which only covers Western European characters, so other characters are transliterated.
- **Links:** email, LinkedIn, GitHub, website and project URLs are printed as visible text without `https://` (for example `github.com/JaneDoe`) and are also clickable. ATS parsers read the visible text; nothing is hidden behind icons or link words.
- **Contact line:** city, state and country, phone, email and links, all from `personal` in the profile.
- **Page:** Letter or A4, 0.7″ side margins, 10.5 pt body text.

#### `render_kit.py`: application kit

- **Purpose:** a self-contained HTML page for filling in Workday, Greenhouse, Lever and similar portals.
- **Sections:**
  - My Information
  - My Experience (with portal-format dates `MM/YYYY`)
  - Education
  - Certifications
  - Languages
  - Skills (one clickable chip per skill, since Workday adds skills one at a time)
  - Application Questions (from `application_info` in the profile, plus Claude's tailored answers, with character counts)
  - Files
- Empty fields are shown as "Not in master profile — fill manually". Voluntary disclosures (gender, ethnicity, veteran, disability) are deliberately not stored.

#### `render_report.py`: fit report

- **Purpose:** writes the Markdown fit report in a fixed structure:
  1. Role Summary
  2. Key Job Requirements
  3. Profile Match Analysis
  4. Job Fit Score (table with per-dimension weighted values)
  5. Strategic Recommendation
  6. Tailored CV
  7. Change Log

  It then adds an Integrity Check section and an appendix with the full job description analysis.

#### `job_text.py`: posting extraction

- **Purpose:** turns an email or URL into plain text.
- **How it works:**
  - Uses the email's plain-text part, or converts the HTML part if the text is very short.
  - If the body is under 1,200 characters, it follows the email's links, skipping unsubscribe, privacy and image links:
    - **Job links** (a `/jobs/` or `/careers/` style address, or a known job board such as Greenhouse, Lever, Workday or SmartRecruiters): each one is fetched, up to 10, and every page with enough text becomes a separate posting. Links that don't load are reported.
    - **Other links:** up to 3 are tried, and the first page with enough text is appended.
  - HTML is cleaned by removing scripts, styles, navigation, headers and footers.
- **Limitation:** pages behind a login wall can't be read, and the page is fetched without running JavaScript.

#### `duplicates.py`: duplicate check

- **Purpose:** stops the same job from being analysed twice.
- **How it works:**
  - Compares each new posting with every saved review in `applications/` (its `job_posting.txt` and the source link in `analysis.json`), every job waiting in `inbox/`, and the postings queued earlier in the same `fetch`.
  - **Same link:** the job page address, with tracking and language parameters (`utm_…`, `lang`, `ref`…), `www.` and trailing slashes removed.
  - **Same text:** the share of 5-word sequences the two postings have in common (Jaccard similarity) is at least 80%. Measured on real postings, re-sent copies of a job score about 97–99%, while different jobs from the same company score under 50%.
  - It deliberately doesn't ask whether one text is *contained* in the other: two careers pages that failed to load share all their menu text and would look like the same job.
- **Limitation:** the same job posted on two different sites (say, LinkedIn and the company page) with different wording is not caught.

#### `gmail_client.py`: Gmail over IMAP/SMTP

- **Purpose:** reads the label, marks messages processed, and sends the results email.
- **Why IMAP instead of the Gmail API:** an app password is enough, so there's no Google Cloud project or OAuth consent screen. Gmail shows each label as an IMAP folder and supports the `X-GM-LABELS` extension for adding labels.
- **How it works:**
  - **Fetching:** skips messages that already carry the processed, error or duplicate label, are already queued in `inbox/`, or start with `[JobFit]` (its own results emails). Messages are read with `BODY.PEEK`, so they stay unread.
  - **Results email:** sent to yourself over SMTP with the report, PDF and kit attached. The script then finds that email through Gmail search (retrying for up to 60 seconds) and applies the results label.

#### `tracker.py`: Google Sheets tracker

- **Purpose:** keeps one row per job in a Google Sheet.
- **How it works:**
  - Rows are keyed by a hidden **Tracker ID** (the inbox item ID). If the ID isn't found, rows are matched on company + role.
  - The workflow fills company, role, dates, score, recommendation, summary, link, requirements and matches.
  - **Stage** belongs to you. The workflow only moves it from blank to *Processed by Claude* and never overwrites a stage you set.
  - **Stage Met** (1–11) and **Status** (Pending / Open / Closed) are sheet formulas based on the Stage, and Status is colour-coded.
  - `tracker setup` creates and formats the layout: column widths, frozen columns, the stage dropdown and conditional colours.
  - `tracker sync` backfills every saved review and every queued item.
  - Text that starts with `=`, `+`, `-` or `@` is escaped so Sheets doesn't treat it as a formula.
  - Uses gspread's back-off client to retry automatically when Google's per-minute limit is hit.

#### `naming.py`: file names

- **Purpose:** builds the output names. Folders are `date_JobPosition_CompanyName` (for example `2026-01-15_SeniorDataAnalyst_AcmeLogistics`); the files inside are `Name_JobPosition_CompanyName` (for example `JaneDoe_SeniorDataAnalyst_AcmeLogistics.pdf`). Each part is converted to ASCII, written in CamelCase and capped at 40 characters.

### Command reference

| Command | What it does |
|---|---|
| `jobfit validate` | Checks the master profile and prints a one-line summary |
| `jobfit fetch` | Queues new emails from the Gmail label (up to `max_per_run`); duplicates are skipped and labelled |
| `jobfit add <file-or-url> [--force]` | Queues one posting from a text file or a public URL; skips duplicates unless `--force` |
| `jobfit list` | Lists queued items and whether each has an analysis and a tailoring |
| `jobfit schema analysis` | Prints the JSON schema for Steps 1–4 |
| `jobfit schema tailoring` | Prints the JSON schema for Step 5, built from your profile |
| `jobfit build inbox/<id> [--accept-issues]` | Validates, scores, checks and renders; prints the next status |
| `jobfit tracker setup` | Creates and formats the tracker sheet |
| `jobfit tracker sync` | Adds every saved review and queued item to the tracker |

### Configuration

**`config.yaml`** (committed):

| Key | Default | Meaning |
|---|---|---|
| `fit_threshold` | `65` | Minimum weighted score that triggers tailoring |
| `profile_path` | `profile/master_profile.yaml` | Where the master profile lives |
| `output_dir` | `applications` | Where finished reviews are saved |
| `resume.page_size` | `letter` | `letter` or `A4` |
| `resume.max_bullets_per_role` | `6` | Bullet cap per role |
| `gmail.source_label` | `Job Opportunities` | Label to read job emails from |
| `gmail.processed_label` | `Job Opportunities/Processed` | Added after a review |
| `gmail.error_label` | `Job Opportunities/Error` | Messages with this label are skipped |
| `gmail.duplicate_label` | `Job Opportunities/Duplicate` | Added to an email whose job was already reviewed or queued; such messages are skipped |
| `gmail.max_per_run` | `5` | Maximum emails queued per `fetch` |
| `notify.email_results` | `true` | Email the results to yourself |
| `notify.results_label` | `Job Opportunities/JobFit` | Label for the results email (`""` to skip) |
| `tracker.enabled` | `true` | Turn the Google Sheets tracker on or off |

**`.env`** (git-ignored, copied from [`.env.example`](../.env.example)):

| Variable | Needed for |
|---|---|
| `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | Gmail fetch, labels and results email |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Tracker: path to the service-account JSON key, kept in `secrets/` |
| `GOOGLE_SHEET_ID` | Tracker: the ID from the sheet URL |

The weights (40/25/15/10/10) live in `WEIGHTS` in [`jobfit/config.py`](../jobfit/config.py).

### The master profile format

The profile is a YAML file. Only `personal.full_name`, `personal.email`, at least one experience entry (with `title`, `company`, `start`) and at least one skill are required. Everything else is optional. A fictional example:

```yaml
personal:
  full_name: Jane Doe
  first_name: Jane
  last_name: Doe
  email: jane.doe@example.com
  phone: "+1 555 0100"
  address_line: 123 Example St
  city: Springfield
  state: IL
  postal_code: "00000"
  country: United States
  linkedin: linkedin.com/in/janedoe-example
  website: ""
  github: ""

professional_profile: >
  Data analyst with six years of experience turning operational data into reporting...

experience:
  - id: acme-analyst            # optional; generated from the company name if omitted
    title: Senior Data Analyst
    company: Acme Logistics
    location: Springfield, IL
    employment_type: Full-time
    start: 2021-03              # YYYY-MM
    end: present
    bullets:
      - Built a weekly operations dashboard used by 40 managers
      - Cut report preparation time by 30% by automating data refreshes

education:
  - institution: Example State University
    degree: B.S.
    field: Economics
    location: Springfield, IL
    start: 2014-09
    end: 2018-05
    gpa: ""
    honors: ""
    details: []

certifications:
  - name: "Example Cloud: Data Fundamentals"   # quote values that contain a colon
    issuer: Example Corp
    issued: 2023-06
    expires: ""
    credential_id: ""
    url: ""

skills:                         # groups are free-form; each item is one skill
  analytics: [SQL, Python, Excel]
  visualization: [Power BI, Tableau]

languages:
  - language: English
    proficiency: Native

projects: []                    # optional: name, date, url, bullets

application_info:               # used only by the application kit
  work_authorization: ""
  requires_sponsorship: ""
  willing_to_relocate: ""
  notice_period: ""
  desired_salary: ""
  earliest_start_date: ""
  pronouns: ""
```

The integrity checker searches the **whole file as text**, so a number or tool counts as "in the profile" wherever it appears, whether in a bullet, the summary or a skill list. List every tool, skill and real metric you can back up: the tailoring step can only use what is here.

### How fabrication is prevented

The workflow uses several layers of protection. Each one catches what the previous one might miss:

| Layer | Mechanism | Stops |
|---|---|---|
| Instructions | `SKILL.md` and both prompts forbid inventing, exaggerating or copying | Most problems, before they happen |
| Copied facts | Employers, titles, dates, degrees and certifications are copied from the profile by code; Claude only picks IDs | Invented or altered roles, dates and credentials |
| Enum-locked schema | IDs and skills must be values from the profile | Invented skills or entries |
| Number check | Every number in the draft must appear in the profile | Made-up metrics |
| Tool check | Tools named in the posting must be in the profile to appear in the draft | Keyword stuffing from the posting |
| Phrase check | No 8-word sequence shared with the posting | Copied job-description text |
| Code-computed score | The weighted total and threshold are computed in Python | Score inflation to reach 65% |
| Revision loop | Up to 2 revisions; anything left over is listed under **Integrity Check** in the report | Silent acceptance of flagged items |

### Error handling

The core review never depends on the optional integrations:

- **No `.env`:** files, URLs and pasted text still work. Gmail fetch, labels and the results email are skipped with a printed reason.
- **Tracker not configured or unreachable:** prints `Tracker step skipped: …` and the review continues.
- **Invalid profile:** the run stops at the setup check with a list of specific problems.
- **Email with several job links:** each job page that loads is reviewed separately; the email is marked processed after the last one.
- **Posting that isn't a single job** (for example a digest of many job titles with no readable job pages): Claude marks it not evaluable. It still gets a report, and the email is still marked processed.
- **Page behind a login wall:** `add <url>` asks you to save the text to a file instead.

---

## Part 3 — Replicating it

### What you need

- A Claude plan with **Claude Code** (CLI, desktop app or VS Code extension).
- **Python 3.10+** (built and tested with 3.12) on Windows or macOS. Linux should also work but is untested.
- **Git:** required by Claude Code on Windows; otherwise only needed if you want results versioned.
- *Optional:* a Gmail account with 2-Step Verification, for the email integration.
- *Optional:* a free Google Cloud project, for the Sheets tracker. No billing account is needed.

### Build steps

1. **Get the code.** Clone this repository, or recreate the layout shown in [Repository layout](#repository-layout).
2. **Create the environment:**
   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install -r requirements.txt   # Windows
   .venv/bin/python -m pip install -r requirements.txt       # macOS / Linux
   ```
   You can skip this step: `/review-jobs` creates the environment on its first run. The skill and `CLAUDE.md` tell Claude to use `.venv/Scripts/python` on Windows and `.venv/bin/python` on macOS and Linux.
3. **Write your master profile** in `profile/master_profile.yaml`, following the [format above](#the-master-profile-format), then run `python -m jobfit validate` until it prints `OK`.
4. **Check `.gitignore`.** It must include `.env`, `inbox/`, `secrets/` and `*service-account*.json`, so credentials and work in progress never reach Git.
5. **Test without any integrations.** In Claude Code, run `/review-jobs samples/sample_posting.txt`. You should get a folder in `applications/` containing a report (and a PDF and kit if the score is 65% or more).
6. **Optional: Gmail.** Create the `Job Opportunities` label. Create an app password at Google Account → Security → App passwords. Copy `.env.example` to `.env` and fill in `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`. Then run `/review-jobs` with no arguments. If you use a Gmail filter, make sure it doesn't match subjects starting with `[JobFit]`.
7. **Optional: tracker.**
   1. In Google Cloud, create a project and enable the **Google Sheets API**.
   2. Create a service account and download its JSON key into `secrets/`.
   3. Create a blank Google Sheet and share it as **Editor** with the service account's `client_email`.
   4. Add `GOOGLE_SERVICE_ACCOUNT_FILE` and `GOOGLE_SHEET_ID` to `.env`.
   5. Run `python -m jobfit tracker setup`, then `python -m jobfit tracker sync`.

   [GETTING_STARTED.md](GETTING_STARTED.md#6-optional-set-up-the-google-sheets-tracker) has click-by-click instructions.
8. **Optional: Git remote.** If the folder is a Git repository with a remote, the skill commits and pushes `applications/` after each run; otherwise it skips that step. If you add a remote, make it a **private** repository, since reviews contain your career details.

### Adapting it

| To change | Edit |
|---|---|
| The threshold, labels, page size, bullet cap, email or tracker switches | [`config.yaml`](../config.yaml) |
| The dimension weights | `WEIGHTS` in [`jobfit/config.py`](../jobfit/config.py), and the matching text in `prompts/analysis.md` |
| How Claude analyses or writes | [`prompts/analysis.md`](../prompts/analysis.md), [`prompts/tailoring.md`](../prompts/tailoring.md) |
| The overall procedure | [`.claude/skills/review-jobs/SKILL.md`](../.claude/skills/review-jobs/SKILL.md) |
| Report sections, resume look, or kit fields | `render_report.py`, `render_pdf.py`, `render_kit.py` |
| Integrity strictness (for example the 8-word phrase length) | `SHINGLE` and the checks in [`jobfit/guard.py`](../jobfit/guard.py) |
| How alike two postings must be to count as duplicates | `SIMILARITY` in [`jobfit/duplicates.py`](../jobfit/duplicates.py) |

When you change the weights or the threshold, update the prompt text too. Claude is told the weights so its recommendation stays consistent with the computed score.
