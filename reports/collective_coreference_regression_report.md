# 集合共指消解回归验证报告

> 验证范围：Step 8 集合共指规则、专项夹具与历史共指回归
> 说明：本报告不代表实时 HTTP 服务联调结果。

## 1. 验证背景

本轮在保留既有单实体共指语义的前提下，验证显式并列前件的集合指代能力。成功集合结果使用多个去重 `entity_ids`，并保持 `entity_id=null`、`is_collective=true`、`is_nil=false`；不满足规则时保守返回集合未解析 NIL。

## 2. 验证数据与结果

| 验证项 | 结果 | 说明 |
| --- | :---: | --- |
| 集合专项规则评测 | 通过 | 专项数据共 8 条文本，每条包含 1 个待验证指代，共 8 个评测 case；8/8 正确。 |
| 集合精确匹配 | 通过 | 3 个集合成功 case，精确匹配率 100%。 |
| 集合 NIL 判断 | 通过 | 4 个集合未解析 case，判断准确率 100%。 |
| 单实体回归 | 通过 | 专项中 1 个单实体 case 正确。 |
| 历史长文本共指回归 | 通过 | 154 条文本、257 个共指 case，257/257 正确，准确率 100%。 |
| 专项单元测试 | 通过 | 直接执行 `python tests/test_collective_coreference.py`，基于 `unittest` 运行 2 项测试。 |
| 评测数据校验 | 通过 | 0 error、0 warning。 |

历史长文本数据未以 `entity_ids` 标注集合 gold，因此其集合分项指标为 0 个适用 case；这不表示集合能力为 0，而是该历史集不覆盖该专项评测口径。

## 3. 实际执行命令与结果

以下命令在仓库根目录直接执行；`--output NUL` 使用 Windows 空设备，避免生成新的评测产物。

```powershell
python tests\test_collective_coreference.py
```

结果：`unittest` 直接脚本执行通过，运行 2 项测试；本次**未**通过 pytest 框架执行。

```powershell
python scripts\evaluate_coreference_rules.py --dataset data/eval/coreference_collective_test.json --output NUL --fail-on-wrong
```

结果：8 条文本、8 个 case；正确 8、错误 0；整体准确率、集合精确匹配、集合 NIL 判断均为 `1.0000`。

```powershell
python scripts\evaluate_coreference.py --dataset data/eval/coreference_long_text_test.json --output NUL
```

结果：154 条文本、257 个 case；正确 257、错误 0；整体准确率 `1.0000`。

```powershell
python scripts\validate_eval_data.py --output NUL
```

结果：数据校验通过，`errors=0`、`warnings=0`。

```powershell
git diff --check
```

结果：未报告 Markdown 空白或补丁格式错误。Git 输出的 LF/CRLF 提示仅表示检出或提交时可能转换行尾格式，不属于 Markdown 格式错误，也不影响本轮测试结论。

## 4. 典型行为

在“人民日报社和新华通讯社正在飞速发展，他们是我们的未来”中，前两个机构若已分别链接，`他们` 解析为两个去重 ID，且 `entity_id=null`、`is_collective=true`、`is_nil=false`。混合类型、跨句无显式连接、前件未链接或重复实体 ID 的情形均不会被强行合并，而是返回集合未解析 NIL。

## 5. 兼容性与接口说明

历史数据的 gold 未因新增集合能力改写。评测器仅在 gold 明确具有 `entity_ids` 时比较集合结果，故历史回归维持原有单实体/NIL 口径。HTTP 管线会把内部对象放入 `results[i].coreference`；只有原结果为 NIL 且共指成功时，才将集合字段同步至顶层 `results[i]`。完整字段语义见 `docs/api_response_fields.md`。

## 6. 未执行项目与环境限制

未执行实时 HTTP API 自动化测试：当前 Python 环境执行 `python -c "import fastapi"` 返回 `ModuleNotFoundError`，无法导入服务依赖。

未执行 pytest 框架测试：当前 Python 环境执行 `python -m pytest --version` 返回“`No module named pytest`”。专项单元测试采用 Python 自带 `unittest` 的直接脚本方式，故“2 项通过”不依赖 pytest。

未安装新依赖，也未修改环境配置。

## 7. 当前风险

当前实现是可解释的本地规则，不是通用语义共指模型。复杂隐式并列、跨句集合、混合类型集群与嵌套集合仍应保持 NIL；后续如需扩展，应新增独立 gold 与回归用例，避免放宽规则导致错误扩链。
