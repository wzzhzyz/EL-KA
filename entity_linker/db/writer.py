"""SQLite 数据写入工具。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..exceptions import DatabaseError


class DBWriter:
    def __init__(self, db_path: str | Path = None):
        self.db_path = (
            Path(db_path)
            if db_path
            else Path(__file__).resolve().parents[2] / "data" / "trace.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise DatabaseError(f"无法连接 SQLite: {exc}") from exc

    @contextmanager
    def transaction(self) -> sqlite3.Connection:
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"SQLite 事务失败: {exc}") from exc
        finally:
            conn.close()

    def insert_pipeline_run(
        self,
        run_id: str,
        task_name: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO pipeline_run (run_id, task_name, status, metadata) VALUES (?, ?, ?, ?)",
                        (run_id, task_name, status, metadata_json),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO pipeline_run (run_id, task_name, status, metadata) VALUES (?, ?, ?, ?)",
                    (run_id, task_name, status, metadata_json),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 pipeline_run 失败: {exc}") from exc

    def update_pipeline_run(
        self,
        run_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            if conn is None:
                with self._get_connection() as conn:
                    conn.execute(
                        "UPDATE pipeline_run SET status = ?, metadata = ?, end_ts = datetime('now') WHERE run_id = ?",
                        (status, metadata_json, run_id),
                    )
            else:
                conn.execute(
                    "UPDATE pipeline_run SET status = ?, metadata = ?, end_ts = datetime('now') WHERE run_id = ?",
                    (status, metadata_json, run_id),
                )
        except sqlite3.Error as exc:
            raise DatabaseError(f"更新 pipeline_run 失败: {exc}") from exc

    def insert_pipeline_step(
        self,
        run_id: str,
        stage_name: str,
        status: str,
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            payload_json = json.dumps(payload or {}, ensure_ascii=False)
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO pipeline_step (run_id, stage_name, status, message, payload) VALUES (?, ?, ?, ?, ?)",
                        (run_id, stage_name, status, message, payload_json),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO pipeline_step (run_id, stage_name, status, message, payload) VALUES (?, ?, ?, ?, ?)",
                    (run_id, stage_name, status, message, payload_json),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 pipeline_step 失败: {exc}") from exc

    def insert_mention(
        self,
        task_id: str,
        doc_id: str,
        mention_text: str,
        start_idx: int,
        end_idx: int,
        mention_norm: str = "",
        context: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO mention (task_id, doc_id, mention_text, start_idx, end_idx, mention_norm, context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            task_id,
                            doc_id,
                            mention_text,
                            start_idx,
                            end_idx,
                            mention_norm,
                            context,
                        ),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO mention (task_id, doc_id, mention_text, start_idx, end_idx, mention_norm, context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        task_id,
                        doc_id,
                        mention_text,
                        start_idx,
                        end_idx,
                        mention_norm,
                        context,
                    ),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 mention 失败: {exc}") from exc

    def insert_candidate(
        self,
        mention_id: int,
        candidate_entity_id: str,
        candidate_name: str,
        score: float,
        metadata: Optional[Dict[str, Any]] = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO candidate (mention_id, candidate_entity_id, candidate_name, score, metadata) VALUES (?, ?, ?, ?, ?)",
                        (
                            mention_id,
                            candidate_entity_id,
                            candidate_name,
                            score,
                            metadata_json,
                        ),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO candidate (mention_id, candidate_entity_id, candidate_name, score, metadata) VALUES (?, ?, ?, ?, ?)",
                    (
                        mention_id,
                        candidate_entity_id,
                        candidate_name,
                        score,
                        metadata_json,
                    ),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 candidate 失败: {exc}") from exc

    def insert_link_result(
        self,
        mention_id: int,
        linked_entity_id: str,
        linked_entity_name: str,
        is_nil: bool,
        score: float,
        decision_reason: str,
        evidence: str,
        model_version: str = "",
        actor: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO link_result (mention_id, linked_entity_id, linked_entity_name, is_nil, score, decision_reason, evidence, model_version, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            mention_id,
                            linked_entity_id,
                            linked_entity_name,
                            int(is_nil),
                            score,
                            decision_reason,
                            evidence,
                            model_version,
                            actor,
                        ),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO link_result (mention_id, linked_entity_id, linked_entity_name, is_nil, score, decision_reason, evidence, model_version, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        mention_id,
                        linked_entity_id,
                        linked_entity_name,
                        int(is_nil),
                        score,
                        decision_reason,
                        evidence,
                        model_version,
                        actor,
                    ),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 link_result 失败: {exc}") from exc

    def insert_audit_log(
        self,
        mention_id: int,
        link_result_id: int,
        field: str,
        old_value: str,
        new_value: str,
        reason: str = "",
        actor: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> int:
        try:
            if conn is None:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "INSERT INTO audit_log (mention_id, link_result_id, field, old_value, new_value, reason, actor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            mention_id,
                            link_result_id,
                            field,
                            old_value,
                            new_value,
                            reason,
                            actor,
                        ),
                    )
            else:
                cursor = conn.execute(
                    "INSERT INTO audit_log (mention_id, link_result_id, field, old_value, new_value, reason, actor) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        mention_id,
                        link_result_id,
                        field,
                        old_value,
                        new_value,
                        reason,
                        actor,
                    ),
                )
            return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 audit_log 失败: {exc}") from exc

    def batch_insert_candidates(
        self,
        mention_id: int,
        candidates: Iterable[Dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> List[int]:
        rows = []
        for candidate in candidates:
            metadata_json = json.dumps(candidate.get("metadata") or {}, ensure_ascii=False)
            rows.append(
                (
                    mention_id,
                    candidate.get("candidate_entity_id", ""),
                    candidate.get("candidate_name", ""),
                    float(candidate.get("score", 0.0)),
                    metadata_json,
                )
            )

        try:
            if conn is None:
                with self._get_connection() as conn:
                    conn.executemany(
                        "INSERT INTO candidate (mention_id, candidate_entity_id, candidate_name, score, metadata) VALUES (?, ?, ?, ?, ?)",
                        rows,
                    )
            else:
                conn.executemany(
                    "INSERT INTO candidate (mention_id, candidate_entity_id, candidate_name, score, metadata) VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
            return []
        except sqlite3.Error as exc:
            raise DatabaseError(f"批量插入 candidate 失败: {exc}") from exc

    def batch_insert_mentions(
        self,
        mention_rows: Iterable[Dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> List[int]:
        rows = []
        for row in mention_rows:
            rows.append(
                (
                    row.get("task_id", ""),
                    row.get("doc_id", ""),
                    row.get("mention_text", ""),
                    int(row.get("start_idx", 0)),
                    int(row.get("end_idx", 0)),
                    row.get("mention_norm", ""),
                    row.get("context", ""),
                )
            )

        try:
            if conn is None:
                with self._get_connection() as conn:
                    conn.executemany(
                        "INSERT INTO mention (task_id, doc_id, mention_text, start_idx, end_idx, mention_norm, context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        rows,
                    )
            else:
                conn.executemany(
                    "INSERT INTO mention (task_id, doc_id, mention_text, start_idx, end_idx, mention_norm, context) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
            return []
        except sqlite3.Error as exc:
            raise DatabaseError(f"批量插入 mention 失败: {exc}") from exc

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        try:
            with self._get_connection() as conn:
                run = conn.execute(
                    "SELECT * FROM pipeline_run WHERE run_id = ?",
                    (trace_id,),
                ).fetchone()
                steps = conn.execute(
                    "SELECT * FROM pipeline_step WHERE run_id = ? ORDER BY id",
                    (trace_id,),
                ).fetchall()
                mentions = conn.execute(
                    "SELECT * FROM mention WHERE task_id = ? ORDER BY id",
                    (trace_id,),
                ).fetchall()
                candidates = conn.execute(
                    "SELECT c.*, m.mention_text FROM candidate c JOIN mention m ON c.mention_id = m.id WHERE m.task_id = ? ORDER BY c.id",
                    (trace_id,),
                ).fetchall()
                results = conn.execute(
                    "SELECT lr.*, m.mention_text, m.mention_norm, m.context FROM link_result lr JOIN mention m ON lr.mention_id = m.id WHERE m.task_id = ? ORDER BY lr.id",
                    (trace_id,),
                ).fetchall()
                audits = conn.execute(
                    "SELECT al.*, m.mention_text FROM audit_log al LEFT JOIN mention m ON al.mention_id = m.id WHERE m.task_id = ? OR al.mention_id IN (SELECT id FROM mention WHERE task_id = ?) ORDER BY al.id",
                    (trace_id, trace_id),
                ).fetchall()

            return {
                "run": dict(run) if run else None,
                "steps": [dict(row) for row in steps],
                "mentions": [dict(row) for row in mentions],
                "candidates": [dict(row) for row in candidates],
                "results": [dict(row) for row in results],
                "audits": [dict(row) for row in audits],
            }
        except sqlite3.Error as exc:
            raise DatabaseError(f"查询 trace 失败: {exc}") from exc

    def list_pipeline_runs(self, status: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                if status:
                    rows = conn.execute(
                        "SELECT * FROM pipeline_run WHERE status = ? ORDER BY id DESC LIMIT ?",
                        (status, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM pipeline_run ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            raise DatabaseError(f"查询 pipeline_run 列表失败: {exc}") from exc
