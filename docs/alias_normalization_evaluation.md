# Alias Normalization Evaluation

## Evaluation setup

- Dataset: `data/eval/alias_normalization_test.json`
- Runtime path: `entity_linker.pipeline._LocalKnowledgeBase` + `_FallbackCandidateGenerator`
- Positive Recall: positive samples whose Top-1 predicted entity ID equals the gold entity ID.
- Negative Precision: negative samples for which the local candidate path returns no KB entity.
- Ambiguous Accuracy: positive `is_ambiguous=true` samples with an explicit candidate list whose Top-1 prediction equals gold.
- Scope: evaluates the project local KB alias lookup/candidate path. Candidate lists are acceptance metadata; this fallback path does not use context to rerank them.

## Overall result

- Total samples: 160
- Positive Recall: 100.00% (140/140)
- Negative Precision: 95.00% (19/20)
- Ambiguous Accuracy: 100.00% (20/20)
- Overall Accuracy: 99.38% (159/160)

## By alias type

|alias_type|result|
|-|-|
|abbreviation|36/36 (100.00%)|
|english_name|15/15 (100.00%)|
|former_name|14/14 (100.00%)|
|industry_alias|10/10 (100.00%)|
|nickname|16/16 (100.00%)|
|regional_alias|10/10 (100.00%)|
|short_name|58/59 (98.31%)|

## By difficulty

|difficulty|result|
|-|-|
|easy|49/49 (100.00%)|
|hard|59/60 (98.33%)|
|medium|51/51 (100.00%)|

## By entity type

|entity_type|result|
|-|-|
|AUTO_MANUFACTURER|6/6 (100.00%)|
|CONSUMER_PRODUCT|4/4 (100.00%)|
|EDUCATIONAL_INSTITUTION|6/6 (100.00%)|
|FINANCIAL_INSTITUTION|5/5 (100.00%)|
|GOVERNMENT_AGENCY|6/6 (100.00%)|
|GRID_COMPANY|11/11 (100.00%)|
|MEDIA_ORG|4/4 (100.00%)|
|MEDICAL_INSTITUTION|6/6 (100.00%)|
|NEW_ENERGY_ENTERPRISE|6/6 (100.00%)|
|POWER_FACILITY|10/10 (100.00%)|
|POWER_GENERATOR|18/18 (100.00%)|
|REGION|17/17 (100.00%)|
|RESEARCH_INSTITUTION|7/7 (100.00%)|
|SOFTWARE_PLATFORM|6/6 (100.00%)|
|TECHNICAL_TERM|20/20 (100.00%)|
|TECH_COMPANY|5/5 (100.00%)|
|TRANSPORTATION_ORG|3/3 (100.00%)|
|UNKNOWN|19/20 (95.00%)|

## Badcase analysis

- `ALIAS_HARD_022`: mention `中国农业银行`, expected `None`, predicted `ENT_GEN_0082`, candidates `['ENT_GEN_0082']`

## Current limitations

- The positive set deliberately uses only KB-recorded aliases; typo_alias is a supported schema value but has no sample because the running KB contains no verified typo aliases.
- The running KB has no multi-owner alias. Candidate-pressure samples reuse real candidates and context from existing LLM datasets, but the local fallback candidate generator does not consume context to rerank candidates.
