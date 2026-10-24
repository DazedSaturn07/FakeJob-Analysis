USE job_market_analysis;

-- Separate aggregates count each job score once, regardless of posting count.
CREATE OR REPLACE VIEW mart_executive_kpis AS
SELECT
 (SELECT COUNT(*) FROM fact_job_posting) AS total_postings,
 (SELECT COUNT(*) FROM dim_job) AS distinct_jobs,
 (SELECT ROUND(AVG(jd_quality_score), 2) FROM fact_job_quality) AS average_jd_quality,
 (SELECT ROUND(100.0 * SUM(salary_numeric_present = 1) / NULLIF(COUNT(*), 0), 2)
    FROM fact_job_posting) AS salary_transparency_pct,
 (SELECT COUNT(DISTINCT job_key) FROM fact_job_posting WHERE seniority_title = 'entry') AS entry_jobs,
 (SELECT COUNT(DISTINCT job_key) FROM fact_job_posting
    WHERE seniority_title = 'entry' AND experience_min_years >= 2) AS entry_2plus_jobs,
 (SELECT COUNT(*) FROM fact_repost_event) AS repost_events;

CREATE OR REPLACE VIEW mart_entry_level AS
SELECT r.canonical_role_name, COUNT(DISTINCT p.job_key) AS entry_jobs,
 COUNT(DISTINCT CASE WHEN p.experience_min_years >= 2 THEN p.job_key END) AS entry_2plus_jobs,
 ROUND(100.0 * COUNT(DISTINCT CASE WHEN p.experience_min_years >= 2 THEN p.job_key END)
   / NULLIF(COUNT(DISTINCT p.job_key), 0), 2) AS entry_2plus_pct
FROM fact_job_posting p JOIN dim_role r ON p.role_key = r.role_key
WHERE p.seniority_title = 'entry'
GROUP BY r.canonical_role_name;

-- Keep hourly and annual amounts, and different currencies, in separate groups.
CREATE OR REPLACE VIEW mart_salary_transparency AS
SELECT r.canonical_role_name, p.salary_currency, p.salary_period,
 COUNT(*) AS postings, SUM(p.salary_numeric_present = 1) AS disclosed_postings,
 ROUND(100.0 * SUM(p.salary_numeric_present = 1) / NULLIF(COUNT(*), 0), 2) AS transparency_pct,
 ROUND(AVG(p.salary_min), 2) AS average_disclosed_min
FROM fact_job_posting p JOIN dim_role r ON p.role_key = r.role_key
GROUP BY r.canonical_role_name, p.salary_currency, p.salary_period;

CREATE OR REPLACE VIEW mart_role_quality AS
SELECT r.canonical_role_name, COUNT(*) AS jobs,
 ROUND(AVG(q.jd_quality_score), 2) AS average_jd_quality,
 SUM(q.quality_band IN ('Review Recommended', 'Multiple Quality Concerns')) AS review_jobs
FROM fact_job_quality q JOIN dim_job j ON q.job_key = j.job_key
JOIN dim_role r ON j.role_key = r.role_key
GROUP BY r.canonical_role_name;

SELECT * FROM mart_executive_kpis;
SELECT * FROM mart_entry_level ORDER BY entry_jobs DESC;
SELECT * FROM mart_salary_transparency ORDER BY postings DESC;
SELECT * FROM mart_role_quality ORDER BY jobs DESC;
