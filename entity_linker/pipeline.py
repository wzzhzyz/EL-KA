"""Pipeline 调度与实体链接主流程。

- 运行时会尝试接入 `EntityAlignmentV0` 的候选生成与 BGE 消歧组件；
- 如果 BGE 模型目录或 `EntityAlignmentV0` 初始化失败，会自动回退到本地 fallback 实现：NER → 候选生成 → 存储；
- 中文共指采用轻量规则模块，按 `enable_coreference` 开关启用；
- 每个 run、每个 stage、每条 mention / candidate / result 都会写入 SQLite。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .adapters import normalize_entity
from .coreference import RuleBasedCoreferenceResolver
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
    _MIN_FUZZY_ALIAS_LENGTH = 3
    _MIN_FUZZY_LENGTH_RATIO = 0.50

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
        """Backward-compatible fuzzy entity lookup without match metadata."""
        return [
            entity
            for entity, _ in self.get_entities_by_alias_fuzzy_with_metadata(
                alias, max_results=max_results
            )
        ]

    @staticmethod
    def _edit_distance(left: str, right: str) -> int:
        """Small dependency-free Levenshtein implementation for candidate evidence."""
        if left == right:
            return 0
        if not left:
            return len(right)
        if not right:
            return len(left)
        previous = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current = [left_index]
            for right_index, right_char in enumerate(right, start=1):
                current.append(
                    min(
                        current[-1] + 1,
                        previous[right_index] + 1,
                        previous[right_index - 1]
                        + (0 if left_char == right_char else 1),
                    )
                )
            previous = current
        return previous[-1]

    def get_entities_by_alias_fuzzy_with_metadata(
        self, mention: str, max_results: int = 5
    ) -> List[Tuple[StandardEntity, Dict[str, Any]]]:
        """Return conservative containment matches with score components for tracing.

        Exact aliases remain the responsibility of ``get_entities_by_alias``.  This
        fallback deliberately rejects short substring matches such as ``北京`` in
        ``北京协和医院`` so a place name cannot pollute an organization candidate set.
        """
        mention = mention.strip()
        if not mention:
            return []
        best_by_entity: Dict[str, Tuple[StandardEntity, Dict[str, Any]]] = {}
        for candidate_alias, entities in self._alias_index.items():
            if not (mention in candidate_alias or candidate_alias in mention):
                continue
            shorter_length = min(len(mention), len(candidate_alias))
            longer_length = max(len(mention), len(candidate_alias))
            if shorter_length < self._MIN_FUZZY_ALIAS_LENGTH:
                continue
            length_ratio = shorter_length / longer_length
            if length_ratio < self._MIN_FUZZY_LENGTH_RATIO:
                continue
            edit_distance = self._edit_distance(mention, candidate_alias)
            edit_similarity = 1.0 - edit_distance / longer_length
            # Containment has a conservative base score; ratio and edit similarity
            # make the evidence inspectable instead of assigning a fixed 0.85.
            score = round(0.35 + 0.35 * length_ratio + 0.30 * edit_similarity, 4)
            metadata = {
                "match_type": "alias_fuzzy",
                "reason": "substring_containment",
                "alias": candidate_alias,
                "mention_length": len(mention),
                "alias_length": len(candidate_alias),
                "length_ratio": round(length_ratio, 4),
                "edit_distance": edit_distance,
                "edit_similarity": round(edit_similarity, 4),
                "score": score,
            }
            for entity in entities:
                previous = best_by_entity.get(entity.entity_id)
                if previous is None or score > float(previous[1]["score"]):
                    best_by_entity[entity.entity_id] = (entity, metadata)
        ranked = sorted(
            best_by_entity.values(),
            key=lambda item: (
                float(item[1]["score"]),
                len(item[1]["alias"]),
                item[0].entity_id,
            ),
            reverse=True,
        )
        return ranked[:max_results]

    def get_all_entities(self) -> List[StandardEntity]:
        return list(self.entities)

    def get_all_entities_dict(self) -> List[Dict[str, Any]]:
        return [entity.to_dict() for entity in self.entities]


class _NullVectorIndex:
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        return []


class _FallbackRuleDisambiguator:
    """本地 fallback 消歧器。

    BGE/LLM 未就绪时，仍需要给 HTTP 服务提供可验收的初步链接能力：
    - 候选分数来自 Candidate Generation（alias_exact / alias_fuzzy）；
    - 选择最高分候选作为链接结果；
    - 再交由 NIL 阈值判断是否低置信拒识。

    该实现只作为 7.7 阶段的轻量规则兜底，不替代后续 BGE/LLM 消歧模块。
    """

    def __init__(
        self,
        nil_threshold: float = 0.90,
        llm_trigger_threshold: float = 0.65,
    ) -> None:
        self.nil_threshold = nil_threshold
        self.llm_trigger_threshold = llm_trigger_threshold

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
        ranked = sorted(
            candidates,
            key=lambda item: (
                float(item.score),
                1 if item.method == "alias_exact" else 0,
                len(item.entity.standard_name),
            ),
            reverse=True,
        )
        best = ranked[0]
        evidence_parts = [
            f"fallback规则消歧选择最高分候选: {best.entity.standard_name}",
            f"候选分数={best.score:.2f}",
            f"命中方式={best.method}",
            f"NIL阈值={self.nil_threshold:.2f}",
        ]
        if best.score < self.llm_trigger_threshold:
            evidence_parts.append(
                f"低于LLM触发阈值={self.llm_trigger_threshold:.2f}，可进入后续LLM兜底"
            )
        return {
            "entity": best.entity,
            "score": float(best.score),
            "method": "fallback_rule",
            "evidence": "；".join(evidence_parts),
            "decision_reason": "fallback规则消歧完成",
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

        for entity, fuzzy_metadata in self.kb.get_entities_by_alias_fuzzy_with_metadata(
            mention, max_results=top_k
        ):
            if entity.entity_id in seen:
                continue
            candidates.append(
                Candidate(
                    entity=entity,
                    score=float(fuzzy_metadata["score"]),
                    method="alias_fuzzy",
                    metadata=fuzzy_metadata,
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
        if self.backend != "entity_alignment" and self.config.get("prefer_bge", True):
            logger.warning(
                "当前配置强制优先 BGE，但实际未成功初始化，继续使用本地 fallback"
            )

        logger.info("✅ EntityLinkingPipeline 初始化完成")
        logger.info("   backend=%s", self.backend)
        logger.info("   db=%s", self.db.db_path)

    def _init_components(self) -> None:
        enabled = self.config.get("entity_alignment", {}).get("enabled", True)
        prefer_bge = self.config.get("prefer_bge", True)
        if enabled and prefer_bge:
            try:
                self._init_entity_alignment_components()
                return
            except Exception as exc:
                logger.warning(
                    "EntityAlignmentV0 组件初始化失败，将回退到本地 fallback：%s",
                    exc,
                )

        kb_path = self._resolve_local_kb_path()
        self.kb = _LocalKnowledgeBase(kb_path)
        self.vector_index = _NullVectorIndex()
        self.ner = _FallbackNEREngine(self.kb)
        self.candidate_gen = _FallbackCandidateGenerator(self.kb)
        self.disambiguator = _FallbackRuleDisambiguator(
            nil_threshold=float(self.config.get("nil_threshold", 0.30)),
            llm_trigger_threshold=float(
                self.config.get(
                    "bge_llm_trigger_threshold",
                    self.config.get("llm_trigger_threshold", 0.65),
                )
            ),
        )
        self.backend = "local"

    def _resolve_local_kb_path(self) -> Path:
        configured_kb = self.config.get("kb_path")
        if configured_kb:
            existing = self._resolve_existing_path([configured_kb])
            if existing:
                return Path(existing)

        candidate_paths = [
            self.project_root / "data" / "kb" / "energy_entities.json",
            self.project_root / "data" / "kb.json",
            self.project_root / "data" / "knowledge_base.json",
        ]
        for path in candidate_paths:
            if path.exists():
                return path
        return candidate_paths[0]

    def _resolve_entity_alignment_src_path(self) -> Optional[Path]:
        repo_path = self.project_root / "EntityAlignmentV0"
        if repo_path.exists() and repo_path.is_dir():
            return repo_path
        return None

    def _reload_kb_if_needed(self, options: Dict[str, Any]) -> None:
        kb_path = options.get("kb_path")
        if not kb_path:
            return

        resolved = self._resolve_existing_path([kb_path])
        if not resolved:
            raise PipelineError(f"指定的知识库文件不存在: {kb_path}")

        if self.backend == "local":
            self.kb = _LocalKnowledgeBase(Path(resolved))
            self.ner = _FallbackNEREngine(self.kb)
            self.candidate_gen = _FallbackCandidateGenerator(self.kb)
            logger.info("已按请求加载本地知识库: %s", resolved)
            return

        if self.backend == "entity_alignment":
            self.config["kb_path"] = resolved
            try:
                self._init_entity_alignment_components()
                logger.info("已按请求重新加载 EntityAlignmentV0 知识库: %s", resolved)
            except Exception as exc:
                raise PipelineError(
                    f"按请求重新加载 EntityAlignmentV0 知识库失败: {exc}"
                ) from exc

    def _read_entity_alignment_project_config(self) -> Dict[str, Any]:
        config_path = self.project_root / "EntityAlignmentV0" / "config.yaml"
        if not config_path.exists():
            return {}
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML 未安装，跳过读取 EntityAlignmentV0/config.yaml")
            return {}

        try:
            with config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning(
                "读取 EntityAlignmentV0/config.yaml 失败，将使用默认配置: %s",
                exc,
            )
            return {}

    def _resolve_existing_path(self, candidates: Sequence[Path | str]) -> Optional[str]:
        for candidate in candidates:
            if candidate is None:
                continue
            path = candidate if isinstance(candidate, Path) else Path(str(candidate))
            if not path.is_absolute():
                path = self.project_root / path
            if path.exists():
                return str(path)
        return None

    def _build_entity_alignment_config(self) -> Dict[str, Any]:
        entity_alignment_cfg = self.config.get("entity_alignment", {}) or {}
        project_cfg = self._read_entity_alignment_project_config()
        project_disambiguator = project_cfg.get("disambiguator", {}) or {}
        project_llm = project_cfg.get("llm_fallback", {}) or {}
        user_disambiguator = entity_alignment_cfg.get("disambiguator", {}) or {}
        user_llm = entity_alignment_cfg.get("llm_fallback", {}) or {}

        fallback_kb_path = self._resolve_local_kb_path()
        configured_kb_path = self.config.get("kb_path")
        resolved_kb_path = self._resolve_existing_path([configured_kb_path])
        if resolved_kb_path is None and configured_kb_path:
            logger.warning(
                "配置的知识库路径不存在，回退到默认知识库: %s",
                fallback_kb_path,
            )
        knowledge_base_path = resolved_kb_path or str(fallback_kb_path)

        bge_candidates = [
            entity_alignment_cfg.get("bge_model_path"),
            entity_alignment_cfg.get("model_path"),
            project_cfg.get("bge_model_path"),
            self.config.get("bge_model_path"),
            self.project_root
            / "EntityAlignmentV0"
            / "models_cache"
            / "bge-large-zh-v1.5",
            self.project_root / "EntityAlignmentV0" / "models_cache" / "bge-small-zh",
            self.project_root / "data" / "bge-large-zh-v1.5",
            self.project_root / "data" / "bge-small-zh",
        ]
        bge_path = self._resolve_existing_path(bge_candidates)
        if bge_path is None:
            bge_path = str(
                entity_alignment_cfg.get("bge_model_path")
                or entity_alignment_cfg.get("model_path")
                or project_cfg.get("bge_model_path")
                or self.config.get("bge_model_path")
                or self.project_root
                / "EntityAlignmentV0"
                / "models_cache"
                / "bge-large-zh-v1.5"
            )

        reranker_model_path = self._resolve_existing_path(
            [
                entity_alignment_cfg.get("reranker_model_path"),
                project_cfg.get("reranker_model_path"),
                self.project_root
                / "EntityAlignmentV0"
                / "models_cache"
                / "bge-reranker-large",
                self.project_root
                / "EntityAlignmentV0"
                / "models_cache"
                / "bge-reranker-base",
            ]
        ) or str(
            entity_alignment_cfg.get("reranker_model_path")
            or project_cfg.get("reranker_model_path")
            or self.project_root
            / "EntityAlignmentV0"
            / "models_cache"
            / "bge-reranker-large"
        )

        llm_fallback_cfg = {
            "enabled": False,
            **(project_llm or {}),
            **(user_llm or {}),
        }
        llm_fallback_cfg["enabled"] = bool(llm_fallback_cfg.get("enabled", False))

        config = {
            "knowledge_base": {
                "type": "json",
                "path": knowledge_base_path,
            },
            "bge_model_path": bge_path,
            "disambiguator": {
                "nil_threshold": self.config.get(
                    "nil_threshold",
                    user_disambiguator.get(
                        "nil_threshold",
                        project_disambiguator.get("nil_threshold", 0.65),
                    ),
                ),
                "bge_llm_trigger_threshold": self.config.get(
                    "bge_llm_trigger_threshold",
                    user_disambiguator.get(
                        "bge_llm_trigger_threshold",
                        project_disambiguator.get("bge_llm_trigger_threshold", 0.55),
                    ),
                ),
            },
            "reranker_enabled": entity_alignment_cfg.get(
                "reranker_enabled",
                project_cfg.get("reranker_enabled", False),
            ),
            "reranker_model_path": reranker_model_path,
            "reranker_top_k": entity_alignment_cfg.get(
                "reranker_top_k",
                project_cfg.get("reranker_top_k", 6),
            ),
            "reranker_weight": entity_alignment_cfg.get(
                "reranker_weight",
                project_cfg.get("reranker_weight", 0.7),
            ),
            "bge_reranker_weight": entity_alignment_cfg.get(
                "bge_reranker_weight",
                project_cfg.get("bge_reranker_weight", 0.3),
            ),
            "llm_fallback": llm_fallback_cfg,
        }
        logger.info(
            "已读取 EntityAlignmentV0 配置，使用 BGE 模型路径: %s，Reranker: %s",
            config["bge_model_path"],
            config["reranker_enabled"],
        )
        return config

    def _init_entity_alignment_components(self) -> None:
        src_path = self._resolve_entity_alignment_src_path()
        if src_path is None:
            raise RuntimeError("未找到 EntityAlignmentV0/src，请确认仓库路径存在")

        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            logger.info("已加入 EntityAlignmentV0 源码路径: %s", src_path)

        from src.core.candidate import CandidateGenerator as EACandidateGenerator
        from src.core.disambiguate import Disambiguator as EADisambiguator
        from src.knowledge.kb_manager import KnowledgeBase as EAKnowledgeBase
        from src.knowledge.vector_index import VectorIndex as EAVectorIndex

        ea_config = self._build_entity_alignment_config()
        bge_path = ea_config["bge_model_path"]
        if not Path(bge_path).exists():
            raise RuntimeError(f"BGE 模型路径不存在: {bge_path}")

        self.kb = EAKnowledgeBase(ea_config["knowledge_base"])
        self.vector_index = EAVectorIndex(ea_config["bge_model_path"], kb=self.kb)
        self.vector_index.build(self.kb.get_all_entities())
        self.ner = _FallbackNEREngine(self.kb)
        self.candidate_gen = EACandidateGenerator(self.kb, self.vector_index)
        self.disambiguator = EADisambiguator(ea_config)
        self.backend = "entity_alignment"
        logger.info("✅ 已接入 EntityAlignmentV0 候选生成与 BGE 消歧组件")

    def _record_stage(
        self,
        trace_id: str,
        stage_name: str,
        status: str,
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.db.insert_pipeline_step(
            run_id=trace_id,
            stage_name=stage_name,
            status=status,
            message=message,
            payload=payload or {},
            conn=conn,
        )

    def run(
        self,
        text: str,
        options: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        conn: sqlite3.Connection | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        trace_id = trace_id or options.get("trace_id") or new_trace_id()
        with trace_context(trace_id):
            self._reload_kb_if_needed(options)
            mentions = options.get("mentions") or []
            if mentions:
                return self.run_with_mentions(
                    text=text,
                    mentions=mentions,
                    options=options,
                    trace_id=trace_id,
                    conn=conn,
                    insert_run=False,
                )

            self.db.insert_pipeline_run(
                run_id=trace_id,
                task_name="entity_linking",
                status="running",
                metadata={
                    "backend": self.backend,
                    "options": options,
                    "mode": "single",
                    "input_contract": "text_with_mentions",
                },
                conn=conn,
            )
            self._record_stage(
                trace_id,
                "pipeline_start",
                "running",
                "开始实体链接",
                {
                    "text_length": len(text),
                    "input_contract": "text_with_mentions",
                    "allow_ner_fallback": bool(
                        options.get("allow_ner_fallback", False)
                    ),
                },
                conn=conn,
            )

            try:
                if options.get("allow_ner_fallback", False):
                    result = self._run_single(
                        text=text, options=options, trace_id=trace_id, conn=conn
                    )
                else:
                    result = {
                        "trace_id": trace_id,
                        "text": text,
                        "results": [],
                        "stats": {
                            "total_mentions": 0,
                            "linked": 0,
                            "nil": 0,
                            "coreference_resolved": 0,
                        },
                        "backend": self.backend,
                        "input_mode": "provided_mentions_required",
                        "message": "未提供 mentions，且未开启 NER fallback",
                    }
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="success",
                    metadata={
                        "backend": self.backend,
                        "stats": result.get("stats", {}),
                        "options": options,
                    },
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "success",
                    "实体链接完成",
                    result.get("stats", {}),
                    conn=conn,
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
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "failed",
                    str(exc),
                    {"error": str(exc)},
                    conn=conn,
                )
                raise PipelineError(str(exc)) from exc

    def run_batch(
        self,
        texts: Sequence[str],
        options: Optional[Dict[str, Any]] = None,
        trace_id_prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        with self.db.transaction() as conn:
            for index, text in enumerate(texts, start=1):
                item_trace_id = (
                    new_trace_id(prefix=trace_id_prefix) if trace_id_prefix else None
                )
                item_result = self.run(
                    text=text,
                    options=options,
                    trace_id=item_trace_id,
                    conn=conn,
                )
                item_result["batch_index"] = index
                results.append(item_result)
        return results

    def run_with_mentions(
        self,
        text: str,
        mentions: Sequence[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        conn: sqlite3.Connection | None = None,
        insert_run: bool = True,
    ) -> Dict[str, Any]:
        options = options or {}
        trace_id = trace_id or options.get("trace_id") or new_trace_id()
        with trace_context(trace_id):
            if insert_run:
                self.db.insert_pipeline_run(
                    run_id=trace_id,
                    task_name="entity_linking_mentions",
                    status="running",
                    metadata={
                        "backend": self.backend,
                        "options": options,
                        "mode": "with_mentions",
                    },
                    conn=conn,
                )
            self._record_stage(
                trace_id,
                "pipeline_start",
                "running",
                "开始实体链接(已有mention)",
                {"mention_count": len(mentions), "input_mode": "provided_mentions"},
                conn=conn,
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
                    conn=conn,
                )
                self.db.update_pipeline_run(
                    run_id=trace_id,
                    status="success",
                    metadata={
                        "backend": self.backend,
                        "stats": result.get("stats", {}),
                        "options": options,
                    },
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "success",
                    "实体链接完成",
                    result.get("stats", {}),
                    conn=conn,
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
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "pipeline_finish",
                    "failed",
                    str(exc),
                    {"error": str(exc)},
                    conn=conn,
                )
                raise PipelineError(str(exc)) from exc

    def _run_single(
        self,
        text: str,
        options: Dict[str, Any],
        trace_id: str,
        conn: sqlite3.Connection | None = None,
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
                "input_mode": "ner_extracted",
            },
            conn=conn,
        )
        return self._run_linking(
            text=text,
            mention_objs=mention_objs,
            options=options,
            trace_id=trace_id,
            conn=conn,
        )

    def _run_linking(
        self,
        text: str,
        mention_objs: Sequence[StandardMention],
        options: Dict[str, Any],
        trace_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> Dict[str, Any]:
        if not mention_objs:
            self._record_stage(
                trace_id,
                "candidate_generation",
                "skipped",
                "未识别到 mention",
                {},
                conn=conn,
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
        if options.get("enable_coreference", False):
            linkable_types.update({"PRON", "NOUN", "UNKNOWN"})
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
                conn=conn,
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
                conn=conn,
            )
            self.db.insert_audit_log(
                mention_id=mention_id,
                link_result_id=0,
                field="mention",
                old_value="",
                new_value=mention_obj.mention,
                reason="provided_mentions" if options.get("mentions") else "NER 抽取",
                actor="ner",
                conn=conn,
            )

            candidates = self.candidate_gen.generate(mention_obj.mention)
            self._record_stage(
                trace_id,
                "candidate_generation",
                "success",
                f"候选生成完成: {mention_obj.mention}",
                {"mention": mention_obj.mention, "candidate_count": len(candidates)},
                conn=conn,
            )

            candidate_rows = [
                {
                    "candidate_entity_id": candidate.entity.entity_id,
                    "candidate_name": candidate.entity.standard_name,
                    "score": candidate.score,
                    "metadata": candidate.metadata,
                }
                for candidate in candidates
            ]
            if candidate_rows:
                self.db.batch_insert_candidates(
                    mention_id=mention_id,
                    candidates=candidate_rows,
                    conn=conn,
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
                result["link_basis"] = {
                    "reason": "no_candidates",
                    "evidence": "无候选实体",
                    "source": "candidate_generation",
                }
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
                    conn=conn,
                )
                self.db.insert_audit_log(
                    mention_id=mention_id,
                    link_result_id=link_result_id,
                    field="link_result",
                    old_value=mention_obj.mention,
                    new_value="NIL",
                    reason="候选为空",
                    actor="pipeline",
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "disambiguation",
                    "skipped",
                    "无候选实体，跳过消歧",
                    {"mention": mention_obj.mention},
                    conn=conn,
                )
                self._record_stage(
                    trace_id,
                    "nil_decision",
                    "success",
                    "NIL 决策完成",
                    {"mention": mention_obj.mention, "is_nil": True},
                    conn=conn,
                )
                continue

            disambiguation_result = self._disambiguate_mention(
                mention_obj=mention_obj,
                candidates=candidates,
                text=text,
                options=options,
                trace_id=trace_id,
                conn=conn,
            )

            if disambiguation_result["is_nil"]:
                result = mention_obj.to_link_result(
                    entity_id="",
                    standard_name="",
                    confidence=0.0,
                    evidence=disambiguation_result["evidence"],
                    is_nil=True,
                )
                result["mention_id"] = mention_id
                result["method"] = disambiguation_result.get("method", "disambiguation")
                result["candidate_count"] = len(candidates)
                result["candidates"] = candidate_summary
                result["link_basis"] = {
                    "reason": "nil_threshold",
                    "evidence": disambiguation_result.get("evidence", ""),
                    "source": "disambiguation",
                }
                results.append(result)
                link_result_id = self.db.insert_link_result(
                    mention_id=mention_id,
                    linked_entity_id="",
                    linked_entity_name="",
                    is_nil=True,
                    score=disambiguation_result["score"],
                    decision_reason=disambiguation_result.get(
                        "decision_reason", "NIL 决策"
                    ),
                    evidence=disambiguation_result["evidence"],
                    model_version="",
                    actor=disambiguation_result.get("method", "disambiguation"),
                    conn=conn,
                )
                self.db.insert_audit_log(
                    mention_id=mention_id,
                    link_result_id=link_result_id,
                    field="link_result",
                    old_value=mention_obj.mention,
                    new_value="NIL",
                    reason="消歧未命中或低于 NIL 阈值",
                    actor="pipeline",
                    conn=conn,
                )
                continue

            entity = disambiguation_result["entity"]
            result = mention_obj.to_link_result(
                entity_id=entity.entity_id,
                standard_name=entity.standard_name,
                confidence=disambiguation_result["score"],
                evidence=disambiguation_result["evidence"],
                is_nil=False,
            )
            result["mention_id"] = mention_id
            result["method"] = disambiguation_result.get("method", "disambiguation")
            result["candidate_count"] = len(candidates)
            result["candidates"] = candidate_summary
            result["link_basis"] = {
                "reason": "entity_selected",
                "entity_id": entity.entity_id,
                "standard_name": entity.standard_name,
                "evidence": disambiguation_result.get("evidence", ""),
                "source": "disambiguation",
            }
            results.append(result)
            link_result_id = self.db.insert_link_result(
                mention_id=mention_id,
                linked_entity_id=entity.entity_id,
                linked_entity_name=entity.standard_name,
                is_nil=False,
                score=disambiguation_result["score"],
                decision_reason=disambiguation_result.get(
                    "decision_reason", "disambiguation 成功"
                ),
                evidence=disambiguation_result["evidence"],
                model_version="",
                actor=disambiguation_result.get("method", "disambiguation"),
                conn=conn,
            )
            self.db.insert_audit_log(
                mention_id=mention_id,
                link_result_id=link_result_id,
                field="link_result",
                old_value=mention_obj.mention,
                new_value=entity.entity_id,
                reason="实体链接成功",
                actor="pipeline",
                conn=conn,
            )

        if options.get("enable_coreference", False):
            resolver = RuleBasedCoreferenceResolver(
                nil_threshold=float(options.get("coreference_nil_threshold", 0.55)),
                enable_collective_ambiguity_rejection=bool(options.get("enable_collective_ambiguity_rejection", True)),
            )
            before_resolved = sum(
                1 for item in results if item.get("is_coreference", False)
            )
            results = resolver.resolve_link_results(results, text=text)
            after_resolved = sum(
                1 for item in results if item.get("is_coreference", False)
            )
            self._record_stage(
                trace_id,
                "coreference",
                "success",
                "规则共指消解完成",
                {
                    "input_count": len(results),
                    "resolved_count": after_resolved - before_resolved,
                    "nil_threshold": float(
                        options.get("coreference_nil_threshold", 0.55)
                    ),
                    "collective_ambiguity_rejection_enabled": bool(options.get("enable_collective_ambiguity_rejection", True)),
                },
                conn=conn,
            )
        else:
            self._record_stage(
                trace_id,
                "coreference",
                "skipped",
                "共指消解未启用",
                {"reason": "enable_coreference=false"},
                conn=conn,
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
            "input_mode": "provided_mentions",
        }

    def _disambiguate_mention(
        self,
        mention_obj: StandardMention,
        candidates: List[Candidate],
        text: str,
        options: Dict[str, Any],
        trace_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> Dict[str, Any]:
        context = self._extract_context(
            text, mention_obj.char_start, mention_obj.char_end
        )
        disambiguation = self.disambiguator.disambiguate(
            mention=mention_obj.mention,
            candidates=candidates,
            context=context,
        )
        entity = disambiguation.get("entity")
        if isinstance(entity, dict):
            entity = normalize_entity(entity)
        elif entity is None:
            entity = None

        score = float(disambiguation.get("score", 0.0))
        method = disambiguation.get("method", "disambiguation")
        evidence = disambiguation.get("evidence", "")
        decision_reason = disambiguation.get(
            "decision_reason", evidence or "消歧返回结果"
        )
        self._record_stage(
            trace_id,
            "disambiguation",
            "success",
            f"消歧完成: {mention_obj.mention}",
            {
                "mention": mention_obj.mention,
                "candidate_count": len(candidates),
                "method": method,
                "score": score,
                "entity_id": entity.entity_id if entity else None,
            },
            conn=conn,
        )

        nil_threshold = float(
            options.get(
                "nil_threshold",
                getattr(self.disambiguator, "nil_threshold", 0.0),
            )
        )
        if "nil_threshold" in options and evidence:
            evidence = f"{evidence}；本次请求NIL阈值={nil_threshold:.2f}"
        is_nil = entity is None or score < nil_threshold
        self._record_stage(
            trace_id,
            "nil_decision",
            "success",
            "NIL 判定完成",
            {
                "mention": mention_obj.mention,
                "is_nil": is_nil,
                "score": score,
                "nil_threshold": nil_threshold,
            },
            conn=conn,
        )

        return {
            "entity": entity,
            "score": score,
            "method": method,
            "evidence": evidence,
            "decision_reason": decision_reason,
            "is_nil": is_nil,
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
        return self.db.get_trace(trace_id)

    def list_runs(
        self, status: str | None = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self.db.list_pipeline_runs(status=status, limit=limit)


if __name__ == "__main__":
    p = EntityLinkingPipeline()
    print(p.run("国家电网有限公司发布了新公告。"))
