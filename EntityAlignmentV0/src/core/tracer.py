# src/core/tracer.py
import sqlite3
from typing import List, Dict
from src.utils.logger import logger


class LinkTracer:
    """链接留痕：每条链接记录存入 SQLite"""

    def __init__(self, db_path: str = "./data/link_records.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                mention TEXT NOT NULL,
                mention_type TEXT,
                entity_id TEXT,
                standard_name TEXT,
                confidence REAL,
                is_nil BOOLEAN,
                method TEXT,
                evidence TEXT,
                is_coreference BOOLEAN DEFAULT 0,
                resolved_from TEXT,
                context_snippet TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trace_id ON link_traces(trace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mention ON link_traces(mention)")
        conn.commit()
        conn.close()
        logger.info(f"✅ 留痕数据库初始化完成: {self.db_path}")

    def save(self, trace_id: str, text: str, results: List[Dict]):
        """保存链接记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for r in results:
            # 从 StandardEntity 获取字段，或从字典直接获取
            entity = r.get("entity")
            entity_id = r.get("entity_id")
            standard_name = r.get("standard_entity")

            if entity and not entity_id:
                entity_id = entity.entity_id
                standard_name = entity.standard_name

            cursor.execute("""
                INSERT INTO link_traces (
                    trace_id, mention, mention_type, entity_id, standard_name,
                    confidence, is_nil, method, evidence, is_coreference,
                    resolved_from, context_snippet
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trace_id,
                r.get("mention", ""),
                r.get("type", ""),
                entity_id,
                standard_name,
                r.get("confidence", 0.0),
                1 if r.get("is_nil", True) else 0,
                r.get("method", ""),
                r.get("evidence", ""),
                1 if r.get("is_coreference", False) else 0,
                r.get("resolved_from"),
                text[:200]
            ))

        conn.commit()
        conn.close()
        logger.info(f"✅ 留痕完成: trace_id={trace_id}, 共 {len(results)} 条记录")

    def query_by_trace_id(self, trace_id: str) -> List[Dict]:
        """根据 trace_id 查询记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM link_traces WHERE trace_id = ?", (trace_id,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results