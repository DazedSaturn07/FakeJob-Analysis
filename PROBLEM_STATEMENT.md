# Problem statement: job-posting information quality

## Context

A job posting is useful when candidates can understand its requirements, compensation and working arrangements. Historical posting data can contain missing pay, ambiguous descriptions and repeated text. Reporting raw row counts without accounting for repetition can also overstate the number of distinct opportunities represented in a dataset.

This project studies the information visible in one historical LinkedIn snapshot. It provides a reproducible way to compare posting clarity, identify records for review and trace a reported metric back to source evidence.

## Intended users

| Audience | Analytical use |
|---|---|
| Job seekers and career advisers | Understand information gaps and inspect experience expectations behind explicitly junior titles |
| Recruitment and people-analytics teams | Review how consistently postings describe compensation, requirements and workplace arrangements |
| Analysts and reviewers | Reconcile counts across tools and investigate the source records behind a result |

These are intended uses of the analysis, not evidence of deployment or measured business impact.

## Questions

1. What share of posting observations includes numeric salary information?
2. Among exact text groups with explicit junior-title keywords, how many have a parsed minimum requirement of two or more years?
3. Which descriptions meet transparent information-quality review rules?
4. How much does exact text repetition contribute to the observation count?
5. Do the same definitions produce consistent results in Python, MySQL, Excel and Power BI?

## Scope and definitions

The retained source version contains 123,849 observations, 31 source columns and listed dates from 24 March to 20 April 2024 UTC. The final listed date is partial. The source manifest identifies the exact file used.

| Term | Definition |
|---|---|
| Posting observation | One row identified by a source posting ID |
| Exact job-text group | Observations sharing normalized company, title, location and cleaned description |
| Representative quality record | The heuristic score and rules for the latest observed posting within a group |
| Numeric salary disclosure | At least one usable minimum, maximum or publisher-provided median pay value |
| Entry-title review | Explicit junior-title keywords together with a parsed minimum experience requirement of 2+ years |
| Extra repeated observation | An observation after the first within an exact text group |
| Unknown | Information missing from the source or not confidently parsed by the supplied rules |

A text group is not a verified unique vacancy. The quality record is not a historical score for every observation. Missing numeric experience is not zero experience, and an experience review flag does not by itself establish an unreasonable requirement.

## Approach

Python validates and profiles the source, normalizes selected fields, applies conservative text rules and exports a dimensional model. MySQL independently summarizes and checks the same exports. Excel supplies a review sample with provenance and reconciliation formulas. Power BI presents the population, comparisons and record-level evidence through six report pages.

The score combines six visible components: completeness, experience consistency, salary disclosure, location clarity, role/skill alignment and exact repetition. The rules and weights remain explicit so a reviewer can explain or challenge a result.

## Deliverables and acceptance criteria

- Ordered notebooks, source provenance and configurable analysis settings reproduce the analytical tables without changing the original CSV.
- Twelve shared export tables support consistent posting-level and group-level reporting.
- MySQL table counts and headline metrics reconcile with Python, and exception queries return no rows for the verified build.
- An Excel workbook supports manual review without inventing reviewer decisions.
- An editable Power BI project supports filters, job drill-through and phone layouts, with totals checked against the exported data.
- Public documentation states the source, method, reproduction requirements and interpretation limits.

## Boundaries

Despite the repository name FakeJob-Analysis, the dataset and rules do not support a validated fraud detector. There are no verified fraud labels, application outcomes, hiring outcomes or employer intent measures. The project therefore makes no claim to identify fake jobs or deceptive employers.

It also does not estimate today's vacancies, hiring demand, causal effects or the whole labour market. Title/skill vocabularies are limited, text extraction can miss or misread a requirement, and exact matching can both combine reused text and miss edited duplicates. Salary comparisons must respect currency and pay period. Further validation would require manual labelled review and, for wider claims, additional representative data.

See the [README](README.md) for the verified full-source results and reproduction instructions.
