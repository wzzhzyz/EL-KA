"""Pipeline 调度与实体链接主流程。

- 仅串联 NER / 候选生成 / 存储，不接入 BGE 或消歧；
- 中文共指目前只保留占位步骤，不强行接入英文 Coreferee；
- 每个 run、每个 stage、每条 mention / candidate / result 都会写入 SQLite。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .adapters import normalize_entity
from .db import DBWriter
from .db.init_db import init_db
from .exceptions import PipelineError
from .logging_util import get_logger
from .models import LINKABLE_TYPES, Candidate, StandardEntity, StandardMention
from .utils.trace import new_trace_id, trace_context

logger = get_logger(__name__)

StageCallable = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class PipelineStage:
    name: str
    fn: StageCallable


class Pipeline:
    def __init__(self, name: str = "entity_linking_pipeline"):
        self.name = name
        self.stages: List[PipelineStage] = []

    def register(self, name: str, fn: StageCallable) -> None:
        """注册一个阶段函数。阶段函数接受并返回 context(dict)。"""
        self.stages.append(PipelineStage(name=name, fn=fn))

    def run(
        self, context: Optional[Dict[str, Any]] = None, trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        ctx = context.copy() if context else {}
        ctx.setdefault("trace_id", trace_id or new_trace_id())
        ctx.setdefault("pipeline_name", self.name)
        ctx.setdefault("stage_log", [])

        with trace_context(ctx["trace_id"]):
            for stage in self.stages:
                try:
                    ctx = stage.fn(ctx) or ctx
                    ctx["stage_log"].append({"stage": stage.name, "status": "ok"})
                except Exception as exc:
                    ctx["stage_log"].append(
                        {"stage": stage.name, "status": "error", "error": str(exc)}
                    )
                    raise PipelineError(
                        f"Pipeline stage '{stage.name}' failed: {exc}"
                    ) from exc

        return ctx


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _collect_entity_records(node: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(node, dict):
        if "entity_id" in node and ("standard_name" in node or "entity_name" in node):
            yield node
        for value in node.values():
            yield from _collect_entity_records(value)
    elif isinstance(node, list):
        for item in node:
            yield from _collect_entity_records(item)


class _LocalKnowledgeBase:
    def __init__(self, kb_path: Path):
        self.kb_path = kb_path
        self.entities: List[StandardEntity] = []
        self._alias_index: Dict[str, List[StandardEntity]] = {}
        self._load()

    def _load(self) -> None:
        if not self.kb_path.exists():
            logger.warning("本地知识库文件不存在: %s", self.kb_path)
            return

        with open(self.kb_path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        for record in _collect_entity_records(payload):
            entity = normalize_entity(record)
            if not entity.entity_id or not entity.standard_name:
                continue
            self.entities.append(entity)
            self._add_alias(entity.standard_name, entity)
            for alias in entity.aliases:
                self._add_alias(alias, entity)

    def _add_alias(self, alias: str, entity: StandardEntity) -> None:
        alias = alias.strip()
        if not alias:
            return
        bucket = self._alias_index.setdefault(alias, [])
        if entity not in bucket:
            bucket.append(entity)

    def get_entities_by_alias(self, alias: str) -> List[StandardEntity]:
        return list(self._alias_index.get(alias, []))

    def get_entities_by_alias_fuzzy(
        self, alias: str, max_results: int = 5
    ) -> List[StandardEntity]:
        results: List[StandardEntity] = []
        seen: set[str] = set()
        for candidate_alias, entities in self._alias_index.items():
            if alias in candidate_alias or candidate_alias in alias:
                for entity in entities:
                    if entity.entity_id in seen:
                        continue
                    results.append(entity)
                    seen.add(entity.entity_id)
                    if len(results) >= max_results:
                        return results
        return results

    def get_all_entities(self) -> List[StandardEntity]:
        return list(self.entities)

    def get_all_entities_dict(self) -> List[Dict[str, Any]]:
        return [entity.to_dict() for entity in self.entities]


class _NullVectorIndex:
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return []


class _NullDisambiguator:
    nil_threshold: float = 1.0

    def disambiguate(
        self, mention: str, candidates: List[Candidate], context: str = ""
    ) -> Dict[str, Any]:
        if not candidates:
            return {
                "entity": None,
                "score": 0.0,
                "method": "none",
                "evidence": "无候选实体",
            }
        return {
            "entity": None,
            "score": 0.0,
            "method": "none",
            "evidence": "当前流程仅执行 NER、候选生成与存储，不做消歧",
        }


class _FallbackNEREngine:
    def __init__(self, kb: _LocalKnowledgeBase):
        self.kb = kb

    def get_model_name(self) -> str:
        return "fallback_kb_ner"

    def extract(self, text: str) -> List[StandardMention]:
        mentions: List[StandardMention] = []
        occupied: List[Tuple[int, int]] = []
        aliases = sorted(self.kb._alias_index.keys(), key=len, reverse=True)

        for alias in aliases:
            start = text.find(alias)
            while start != -1:
                end = start + len(alias)
                overlaps = any(not (end <= s or start >= e) for s, e in occupied)
                if not overlaps:
                    entity = self.kb.get_entities_by_alias(alias)[:1]
                    entity_type = entity[0].entity_type if entity else "UNKNOWN"
                    mention_type = self._infer_mention_type(entity_type)
                    mentions.append(
                        StandardMention(
                            mention=alias,
                            mention_type=mention_type,
                            char_start=start,
                            char_end=end,
                            metadata={"source": "fallback_kb"},
                        )
                    )
                    occupied.append((start, end))
                    break
                start = text.find(alias, start + 1)

        mentions.sort(
            key=lambda item: (item.char_start, -(item.char_end - item.char_start))
        )
        return mentions

    @staticmethod
    def _infer_mention_type(entity_type: str) -> str:
        if not entity_type:
            return "UNKNOWN"
        if entity_type in {"PERSON", "ORG", "GPE", "LOC"}:
            return entity_type
        if "人" in entity_type:
            return "PERSON"
        if "地区" in entity_type or "地" in entity_type:
            return "GPE"
        return "ORG"


class _FallbackCandidateGenerator:
    def __init__(self, kb: _LocalKnowledgeBase):
        self.kb = kb

    def generate(self, mention: str, top_k: int = 10) -> List[Candidate]:
        candidates: List[Candidate] = []
        seen: set[str] = set()

        for entity in self.kb.get_entities_by_alias(mention):
            candidates.append(
                Candidate(
                    entity=entity,
                    score=0.95,
                    method="alias_exact",
                    metadata={"match_type": "alias_exact"},
                )
            )
            seen.add(entity.entity_id)

        for entity in self.kb.get_entities_by_alias_fuzzy(mention, max_results=top_k):
            if entity.entity_id in seen:
                continue
            candidates.append(
                Candidate(
                    entity=entity,
                    score=0.85,
                    method="alias_fuzzy",
                    metadata={"match_type": "alias_fuzzy"},
                )
            )
            seen.add(entity.entity_id)

        return candidates[:top_k]


class EntityLinkingPipeline:
    """实体链接主流水线：NER -> 候选生成 -> 留痕。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.project_root = _project_root()

        self.db = DBWriter(self.config.get("db_path"))
        init_db(str(self.db.db_path))

        self.backend = "local"
        self._init_components()

        logger.info("✅ EntityLinkingPipeline 初始化完成")
        logger.info("   backend=%s", self.backend)
        logger.info("   db=%s", self.db.db_path)

    def _init_components(self) -> None:
        kb_path = self._resolve_local_kb_path()
        self.kb = _LocalKnowledgeBase(kb_path)
        self.vector_index = _NullVectorIndex()
        self.ner = _FallbackNEREngine(self.kb)
        self.candidate_gen = _FallbackCandidateGenerator(self.kb)
        self.disambiguator = _NullDisambiguator()
        self.backend = "local"

    def _resolve_local_kb_path(self) -> Path:
        candidate_paths = [
            self.project_root / "data" / "kb" / "energy_entities.json",
            self.project_root / "data" / "kb.json",
            self.project_root / "data" / "knowledge_base.json",
        ]
        for path in candidate_paths:
            if path.exists():
                return path
        return candidate_paths[0]

    def _record_stage(
        self,
        trace_id: str,
        stage_name: str,
        status: str,
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db.insert_pipeline_step(
            run_id=trace_id,
            stage_name=stage_name,
            status=status,
            message=message,
            payload=payload or {},
        )

    def run(
        self,
        text: str,
        options: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        trace_id = trace_id or options.get("trace_id") or new_trace_id()
        with trace_context(trace_id):
            self.db.insert_pipeline_run(
                run_id=trace_id,
                task_name="entity_linking",
                status="running",
                metadata={
                    "backend": self.backend,
                    "options": options,
                    "mode": "single",
                },
            )
            self._record_stage(
                trace_id,
                "pipeline_start",
                "running",
                "开始实体链接",
                {"text_length": len(text)},
            )

            try:
                result = self._run_single(text=text, options=options, trace_id=trace_id)
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="success",
                    metadata={
                        "backend": self.backend,
                        "stats": result.get("stats", {}),
                        "options": options,
                    },
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "success",
                    "实体链接完成",
                    result.get("stats", {}),
                )
                return result
            except Exception as exc:
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="failed",
                    metadata={
                        "backend": self.backend,
                        "error": str(exc),
                        "options": options,
                    },
                )
                self._record_stage(
                    trace_id, "pipeline_finish", "failed", str(exc), {"error": str(exc)}
                )
                raise PipelineError(str(exc)) from exc

    def run_batch(
        self,
        texts: Sequence[str],
        options: Optional[Dict[str, Any]] = None,
        trace_id_prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for index, text in enumerate(texts, start=1):
            item_trace_id = (
                new_trace_id(prefix=trace_id_prefix) if trace_id_prefix else None
            )
            item_result = self.run(text=text, options=options, trace_id=item_trace_id)
            item_result["batch_index"] = index
            results.append(item_result)
        return results

    def run_with_mentions(
        self,
        text: str,
        mentions: Sequence[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        trace_id = trace_id or options.get("trace_id") or new_trace_id()
        with trace_context(trace_id):
            self.db.insert_pipeline_run(
                run_id=trace_id,
                task_name="entity_linking_mentions",
                status="running",
                metadata={
                    "backend": self.backend,
                    "options": options,
                    "mode": "with_mentions",
                },
            )
            self._record_stage(
                trace_id,
                "pipeline_start",
                "running",
                "开始实体链接(已有mention)",
                {"mention_count": len(mentions)},
            )

            try:
                mention_objs = [
                    StandardMention.from_dict(item)
                    for item in mentions
                    if isinstance(item, dict)
                ]
                result = self._run_linking(
                    text=text,
                    mention_objs=mention_objs,
                    options=options,
                    trace_id=trace_id,
                )
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="success",
                    metadata={
                        "backend": self.backend,
                        "stats": result.get("stats", {}),
                        "options": options,
                    },
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "success",
                    "实体链接完成",
                    result.get("stats", {}),
                )
                return result
            except Exception as exc:
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="failed",
                    metadata={
                        "backend": self.backend,
                        "error": str(exc),
                        "options": options,
                    },
                )
                self._record_stage(
                    trace_id, "pipeline_finish", "failed", str(exc), {"error": str(exc)}
                )
                raise PipelineError(str(exc)) from exc

    def _run_single(
        self, text: str, options: Dict[str, Any], trace_id: str
    ) -> Dict[str, Any]:
        mention_objs = self.ner.extract(text)
        self._record_stage(
            trace_id,
            "ner",
            "success",
            f"NER 完成: {len(mention_objs)} 个 mention",
            {
                "mention_count": len(mention_objs),
                "mentions": [m.to_dict() for m in mention_objs[:20]],
            },
        )
        return self._run_linking(
            text=text, mention_objs=mention_objs, options=options, trace_id=trace_id
        )

    def _run_linking(
        self,
        text: str,
        mention_objs: Sequence[StandardMention],
        options: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        if not mention_objs:
            self._record_stage(
                trace_id, "candidate_generation", "skipped", "未识别到 mention", {}
            )
            empty_stats = {
                "total_mentions": 0,
                "linked": 0,
                "nil": 0,
                "coreference_resolved": 0,
            }
            return {
                "trace_id": trace_id,
                "text": text,
                "results": [],
                "stats": empty_stats,
                "backend": self.backend,
            }

        linkable_types = set(options.get("linkable_types", list(LINKABLE_TYPES)))
        filtered_mentions = [
            item for item in mention_objs if item.mention_type in linkable_types
        ]
        if len(filtered_mentions) != len(mention_objs):
            self._record_stage(
                trace_id,
                "mention_filter",
                "success",
                "过滤不可链接类型",
                {
                    "input_count": len(mention_objs),
                    "filtered_count": len(filtered_mentions),
                },
            )

        results: List[Dict[str, Any]] = []

        for mention_obj in filtered_mentions:
            mention_id = self.db.insert_mention(
                task_id=trace_id,
                doc_id=options.get("doc_id", trace_id),
                mention_text=mention_obj.mention,
                start_idx=mention_obj.char_start,
                end_idx=mention_obj.char_end,
                mention_norm=self._normalize_mention(mention_obj.mention),
                context=self._extract_context(
                    text, mention_obj.char_start, mention_obj.char_end
                ),
            )
            self.db.insert_audit_log(
                mention_id=mention_id,
                link_result_id=0,
                field="mention",
                old_value="",
                new_value=mention_obj.mention,
                reason="NER 抽取",
                actor="ner",
            )

            candidates = self.candidate_gen.generate(mention_obj.mention)
            self._record_stage(
                trace_id,
                "candidate_generation",
                "success",
                f"候选生成完成: {mention_obj.mention}",
                {"mention": mention_obj.mention, "candidate_count": len(candidates)},
            )

            for candidate in candidates:
                self.db.insert_candidate(
                    mention_id=mention_id,
                    candidate_entity_id=candidate.entity.entity_id,
                    candidate_name=candidate.entity.standard_name,
                    score=candidate.score,
                    metadata=candidate.metadata,
                )

            candidate_summary = [
                {
                    "entity_id": candidate.entity.entity_id,
                    "standard_name": candidate.entity.standard_name,
                    "score": candidate.score,
                    "method": candidate.method,
                }
                for candidate in candidates[:10]
            ]

            if not candidates:
                result = mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=0.0,
                    evidence="无候选实体",
                    is_nil=True,
                )
                result["mention_id"] = mention_id
                results.append(result)
                link_result_id = self.db.insert_link_result(
                    mention_id=mention_id,
                    linked_entity_id="",
                    linked_entity_name="",
                    is_nil=True,
                    score=0.0,
                    decision_reason="无候选实体",
                    evidence="无候选实体",
                    model_version="",
                    actor="candidate_generator",
                )
                self.db.insert_audit_log(
                    mention_id=mention_id,
                    link_result_id=link_result_id,
                    field="link_result",
                    old_value=mention_obj.mention,
                    new_value="NIL",
                    reason="候选为空",
                    actor="pipeline",
                )
                continue

            result = mention_obj.to_link_result(
                entity_id="",
                standard_name="",
                confidence=0.0,
                evidence="当前流程仅执行 NER、候选生成与存储，不做消歧",
                is_nil=True,
            )
            result["mention_id"] = mention_id
            result["method"] = "candidate_generation_only"
            result["candidate_count"] = len(candidates)
            result["candidates"] = candidate_summary
            results.append(result)
            link_result_id = self.db.insert_link_result(
                mention_id=mention_id,
                linked_entity_id="",
                linked_entity_name="",
                is_nil=True,
                score=0.0,
                decision_reason="当前流程不做消歧，仅保存候选结果",
                evidence="当前流程仅执行 NER、候选生成与存储，不做消歧",
                model_version="",
                actor="candidate_generation_only",
            )
            self.db.insert_audit_log(
                mention_id=mention_id,
                link_result_id=link_result_id,
                field="link_result",
                old_value=mention_obj.mention,
                new_value="CANDIDATES_SAVED",
                reason="仅执行候选生成与存储",
                actor="pipeline",
            )

        self._record_stage(
            trace_id,
            "coreference",
            "skipped",
            "共指消解不在当前串联范围内",
            {"reason": "当前需求仅包含 NER、候选生成与存储"},
        )

        stats = {
            "total_mentions": len(results),
            "linked": sum(1 for item in results if not item.get("is_nil", True)),
            "nil": sum(1 for item in results if item.get("is_nil", True)),
            "coreference_resolved": sum(
                1 for item in results if item.get("is_coreference", False)
            ),
        }

        return {
            "trace_id": trace_id,
            "text": text,
            "results": results,
            "stats": stats,
            "backend": self.backend,
        }

    @staticmethod
    def _normalize_mention(mention: str) -> str:
        return "".join(mention.split()).lower()

    @staticmethod
    def _extract_context(
        text: str, start_idx: int, end_idx: int, window: int = 80
    ) -> str:
        return text[max(0, start_idx - window) : min(len(text), end_idx + window)]

    def get_knowledge_base(self) -> List[Dict[str, Any]]:
        return self.kb.get_all_entities_dict()

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        with sqlite3.connect(str(self.db.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            run = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id = ?", (trace_id,)
            ).fetchone()
            steps = conn.execute(
                "SELECT * FROM pipeline_step WHERE run_id = ? ORDER BY id", (trace_id,)
            ).fetchall()
            mentions = conn.execute(
                "SELECT * FROM mention WHERE task_id = ? ORDER BY id", (trace_id,)
            ).fetchall()
            candidates = conn.execute(
                """
                SELECT c.*, m.mention_text
                FROM candidate c
                JOIN mention m ON c.mention_id = m.id
                WHERE m.task_id = ?
                ORDER BY c.id
                """,
                (trace_id,),
            ).fetchall()
            results = conn.execute(
                """
                SELECT lr.*, m.mention_text, m.mention_norm, m.context
                FROM link_result lr
                JOIN mention m ON lr.mention_id = m.id
                WHERE m.task_id = ?
                ORDER BY lr.id
                """,
                (trace_id,),
            ).fetchall()
            audits = conn.execute(
                """
                SELECT al.*, m.mention_text
                FROM audit_log al
                LEFT JOIN mention m ON al.mention_id = m.id
                WHERE m.task_id = ? OR al.mention_id IN (SELECT id FROM mention WHERE task_id = ?)
                ORDER BY al.id
                """,
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


if __name__ == "__main__":
    p = EntityLinkingPipeline()
    print(p.run("国家电网有限公司发布了新公告。"))
