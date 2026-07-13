import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print recent trace IDs from the SQLite trace DB"
    )
    parser.add_argument(
        "--db", default="data/trace.db", help="Path to the trace database"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="How many recent runs to print"
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Trace DB not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, run_id, status, task_name, start_ts, end_ts, metadata
            FROM pipeline_run
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No pipeline runs found.")
        return

    print(f"Recent runs (limit={args.limit}):")
    for row in rows:
        print(
            f"id={row['id']} | run_id={row['run_id']} | status={row['status']} | "
            f"task_name={row['task_name']} | start_ts={row['start_ts']} | end_ts={row['end_ts']}"
        )


if __name__ == "__main__":
    main()
