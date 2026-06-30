"""SQLite 数据写入工具。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

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

    def insert_pipeline_run(
        self,
        run_id: str,
        task_name: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO pipeline_run (run_id, task_name, status, metadata) VALUES (?, ?, ?, ?)",
                    (run_id, task_name, status, metadata_json),
                )
                return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 pipeline_run 失败: {exc}") from exc

    def insert_mention(
        self,
        task_id: str,
        doc_id: str,
        mention_text: str,
        start_idx: int,
        end_idx: int,
        mention_norm: str = "",
        context: str = "",
    ) -> int:
        try:
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
    ) -> int:
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
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
    ) -> int:
        try:
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
    ) -> int:
        try:
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
                return cursor.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"插入 audit_log 失败: {exc}") from exc
