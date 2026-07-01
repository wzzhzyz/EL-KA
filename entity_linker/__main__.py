from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .pipeline import EntityLinkingPipeline


def _load_batch_texts(path: str) -> List[str]:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    if file_path.suffix.lower() == ".jsonl":
        texts: List[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                payload = json.loads(line)
                texts.append(payload.get("text", ""))
            else:
                texts.append(line)
        return texts

    if file_path.suffix.lower() == ".json":
        payload = json.loads(content)
        if isinstance(payload, list):
            return [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in payload
            ]
        if isinstance(payload, dict) and isinstance(payload.get("texts"), list):
            return [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in payload["texts"]
            ]
        if isinstance(payload, dict) and isinstance(payload.get("text"), str):
            return [payload["text"]]

    return [line.strip() for line in content.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="实体链接与知识对齐主程序")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="单条文本输入")
    group.add_argument("--texts", nargs="+", help="多条文本直接输入")
    group.add_argument("--batch-file", help="批量文本文件，支持 txt/json/jsonl")

    parser.add_argument("--trace-id", help="单条文本的 trace_id；批量时作为前缀使用")
    parser.add_argument(
        "--enable-coreference", action="store_true", help="保留共指占位步骤"
    )
    parser.add_argument("--output", help="将结果保存为 JSON 文件")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline = EntityLinkingPipeline()

    options = {"enable_coreference": args.enable_coreference}

    if args.text is not None:
        result = pipeline.run(args.text, options=options, trace_id=args.trace_id)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
    elif args.texts is not None:
        results = pipeline.run_batch(
            args.texts, options=options, trace_id_prefix=args.trace_id
        )
        rendered = json.dumps(results, ensure_ascii=False, indent=2)
    else:
        texts = _load_batch_texts(args.batch_file)
        results = pipeline.run_batch(
            texts, options=options, trace_id_prefix=args.trace_id
        )
        rendered = json.dumps(results, ensure_ascii=False, indent=2)

    print(rendered)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
