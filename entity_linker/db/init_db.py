"""初始化 SQLite 数据库并应用 schema.sql。"""

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).parent
SCHEMA = ROOT / "schema.sql"


def init_db(db_path: str = None):
    db_path = db_path or (ROOT.parent.parent / "data" / "trace.db")
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
    print(f"Initialized DB at {db_path}")


if __name__ == "__main__":
    init_db()
