import hanlp

ner = hanlp.load("CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH")

texts = [
    "国家电网",  # 4个字
    "国家电网有限公司",  # 8个字（完整名称）
    "国家电网有限公司在华北地区",  # 更完整
]

for text in texts:
    result = ner(text)
    result_dict = result.to_dict()
    ner_data = result_dict.get('ner/pku', [])
    print(f"文本: {text}")
    print(f"  识别结果: {ner_data}")
    print()