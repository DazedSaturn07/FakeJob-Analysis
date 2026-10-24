-- Run in MySQL Workbench before loading notebook 03 exports.
-- Creates missing tables; it does not migrate an older schema.
CREATE DATABASE IF NOT EXISTS job_market_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE job_market_analysis;

CREATE TABLE IF NOT EXISTS dim_company (
 company_key BIGINT PRIMARY KEY, company_name VARCHAR(500),
 normalized_company_name VARCHAR(500) COLLATE utf8mb4_bin NOT NULL UNIQUE, industry VARCHAR(255), country VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS dim_date (
 date_key INT PRIMARY KEY, full_date DATE NOT NULL UNIQUE, year SMALLINT, quarter TINYINT,
 month TINYINT, month_name VARCHAR(12), day TINYINT, day_of_week VARCHAR(12), is_weekend TINYINT
);
CREATE TABLE IF NOT EXISTS dim_location (
 location_key BIGINT PRIMARY KEY, city VARCHAR(500), region VARCHAR(255), country VARCHAR(100),
 metro VARCHAR(500), workplace_type VARCHAR(30), location_normalized VARCHAR(500) COLLATE utf8mb4_bin,
 UNIQUE KEY uq_location (location_normalized, workplace_type)
);
CREATE TABLE IF NOT EXISTS dim_role (
 role_key BIGINT PRIMARY KEY, canonical_role_name VARCHAR(255) UNIQUE,
 role_family VARCHAR(100), occupational_group VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS dim_skill (
 skill_key BIGINT PRIMARY KEY, skill_name VARCHAR(100) UNIQUE, category VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS dim_source (
 source_key BIGINT PRIMARY KEY, source_name VARCHAR(100) UNIQUE, source_type VARCHAR(50),
 platform_or_ats VARCHAR(100), collection_method VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS dim_job (
 job_key BIGINT PRIMARY KEY, canonical_job_key VARCHAR(100) NOT NULL UNIQUE,
 title_normalized VARCHAR(1000), company_key BIGINT NOT NULL, role_key BIGINT NOT NULL, location_key BIGINT NOT NULL,
 FOREIGN KEY (company_key) REFERENCES dim_company(company_key),
 FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
 FOREIGN KEY (location_key) REFERENCES dim_location(location_key)
);
CREATE TABLE IF NOT EXISTS fact_job_posting (
 posting_observation_key BIGINT PRIMARY KEY, job_key BIGINT NOT NULL, source_key BIGINT NOT NULL,
 company_key BIGINT NOT NULL, role_key BIGINT NOT NULL, location_key BIGINT NOT NULL,
 published_date_key INT, observed_date_key INT NOT NULL, source_job_id VARCHAR(100) NOT NULL UNIQUE,
 title_raw VARCHAR(1000), title_normalized VARCHAR(1000), description_clean MEDIUMTEXT,
 seniority_title VARCHAR(30), employment_type VARCHAR(50), workplace_type VARCHAR(30),
 experience_min_years DECIMAL(5,2), experience_max_years DECIMAL(5,2),
 salary_min DECIMAL(16,2), salary_max DECIMAL(16,2), salary_median DECIMAL(16,2),
 salary_currency VARCHAR(10), salary_period VARCHAR(30), posting_age_days INT, description_word_count INT,
 salary_numeric_present TINYINT NOT NULL, experience_numeric_present TINYINT NOT NULL, payload_hash CHAR(64) NOT NULL,
 FOREIGN KEY (job_key) REFERENCES dim_job(job_key),
 FOREIGN KEY (source_key) REFERENCES dim_source(source_key),
 FOREIGN KEY (company_key) REFERENCES dim_company(company_key),
 FOREIGN KEY (role_key) REFERENCES dim_role(role_key),
 FOREIGN KEY (location_key) REFERENCES dim_location(location_key),
 FOREIGN KEY (published_date_key) REFERENCES dim_date(date_key),
 FOREIGN KEY (observed_date_key) REFERENCES dim_date(date_key)
);
CREATE TABLE IF NOT EXISTS fact_job_quality (
 job_key BIGINT NOT NULL, score_version VARCHAR(30) NOT NULL, jd_quality_score DECIMAL(5,2),
 quality_band VARCHAR(100), completeness_score DECIMAL(8,4), experience_consistency_score DECIMAL(5,2),
 role_alignment_score DECIMAL(5,2), salary_transparency_score DECIMAL(5,2),
 duplicate_repost_score DECIMAL(5,2), location_clarity_score DECIMAL(5,2),
 flag_count INT, scored_at DATETIME, PRIMARY KEY (job_key, score_version),
 FOREIGN KEY (job_key) REFERENCES dim_job(job_key)
);
CREATE TABLE IF NOT EXISTS fact_job_flag (
 flag_id BIGINT PRIMARY KEY, job_key BIGINT NOT NULL, rule_code VARCHAR(100), severity VARCHAR(20),
 observed_value TEXT, expected_value TEXT, evidence_text TEXT, created_at DATETIME,
 FOREIGN KEY (job_key) REFERENCES dim_job(job_key)
);
CREATE TABLE IF NOT EXISTS bridge_job_skill (
 job_key BIGINT NOT NULL, skill_key BIGINT NOT NULL, PRIMARY KEY (job_key, skill_key),
 FOREIGN KEY (job_key) REFERENCES dim_job(job_key), FOREIGN KEY (skill_key) REFERENCES dim_skill(skill_key)
);
CREATE TABLE IF NOT EXISTS fact_repost_event (
 repost_event_key BIGINT PRIMARY KEY, job_key BIGINT NOT NULL,
 previous_source_job_id VARCHAR(100), current_source_job_id VARCHAR(100),
 FOREIGN KEY (job_key) REFERENCES dim_job(job_key)
);
