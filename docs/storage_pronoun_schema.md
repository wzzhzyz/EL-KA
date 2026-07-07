# 存储模块：代词回链相关记录字段设计

## 目标

为支持共指消解结果与代词回链，扩展数据库与存储模块记录字段，便于后续查询、回放与评估。

## 建议新增字段（`mention` 表）

- `is_pronoun` BOOLEAN DEFAULT 0
  - 表示该 mention 是否为代词候选。
- `coref_group_id` TEXT NULLABLE
  - 相同共指链的唯一 ID（例如 UUID）。
- `antecedent_mention_id` TEXT NULLABLE
  - 指向本系统中被判定为先行项的 mention 的 `mention_id`。
- `antecedent_entity_id` TEXT NULLABLE
  - 指向先行项解析出的 `entity_id`（若先行项已有链接）。
- `coref_confidence` REAL NULLABLE
  - 回链置信度分数。
- `coref_method` TEXT NULLABLE
  - 标记使用的共指方法（`rule-based` / `neural-small` / `ea-backend`）。

## 备选：在 `link_result` 表中增加冗余字段

为便于快速查询，可在 `link_result` 中增加 `coref_group_id` 与 `antecedent_entity_id` 的冗余列。

## 数据库迁移示例（SQLite）

```sql
ALTER TABLE mention ADD COLUMN is_pronoun INTEGER DEFAULT 0;
ALTER TABLE mention ADD COLUMN coref_group_id TEXT;
ALTER TABLE mention ADD COLUMN antecedent_mention_id TEXT;
ALTER TABLE mention ADD COLUMN antecedent_entity_id TEXT;
ALTER TABLE mention ADD COLUMN coref_confidence REAL;
ALTER TABLE mention ADD COLUMN coref_method TEXT;
```

> 注意：SQLite 在某些旧版本中对 `ALTER TABLE` 支持有限，生产环境推荐备份并通过创建临时表 + 拷贝数据完成迁移。

## `entity_linker/db/writer.py` 更新点

- 新增 `write_mention_coref(...)` 或在 `write_mention` 中增加可选参数接收上述字段并写入。
- 在事务中保证 mention 与 link_result 的原子写入，避免部分回链写入导致不一致。

示例签名：

```python
def write_mention(self, mention_id, run_id, text, start, end, is_pronoun=False, coref_group_id=None, antecedent_mention_id=None, antecedent_entity_id=None, coref_confidence=None, coref_method=None):
    ...
```

## API 层返回字段

在 `/link_with_mentions` 的 `mentions` 项中返回：
- `is_pronoun`
- `coref_group_id`
- `antecedent_mention_id`
- `antecedent_entity_id`
- `coref_confidence`
- `coref_method`

## 查询用例

- 查询某一 `coref_group_id` 下所有 mentions：用于可视化共指链。
- 统计代词回链成功率：`COUNT(antecedent_entity_id IS NOT NULL) / COUNT(is_pronoun=1)`。

## 备注

- 确保 API 与写入函数同时更新文档与迁移脚本。
- 若后续引入外部 KB 的 coref 链接，`coref_group_id` 应支持跨服务传递。