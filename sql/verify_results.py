"""Run the analysis/quality scripts and reconcile MySQL with the notebook exports."""
import argparse
import getpass
import json
import re
from pathlib import Path

import pandas as pd
import pymysql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", default="root")
    args = parser.parse_args()
    connection = pymysql.connect(
        host="localhost", user=args.user, password=getpass.getpass("MySQL password: "),
        database="job_market_analysis", charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    evidence = {"tables": {}, "checks": [], "comparisons": []}
    try:
        with connection.cursor() as cursor:
            for path in sorted((ROOT / "notebooks/data/exports").glob("*.csv")):
                expected = len(pd.read_csv(path, usecols=[0]))
                cursor.execute(f"SELECT COUNT(*) AS rows_loaded FROM `{path.stem}`")
                actual = cursor.fetchone()["rows_loaded"]
                assert actual == expected, f"{path.stem}: {actual} != {expected}"
                evidence["tables"][path.stem] = actual
            for filename in ["02_analytics_views.sql", "03_quality_checks.sql"]:
                text = re.sub(r"--[^\n]*", "", (ROOT / "sql" / filename).read_text())
                query_number = 0
                for statement in text.split(";"):
                    if not statement.strip():
                        continue
                    cursor.execute(statement)
                    rows = cursor.fetchall() if cursor.description else []
                    if filename.startswith("03") and statement.strip().upper().startswith("SELECT"):
                        query_number += 1
                        if query_number <= 6:
                            assert not rows, f"Quality exception query {query_number} returned rows"
                            evidence["checks"].append({"query": query_number, "exceptions": len(rows)})
            cursor.execute("SELECT * FROM mart_executive_kpis")
            actual = cursor.fetchone()
            summary = json.loads((ROOT / "notebooks/data/qa_summary.json").read_text())
            for sql_name, python_name in {
                "total_postings": "rows_silver", "distinct_jobs": "distinct_jobs",
                "average_jd_quality": "average_jd_quality", "salary_transparency_pct": "salary_numeric_coverage_pct",
                "entry_jobs": "entry_jobs_count", "entry_2plus_jobs": "entry_jobs_requiring_2plus_years",
                "repost_events": "repost_events_count",
            }.items():
                difference = float(actual[sql_name]) - summary[python_name]
                assert abs(difference) <= 0.01, sql_name
                evidence["comparisons"].append({"metric": sql_name, "python": summary[python_name],
                    "mysql": float(actual[sql_name]), "difference": round(difference, 8)})
            cursor.execute("SELECT VERSION() AS version")
            evidence["mysql_version"] = cursor.fetchone()["version"]
        path = ROOT / "notebooks/data/sql_verification.json"
        path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
