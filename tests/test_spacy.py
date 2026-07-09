import spacy
nlp = spacy.load("zh_core_web_md")
doc = nlp("小明吃了红苹果。")

for token in doc:
    # token.text: 当前词
    # token.dep_: 该词充当的依存角色（依赖标签）
    # token.head.text: 该词依附的核心词是什么
    print(f"{token.text} → 依存于 → {token.head.text} (关系: {token.dep_})")