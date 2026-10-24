# Job Market Quality Analysis

An analysis of **123,849 historical job-posting observations**, built with Python, MySQL, Excel and Power BI. It examines salary disclosure, entry-level experience expectations, description clarity and repeated job text.

The repository is named FakeJob-Analysis, but the analysis measures observable posting information. It does **not** classify employers or job adverts as fraudulent.

## The problem

Job seekers need enough information to judge whether an opportunity fits their experience and expectations. Missing salary information, unclear requirements and repeated adverts make that comparison harder. Analysts also need to distinguish source observations from distinct job-text groups before reporting totals.

This project turns one historical snapshot into consistent analytical tables, transparent review rules and an interactive report. The [problem statement](PROBLEM_STATEMENT.md) describes the questions, definitions and scope.

## Results from the full source

| Metric | Result |
|---|---:|
| Source observations | 123,849 |
| Exact job-text groups | 119,041 |
| Observations with numeric salary information | 36,073 (29.13%) |
| Explicit entry-title groups | 2,919 |
| Entry-title groups with a parsed requirement of 2+ years | 73 (2.50%) |
| Extra observations within exact text groups | 4,808 |
| Average heuristic clarity score | 68.98 / 100 |

These results use the full source and `notebook_v3` rules. The junior-title result is a prompt to inspect the description, not a judgement that the requirement is inappropriate. Counts describe the collected snapshot rather than current vacancies or overall market demand.

## How it works

`Source CSV → Python notebooks → 12 shared CSV tables → MySQL checks / Excel review / Power BI report`

| Component | Responsibility |
|---|---|
| `notebooks/01_load_and_profile.ipynb` | Validate the source, inspect missing values and create the initial working table |
| `notebooks/02_clean_and_enrich.ipynb` | Normalize fields, identify exact text groups and extract conservative role, skill and experience signals |
| `notebooks/03_score_and_export.ipynb` | Calculate rule-based scores and flags; export dimensional tables and the summary |
| `notebooks/04_build_excel_review.ipynb` | Create a 200-observation review sample with provenance and reconciliation formulas |
| `sql/` | Load exports into MySQL, calculate independent summaries and check consistency |
| `power_bi/` | Editable native report, semantic model, DAX, relationships, theme and rebuild utilities |

The 12 exported tables contain seven dimensions, four facts and one job-skill bridge. A posting observation is a source row. An exact job-text group shares normalized company, title, location and cleaned description. Its quality record scores the latest representative observation; it is not a verified unique vacancy or a score history.

## Data

Source: [LinkedIn Job Postings (2023–2024), published on Kaggle](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings). The version used here has 31 columns and listed timestamps from **24 March to 20 April 2024 UTC**; the final date is partial. The [source manifest](notebooks/data/raw/manifest.json) records row count, byte size and SHA256 so another run can identify the same input.

Download the original `postings.csv` and place it at:

```text
notebooks/data/raw/historical_linkedin_124k/postings.csv
```

Review the publisher's dataset terms before use or redistribution. Raw records, generated CSVs, review workbooks and binary Power BI files are excluded from Git. This repository includes the analysis and report source; a fresh clone must generate its own local data outputs.

## Reproduce the analysis

Requirements: Python 3.10+, MySQL Server 8+ for database validation, Excel for workbook review, and Power BI Desktop on Windows for the report. Python alone can run the notebook analysis and exports.

```powershell
git clone https://github.com/DazedSaturn07/FakeJob-Analysis.git
cd FakeJob-Analysis
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --sys-prefix --name job-market-quality --display-name "Python (job-market-quality)"
.\.venv\Scripts\python.exe -m jupyterlab
```

After placing the source CSV, execute notebooks **01 → 02 → 03 → 04**, each from a fresh kernel using the installed environment. The settings in [analysis_settings.yaml](notebooks/analysis_settings.yaml) default to the full source (`row_limit: null`). A value of `5000` gives a smaller practice run in source order, not a representative sample. All downstream tools must use exports from the same run.

Notebook 03 writes 12 tables to `notebooks/data/exports/` and the reconciliation summary to `notebooks/data/qa_summary.json`. Notebook 04 writes `excel/job_market_quality_review.xlsx`. Rerunning 04 replaces that generated workbook; preserve manual review separately.

### MySQL validation

Execute `sql/01_mysql_schema.sql` against the intended MySQL server. It creates the `job_market_analysis` schema and tables. With a database account authorized for that schema:

```powershell
.\.venv\Scripts\python.exe sql/load_csv.py
.\.venv\Scripts\python.exe sql/load_csv.py --load --user YOUR_MYSQL_USER
.\.venv\Scripts\python.exe sql/verify_results.py --user YOUR_MYSQL_USER
```

The first command validates export headers without connecting. The loader prompts for the password, checks schemas, loads parents before children and rolls back failed loads. It refuses existing rows by default. `--load --replace` intentionally replaces the project's table rows; use it only after preserving data that needs to be retained.

The verification script runs `02_analytics_views.sql` and `03_quality_checks.sql`, compares all 12 table counts and seven headline metrics with Python, and writes an ignored local result. The six exception queries should return no rows. SQL summaries aggregate at the intended grain to avoid inflating job-level scores through joins.

### Excel review

The generated workbook contains Overview, QA Sample, Checks and Source sheets. Reviewer decisions are left blank. The Checks sheet reconciles exported populations; after native Excel calculation, the three differences should be zero and the status cells should show Match. Reconciliation confirms counts, while manual record review assesses the extraction rules.

### Power BI report

After generating the exports, open `power_bi/Job_Market_Quality.pbip` in Power BI Desktop. Keep its `.Report` and `.SemanticModel` folders together. Set the **DataFolder** text parameter to the absolute path of the local `notebooks/data/exports` folder, then apply changes and refresh. The checked-in value is a generic placeholder, not a working data source. Save a local `.pbix` copy when the model has loaded.

| Page | Purpose |
|---|---|
| Overview | Population, exact groups, clarity score, salary disclosure and listed-date coverage |
| Pay & clarity | Pay disclosure, parsed experience coverage, remote permission, bands and skills |
| Entry expectations | Explicit junior titles with numeric experience requirements and source rows |
| Repeated text | Extra observations in exact text groups, companies and record-level investigation |
| Job detail | Drill-through to one job's observations, rule evidence and description |
| Method & checks | Source, score weights, definitions, limitations and refresh context |

The native project includes **25 measures**, **11 single-direction relationships**, page filters, job drill-through and phone layouts. Date and posting filters transfer visible job IDs to other facts through `TREATAS`. Location filters observations directly because workplace permission can differ within a text group. Recognized skill counts use the bridge table; selecting a skill intentionally does not filter unrelated posting metrics.

`power_bi/build_report.py` can recreate the native definitions from existing exports. A deliberate `--rebuild` replaces generated project definitions and can overwrite manual edits. It does not refresh or overwrite a saved PBIX. For normal use, update DataFolder and refresh the existing project. `verify_model.ps1` is an optional read-only DAX utility for an open local Desktop model; it requires that session's engine port and a DAX query file.

## Rules and limitations

The clarity score is a heuristic weighted sum: completeness 30%, experience consistency 20%, salary disclosure 15%, location clarity 10%, role/skill alignment 15%, and exact repetition 10%. It is not a trained model or validated employer rating.

- Numeric pay includes usable minimum, maximum or publisher-provided median pay. Different currencies and pay periods remain separate.
- Experience extraction requires nearby applicant or qualification wording and excludes clear employer/team-background references. Unparsed experience remains unknown rather than zero.
- Role and skill rules have limited vocabularies. Unclassified titles are not evidence of poor quality.
- Remote permission is confirmed only when the source explicitly allows it. Missing permission does not mean on-site.
- Exact text reuse may reflect collection patterns or legitimate reuse. It does not establish fraud, vacancy status or hiring outcomes.

## Validation

The full-source build was checked across Python, MySQL, native Excel and Power BI Desktop. All 12 MySQL table counts and seven headline comparisons matched; six SQL exception queries were empty. Thirty DAX values matched independent CSV calculations across full-population, role, seniority, remote and date scopes. Excel recalculated three matching reconciliation checks, and the saved PBIX reopened successfully with slicer and drill-through checks.

Notebook cells were executed sequentially in fresh Python namespaces; Jupyter UI startup was not part of that verification. All six desktop pages and selected phone previews were inspected. Physical mobile devices, cloud publishing and scheduled cloud refresh were not tested. These checks establish calculation consistency, not the accuracy of every text-classification decision.
