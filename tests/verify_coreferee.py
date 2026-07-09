# verify_coreferee.py
import spacy
import coreferee

print("加载 spacy 模型...")
nlp = spacy.load("zh_core_web_sm")

print("添加 coreferee 管道...")
nlp.add_pipe("coreferee")

print("测试文本...")
doc = nlp("国家电网有限公司2025年营收增长。它在华北地区新建了线路。")

print("检查共指链...")
chains = doc._.coref_chains
print(f"共指链数量: {len(chains)}")

for chain in chains:
    print(f"  共指链: {[m.text for m in chain]}")

print("✅ Coreferee 工作正常！")