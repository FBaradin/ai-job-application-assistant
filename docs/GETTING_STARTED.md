# Getting started

This guide takes you from nothing to your first job review, one step at a time. You don't need to know how to program. Claude does the technical work, and you approve each step with a click.

It works on **Windows** and **macOS**. Where the steps differ, both versions are shown.

**Time needed:** about 30 minutes for the basics. Connecting Gmail adds 10 minutes, and the Google Sheets tracker adds 20.

| Part | What you'll do | Needed? |
|---|---|---|
| [1. Install the tools](#1-install-the-tools) | Install Python, VS Code and Claude Code | Yes |
| [2. Get the workflow](#2-get-the-workflow) | Download this folder and open it | Yes |
| [3. Fill in your master profile](#3-fill-in-your-master-profile) | Describe your career in one file | Yes |
| [4. Review your first job](#4-review-your-first-job) | Run `/review-jobs` | Yes |
| [5. Connect Gmail](#5-optional-connect-gmail) | Review job emails automatically | Optional |
| [6. Set up the Google Sheets tracker](#6-optional-set-up-the-google-sheets-tracker) | Keep one row per job in a spreadsheet | Optional |
| [Troubleshooting](#troubleshooting) | Fixes for common problems | — |

> **Your data stays on your computer.** Your profile, reviews and passwords are saved only in this folder. The Gmail and Google steps connect directly from your computer to your own Google account. The review itself happens in your Claude Code session, under your Claude account.

---

## 1. Install the tools

### 1.1 A Claude subscription

Claude Code needs a paid Claude plan (**Pro** or higher). If you don't have one, sign up at <https://claude.ai> and choose a plan. There's nothing else to pay for: the workflow uses no other paid services.

### 1.2 Python

Python runs the small helper programs that create the PDF and handle Gmail.

**Windows**
1. Go to <https://www.python.org/downloads/> and click the yellow **Download Python 3.x** button.
2. Open the downloaded file.
3. On the first screen, **tick "Add python.exe to PATH"** at the bottom. This matters.
4. Click **Install Now** and wait for it to finish.

**macOS**
1. Go to <https://www.python.org/downloads/> and click **Download Python 3.x**.
2. Open the downloaded `.pkg` file and click through the installer (Continue → Agree → Install).

### 1.3 Git (Windows only)

Claude Code on Windows needs Git for Windows.

1. Go to <https://git-scm.com/downloads/win> and download the installer.
2. Run it and accept every default option (just keep clicking **Next**, then **Install**).

On macOS, skip this step.

### 1.4 Visual Studio Code

VS Code is a free editor. It's where you'll see your files and talk to Claude.

1. Go to <https://code.visualstudio.com/> and download it for your system.
2. **Windows:** run the installer and accept the defaults.
   **macOS:** open the downloaded `.zip` and drag **Visual Studio Code** into your **Applications** folder.
3. Open VS Code.

### 1.5 The Claude Code extension

1. In VS Code, click the **Extensions** icon in the left bar (four small squares), or press `Ctrl+Shift+X` (Windows) / `Cmd+Shift+X` (macOS).
2. Search for **Claude Code** and install the extension published by **Anthropic**.
3. A Claude icon appears. Click it to open the Claude panel, then sign in with your Claude account when asked.

---

## 2. Get the workflow

1. Go to this repository's main page on GitHub (the page that shows the README).
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip the download:
   - **Windows:** right-click the ZIP → **Extract All…**
   - **macOS:** double-click it.
4. You now have a folder called **`ai-job-application-assistant-main`**. Move it somewhere easy to find, such as your **Documents** folder. You can rename it if you like.
5. In VS Code, choose **File → Open Folder…** and select that folder. On Windows, the extracted ZIP sometimes contains a second folder with the same name inside it: if so, open the inner one, the one that directly contains `README.md`.
6. If VS Code asks **"Do you trust the authors of the files in this folder?"**, click **Yes, I trust the authors**.

> **Important:** always open the folder that directly contains `README.md` and the `jobfit` folder. If you open a different folder, Claude won't find the `/review-jobs` command.

**How approvals work.** When Claude wants to run a command or create a file, it asks first. Read the short description and click **Allow** (or **Yes**). You stay in control of everything it does.

---

## 3. Fill in your master profile

The master profile is one file describing your whole career. It's the **only** thing the workflow knows about you. The tailored resumes can select, reorder and reword what's in it, but never add anything. The more complete it is, the better your results.

1. In VS Code's file list on the left, open the **`profile`** folder and click **`master_profile.yaml`**.
2. Fill it in, following the instructions at the top of the file. For a complete example, open **`example_profile.yaml`** in the same folder (it describes a fictional person).
3. Save with `Ctrl+S` (Windows) / `Cmd+S` (macOS).

The rules that matter most:
- Keep the indentation exactly as it is, using spaces.
- Put text that contains a colon (`:`) inside quotes, for example `name: "Microsoft Certified: Azure Fundamentals"`.
- Dates are written as year-month: `2021-03`. Use `present` for your current job.
- List **every** skill and tool you can back up, and include real numbers in your bullets ("cut reporting time by 30%"). Numbers that aren't in this file can't appear on your resumes.

**Shortcut: let Claude draft it.** In the Claude panel, attach your current resume (drag the PDF into the chat) and type:

```
Fill in profile/master_profile.yaml from my attached resume. Only use facts that are in the resume.
```

Then **read the result carefully** and fix anything that's wrong or missing. It's your source of truth.

**Check it.** In the Claude panel, type:

```
Validate my master profile
```

If something is missing or malformed, Claude tells you what and where. Fix it and validate again until it says **OK**.

### Test drive (optional)

Want to see the results before filling in your own profile? You can run the workflow with the fictional example:

1. Open **`config.yaml`** and change the line `profile_path: profile/master_profile.yaml` to `profile_path: profile/example_profile.yaml`. Save.
2. Do step 4 below.
3. Change the line back afterwards, and delete the example results from the `applications` folder.

---

## 4. Review your first job

In the Claude panel, type **`/review-jobs`** followed by one of these:

| Type this | To review |
|---|---|
| `/review-jobs samples/sample_posting.txt` | The included sample posting (a good first test) |
| `/review-jobs https://company.com/careers/job/123` | A public job page (paste its link) |
| `/review-jobs` and then paste the job description text | Any posting you've copied |

The **first run takes a few extra minutes**: Claude sets up Python's helper packages (approve the commands when asked). After that, each review takes a few minutes.

You'll see a few lines like `Tracker step skipped` or `Gmail step skipped`. That's normal until you set up the optional parts.

**Where are the results?** In the **`applications`** folder, one folder per job:

- **`…_FitReport.md`**: the full review, with your score, matching strengths, gaps and a recommendation. To read it nicely formatted, right-click it in VS Code and choose **Open Preview**.
- **`….pdf`**: your tailored resume (only when the fit score is 65% or more).
- **`…_ApplicationKit.html`**: open it in your browser. It lists every application-form field with a **Copy** button, for Workday and similar sites.

> **Always read the resume before sending it.** The workflow is built to never invent anything (details in [HOW_IT_WORKS.md](HOW_IT_WORKS.md#how-fabrication-is-prevented)), but you are the final check. If the report has an **Integrity Check** section listing items, look at those first.

That's the core workflow. The next two parts are optional.

---

## 5. Optional: connect Gmail

With Gmail connected, you just put job emails under a Gmail label and type `/review-jobs`. Each email is reviewed once, marked as processed, and the results are emailed back to you.

### 5.1 Create the Gmail label

1. Open Gmail in your browser.
2. In the left sidebar, scroll to **Labels** and click the **+** next to it.
3. Name it exactly **`Job Opportunities`** and click **Create**.
4. Put job emails under it: open an email, click the **label icon** at the top, and tick **Job Opportunities**.

**Tip:** the best results come from **one job per email with the full description**. Job-alert emails listing many jobs can't be evaluated. Pages behind a login (like LinkedIn when signed out) can't be read.

*Optional filter:* to label emails automatically, use Gmail's search options to **Create filter → Apply the label: Job Opportunities**. Make sure the filter does **not** match emails whose subject starts with `[JobFit]`. Those are the workflow's own results emails.

### 5.2 Create an app password

An app password is a separate 16-letter password that lets this workflow (and only it) read your Gmail. Your real password is never used, and you can revoke the app password at any time.

1. Go to <https://myaccount.google.com/security>.
2. Under **How you sign in to Google**, make sure **2-Step Verification** is **On**. If it isn't, click it and follow the steps. App passwords require it.
3. Go to <https://myaccount.google.com/apppasswords>. Sign in again if asked.
4. Type the name **`jobfit`** and click **Create**.
5. Google shows a 16-letter password in a yellow box. **Copy it now**: you won't see it again.

> If the app-passwords page says the setting isn't available, your account is probably managed by a school or employer that disables it. Use a personal Gmail account instead.

### 5.3 Save your credentials

You'll put the address and app password in a file called **`.env`**, which stays on your computer.

1. In VS Code's file list, right-click **`.env.example`** → **Copy**, then right-click an empty area of the file list → **Paste**.
2. Right-click the new copy → **Rename**, and name it exactly **`.env`**.
3. Open `.env` and fill in the first two lines:
   ```
   GMAIL_ADDRESS=your.address@gmail.com
   GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
   ```
4. Save.

> **Never paste your app password into the Claude chat.** Type it into the `.env` file yourself. The `.env` file is set to be ignored by Git, so it isn't uploaded even if you put this folder on GitHub.

### 5.4 Try it

Label one job email in Gmail, then type `/review-jobs` (with nothing after it). Claude fetches the email, reviews it, and the email gets the label `Job Opportunities/Processed`. A results email starting with `[JobFit]` arrives in your inbox.

To turn off the results email, open `config.yaml` and set `email_results: false`.

---

## 6. Optional: set up the Google Sheets tracker

The tracker is a Google Sheet with one row per job: company, role, dates, fit score, recommendation, matches and gaps. It also has a **Stage** dropdown you update yourself as you apply and interview, from *Application sent* to *Job offer received*. A **Status** column (Pending / Open / Closed) updates automatically.

The workflow writes to the sheet through a **service account**: a robot Google account that only has access to the one sheet you share with it. It's free and needs no billing.

### 6.1 Create a Google Cloud project

1. Go to <https://console.cloud.google.com/> and sign in with your Google account. Accept the terms if asked.
2. At the top, click the project picker (it may say **Select a project**) → **New project**.
3. Name it **`jobfit`** and click **Create**. If you're asked to set up billing, skip it: it isn't needed.
4. Make sure the new project is selected in the project picker at the top.

### 6.2 Turn on the Google Sheets API

1. In the search bar at the top, type **Google Sheets API** and open it.
2. Click **Enable**.

### 6.3 Create the service account and its key

1. In the search bar, type **Service accounts** and open it (under *IAM & Admin*).
2. Click **+ Create service account**.
3. Name it **`jobfit`** and click **Create and continue**. Skip the optional permissions and user-access steps, then click **Done**.
4. Click the new service account's email address in the list.
5. Open the **Keys** tab → **Add key** → **Create new key** → choose **JSON** → **Create**. A `.json` file downloads.
6. While you're on this page, copy the service account's **email** (it ends in `iam.gserviceaccount.com`). You'll need it in 6.4.

**Move the key into the workflow folder:**
1. In VS Code's file list, right-click an empty area → **New Folder** and name it **`secrets`**.
2. Drag the downloaded `.json` file from your Downloads folder into the `secrets` folder in VS Code.
3. Rename it to **`google-service-account.json`**.

> This key file is a password for the robot account. Keep it in `secrets/` (which Git ignores) and never share it or paste it into the chat.

### 6.4 Create and share the sheet

1. Go to <https://sheets.new> to create a blank sheet. Name it **Job Tracker**.
2. Click **Share**, paste the service account email from step 6.3, set it to **Editor**, untick **Notify people**, and click **Share**.
3. Look at the sheet's address in your browser:
   `https://docs.google.com/spreadsheets/d/`**`1AbC...xyz`**`/edit`
   Copy the long part between `/d/` and `/edit`. That's the sheet ID.

### 6.5 Connect it

1. If you don't have a `.env` file yet, create it as described in [5.3](#53-save-your-credentials).
2. Open `.env` and fill in the last two lines:
   ```
   GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
   GOOGLE_SHEET_ID=1AbC...xyz
   ```
3. Save, then ask Claude:
   ```
   Set up the job tracker: run "python -m jobfit tracker setup" and then "python -m jobfit tracker sync"
   ```
4. Open your sheet: it now has its columns, colours and the Stage dropdown, plus a row for every job you've already reviewed.

From now on, every review adds or updates its row automatically. The **Stage** column is yours: the workflow fills it in once (*Processed by Claude*) and never overwrites your changes. Pick the stage from the dropdown as things move along:

| Stage | Status shown |
|---|---|
| *(blank: job waiting to be reviewed)*, *Processed by Claude* | Pending |
| *Application sent*, *First* to *Fifth interview assigned* | Open |
| *Application not sent*, *Interview failed*, *Rejected before interview*, *Job offer received* | Closed |

**Stage Met** shows the stage's number, from 1 (*Processed by Claude*) to 11 (*Job offer received*).

To turn the tracker off, open `config.yaml` and set `enabled: false` under `tracker:`.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `/review-jobs` isn't recognised | You opened the wrong folder. Use **File → Open Folder…** and select the folder that directly contains `README.md`. |
| "Python was not found" / "command not found: python" | Install Python ([1.2](#12-python)). On Windows, reinstall and tick **Add python.exe to PATH**. Then close and reopen VS Code. |
| "Master profile is not valid YAML at line X" | Look at that line in `master_profile.yaml`. Usually it's a missing pair of quotes around text containing a colon, or wrong indentation. |
| Gmail: "Application-specific password required" or login failed | Recreate the app password ([5.2](#52-create-an-app-password)) and paste it into `.env` again. Spaces in it are fine. |
| Gmail: label "Job Opportunities" not found | Create the label with exactly that name ([5.1](#51-create-the-gmail-label)), or change `source_label` in `config.yaml`. |
| Tracker: "Cannot open the Google Sheet" | Check that the sheet is shared with the service account email as **Editor**, that the Google Sheets API is enabled, and that `GOOGLE_SHEET_ID` is correct. |
| Tracker: "Service account key not found" | The key must be at `secrets/google-service-account.json`, matching the path in `.env`. |
| Google Cloud won't let you create a key | Some Google Workspace (company or school) accounts block it. Use a personal Google account. |
| A job link "could not be fetched" | The page needs a login or blocks automated access. Copy the job description text and paste it after `/review-jobs` instead. |
| The resume contains something that isn't true | Don't send it. Check that your master profile is accurate, and look at the report's **Integrity Check** section. Then ask Claude to fix the specific bullet. |

Still stuck? Describe the problem to Claude in the panel: it can read this folder and the error messages.

---

## Getting updates

New versions are published to this repository from time to time. To update without losing your data:

1. Download the new ZIP as in [part 2](#2-get-the-workflow) and unzip it.
2. Copy these from your **old** folder into the **new** one: `profile/master_profile.yaml`, `.env`, the `secrets` folder and the `applications` folder. Also copy `config.yaml` if you changed it. (On macOS, Finder hides `.env` because its name starts with a dot: press `Cmd+Shift+.` to show hidden files, or copy it in VS Code's file list, which shows it.)
3. Open the new folder in VS Code and keep using it. You can delete the old folder once everything works.

If you know Git, you can `git clone` the repository instead and update it with `git pull`. Your personal files are git-ignored or yours to keep, so they aren't touched.

---

## Next steps

- **Customise it:** the 65% threshold, label names and page size (Letter or A4) are in `config.yaml`.
- **Understand it:** [HOW_IT_WORKS.md](HOW_IT_WORKS.md) explains every part of the workflow.
- **Keep your results private:** if you put your copy on GitHub, make the repository **private**. Your reviews and resumes contain your personal details.
