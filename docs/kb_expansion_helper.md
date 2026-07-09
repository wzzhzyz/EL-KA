# 知识库扩充辅助脚本说明

> 日期：2026-07-09  
> 成员视角：欧小红（第三成员，数据处理与实体链接模块实现）  
> 对应任务：开发知识库扩充辅助脚本，支持批量新增实体、别名信息

## 1. 脚本位置

`scripts/expand_knowledge_base.py`

## 2. 支持能力

该脚本支持两类批量操作：

1. `new_entities`：批量新增实体；
2. `alias_updates`：给已有实体批量补充别名。

脚本会在写入前检查：

- `entity_id` 是否重复；
- 别名是否已经存在；
- 别名是否属于其他实体；
- 必填字段是否缺失。

## 3. 输入样例

样例文件：

`data/kb/kb_expansion_sample.json`

结构如下：

```json
{
  "new_entities": [
    {
      "entity_id": "ENT_SAMPLE_9001",
      "entity_name": "示例新能源科技有限公司",
      "entity_type": "NEW_ENERGY_ENTERPRISE",
      "aliases": ["示例新能源"]
    }
  ],
  "alias_updates": [
    {
      "entity_id": "ENT_GEN_0052",
      "aliases": ["腾讯控股集团", "Tencent Holdings"]
    }
  ]
}
```

## 4. Dry-run 校验

建议先执行 dry-run，不写入正式知识库：

```powershell
python scripts\expand_knowledge_base.py --input data\kb\kb_expansion_sample.json --dry-run
```

## 5. 输出到新文件

如需生成扩充后的候选 KB 文件：

```powershell
python scripts\expand_knowledge_base.py --input data\kb\kb_expansion_sample.json --output data\kb\energy_entities_expanded.json
```

## 6. 覆盖正式 KB

确认无误后才允许覆盖正式 KB：

```powershell
python scripts\expand_knowledge_base.py --input data\kb\kb_expansion_sample.json
```

## 7. 注意事项

- 默认不建议直接覆盖正式知识库；
- 新实体 ID 应遵循项目命名规范；
- 别名冲突会记录 warning，需要人工确认；
- 脚本只负责结构化写入，不负责判断实体真实性。
