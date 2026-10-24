USE job_market_analysis;

-- Each exception query should return zero rows.
SELECT source_job_id, COUNT(*) AS duplicates FROM fact_job_posting
GROUP BY source_job_id HAVING COUNT(*) > 1;
SELECT p.job_key FROM fact_job_posting p LEFT JOIN dim_job j ON p.job_key = j.job_key
WHERE j.job_key IS NULL;
SELECT j.job_key FROM dim_job j LEFT JOIN fact_job_quality q ON j.job_key = q.job_key
GROUP BY j.job_key HAVING COUNT(q.job_key) <> 1;
SELECT job_key, jd_quality_score FROM fact_job_quality
WHERE jd_quality_score IS NULL OR jd_quality_score < 0 OR jd_quality_score > 100;
SELECT q.job_key, q.flag_count, COUNT(f.flag_id) AS actual_flags
FROM fact_job_quality q LEFT JOIN fact_job_flag f ON q.job_key = f.job_key
GROUP BY q.job_key, q.flag_count HAVING q.flag_count <> COUNT(f.flag_id);
SELECT posting_observation_key FROM fact_job_posting
WHERE salary_min < 0 OR salary_max < 0 OR salary_median < 0 OR salary_min > salary_max
 OR experience_min_years > experience_max_years;

-- Missing fields are observations to explain, not automatic failures.
SELECT COUNT(*) AS postings, SUM(title_raw IS NULL) AS missing_titles,
 SUM(published_date_key IS NULL) AS missing_dates FROM fact_job_posting;
SELECT * FROM mart_executive_kpis;
SELECT (SELECT COUNT(*) FROM fact_job_posting) - (SELECT COUNT(*) FROM dim_job)
 AS repeated_observations, (SELECT COUNT(*) FROM fact_repost_event) AS repeat_events;
