**阶段一 验收报告**

概述
- 目标：验证实体链接流水线在五个维度（链接准确率、消歧准确率、NIL 检测、别名召回、共指消解）是否满足验收阈值。
- 结论（摘要）：使用仓库中的历史评测报告作为证据时，所有五项阈值均被满足；但历史报告主要基于本地 `fallback` 规则链路而非模型推理，可信度需按来源说明区别对待。

证据与来源（仓库内文件）
- **主报告（历史、规则链路）**: [reports/badcase_threshold_0_90.json](reports/badcase_threshold_0_90.json) — 指标显示 `overall_accuracy=1.0`, `linking_accuracy=1.0`, `nil_f1=1.0`。
- **共指规则评估**: [reports/coreference_rule_eval_detailed.json](reports/coreference_rule_eval_detailed.json) — 共指准确率 `accuracy=1.0`。
- **模型/EA 历史报告（供对比）**: [EntityAlignmentV0/tests/reports/test_linker_report0.json](EntityAlignmentV0/tests/reports/test_linker_report0.json) — 模型路径下历史结果 `accuracy=0.8286`（用于说明本地规则与模型结果差异）。

五维度结果（从历史报告直接提取）
- **链接准确率（Linking Accuracy）**: 1.00  → 达标（阈值 ≥ 0.85）
- **消歧准确率（Disambiguation）**: 1.00（使用 linking_accuracy 作为代理） → 达标（阈值 ≥ 0.85）
- **NIL 检测 F1**: 1.00 → 达标（阈值 ≥ 0.80）
- **别名/简称召回率（Alias Recall）**: 1.00（proxy: non_nil_correct / non_nil_total） → 达标（阈值 ≥ 0.85）
- **共指消解准确率（Coreference）**: 1.00 → 达标（阈值 ≥ 0.80）

关于可信度与差异说明（关键证明）
- 报告来源说明：上表指标直接来自仓库 `reports/` 下的历史评测快照；其中 `reports/badcase_threshold_0_90.json` 的 `backend` 字段为 `local`，表示这些高分是基于**本地规则/回退链路**产生，而非 EntityAlignmentV0 的向量/模型推理。请参见该文件： `backend` 字段即为判定依据。
- 本地 `fallback` 与 模型（EA/BGE）的差异：
  - 本地 `fallback`：以别名精确/模糊匹配、规则化优先、阈值化 NIL 判定与简单规则共指为主；在受控或偏向别名覆盖的样本集上往往得分极高（因为规则直接命中或样本被筛选）。
  - 模型（EntityAlignmentV0 / BGE）：使用向量召回（BGE embedding + FAISS）、基于分数的候选重排与 ML/LLM 辅助判定；在开放/多歧义场景下更能暴露语义错误和召回不足，历史模型报告显示 `accuracy≈0.8286`，显著低于规则链路。
- 结论：历史高分“可信但受限” —— 它们能证明流水线在规则回退时完备且能写入 trace，但不能作为“模型推理下的真实性能”证据。要获得模型路径下可信度高的结论，必须在运行时成功激活 `entity_alignment` 后端并采集输出。

如何在本地复现实验（使用你提供的 `bge-small-zh` CPU 模型）
1) 生成 mini 测试集（仅示例，取前 50 样本）：
```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe - <<'PY'
import json, pathlib
p=pathlib.Path('data/eval/mention_linking_test.json')
J=json.loads(p.read_text(encoding='utf-8'))
J['samples']=J.get('samples',[])[:50]
pathlib.Path('data/eval/mention_linking_mini.json').write_text(json.dumps(J, ensure_ascii=False), encoding='utf-8')
print('mini written')
PY
```

2) 强制 CPU、限制线程并用 `bge-small-zh` 运行评测：
```powershell
$env:CUDA_VISIBLE_DEVICES=""
$env:ELKA_LOG_LEVEL="ERROR"
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
D:/Programfiles/anaconda/envs/EL-KA/python.exe scripts/e2e_from_ground_truth.py --dataset data/eval/mention_linking_mini.json --input-mode mentions --bge-model-path D:\Doc\shixun\2\EL-KA\EntityAlignmentV0\models_cache\bge-small-zh --nil-threshold 0.90 --llm-trigger-threshold 0.65 --badcase-output reports/mini_eval_bge.json
```

3) 验证后端确实为 `entity_alignment`（单条检查）：
```powershell
D:/Programfiles/anaconda/envs/EL-KA/python.exe - <<'PY'
import os
os.environ['ELKA_LOG_LEVEL']='ERROR'
from entity_linker.pipeline import EntityLinkingPipeline
p=EntityLinkingPipeline({'entity_alignment':{'enabled':True},'kb_path':'data/kb/energy_entities.json','prefer_bge':True})
print('backend=', p.backend)
print('candidate=', type(p.candidate_gen).__name__)
print('disambiguator=', type(p.disambiguator).__name__)
print('vector=', type(p.vector_index).__name__)
PY
```

如果运行仍然“卡住”，可采取下列措施：
- 把 `OMP_NUM_THREADS`、`MKL_NUM_THREADS` 设为 `1`，延长等待时间（模型在 CPU 上加载较慢）；
- 逐步调试：先仅初始化 `EntityAlignment` 的 `VectorIndex` 或加载模型脚本来判断卡在哪一阶段（向量索引加载 vs 模型权重加载）；
- 若环境允许，使用 GPU（确保 `torch.cuda.is_available()` 返回 True 且驱动/torch 匹配）。

建议（可信度提升）
- 优先复现一次使用 `--bge-model-path` 的评测并保留 `reports/mini_eval_bge.json`；该文件将作为“模型路径下”的证据。若成功，才把模型路径结果替换历史规则结果作为验收证明。
- 在验收报告中明确标注“证据来源（rules vs model）”并保留原始 `reports/` 快照以便审计。

结尾：文件与证据已存于仓库 `reports/` 下。请回复要我现在（在此环境中）尝试用 `bge-small-zh` 运行 `mini` 并把 `reports/mini_eval_bge.json` 写出，还是仅以历史报告为最终验收证据。
