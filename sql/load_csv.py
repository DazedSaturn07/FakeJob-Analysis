"""Load notebook exports into this project's MySQL schema, in foreign-key order."""
import argparse
import csv
import getpass
from pathlib import Path

import pandas as pd
import pymysql

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "notebooks" / "data" / "exports"
TABLES = [
    "dim_company", "dim_date", "dim_location", "dim_role", "dim_skill", "dim_source",
    "dim_job", "fact_job_posting", "fact_job_quality", "fact_job_flag",
    "bridge_job_skill", "fact_repost_event",
]
BOOLEAN_COLUMNS = {"salary_numeric_present", "experience_numeric_present"}


def convert_value(value, column):
    """CSV blanks become SQL NULL; pandas Boolean text becomes a MySQL integer."""
    if value == "":
        return None
    if column in BOOLEAN_COLUMNS:
        if value.lower() in {"true", "1"}:
            return 1
        if value.lower() in {"false", "0"}:
            return 0
        raise ValueError(f"Invalid Boolean in {column}: {value!r}")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--load", action="store_true", help="Connect and load; otherwise check CSV headers only.")
    parser.add_argument("--replace", action="store_true", help="Replace existing project table rows in one transaction.")
    args = parser.parse_args()
    if args.replace and not args.load:
        parser.error("--replace also requires --load")

    headers = {}
    for table in TABLES:
        path = EXPORTS / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Run notebooks 01–03 first. Missing {path}")
        with path.open(encoding="utf-8", newline="") as stream:
            headers[table] = next(csv.reader(stream))
        if not headers[table] or len(set(headers[table])) != len(headers[table]):
            raise ValueError(f"Invalid headers: {table}")
        print(f"Found {table}: {len(headers[table])} columns")
    if not args.load:
        print("Files checked. No database connection made. Use --load when ready.")
        return

    connection = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=getpass.getpass("MySQL password (not saved): "),
        database="job_market_analysis", charset="utf8mb4", autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            # Check all schemas before changing any data.
            for table in TABLES:
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                actual = {row[0] for row in cursor.fetchall()}
                if actual != set(headers[table]):
                    raise ValueError(f"{table}: schema differs from CSV. Review 01_mysql_schema.sql.")
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                if cursor.fetchone()[0] and not args.replace:
                    raise ValueError("Existing project rows found. Back up your database; use --load --replace for a deliberate refresh.")
            if args.replace:
                for table in reversed(TABLES):
                    cursor.execute(f"DELETE FROM `{table}`")
            for table in TABLES:
                columns = headers[table]
                names = ", ".join(f"`{name}`" for name in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                statement = f"INSERT INTO `{table}` ({names}) VALUES ({placeholders})"
                expected = 0
                for chunk in pd.read_csv(EXPORTS / f"{table}.csv", dtype=str, keep_default_na=False, chunksize=250):
                    rows = [
                        tuple(convert_value(value, column) for value, column in zip(row, columns))
                        for row in chunk.itertuples(index=False, name=None)
                    ]
                    cursor.executemany(statement, rows)
                    expected += len(rows)
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                if cursor.fetchone()[0] != expected:
                    raise ValueError(f"Row count mismatch in {table}")
                print(f"{table}: {expected:,} rows loaded")
        connection.commit()
        print("All 12 tables committed. Now run 02_analytics_views.sql and 03_quality_checks.sql.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
