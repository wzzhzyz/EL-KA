#src/core/XMLRobertaForPronounClassification.py
import os
import json
import torch
import torch.nn as nn
from transformers import XLMRobertaForSequenceClassification, AutoTokenizer, PreTrainedModel
from typing import Optional, Dict, Any


class XLMRobertaForPronounClassification(nn.Module):
    """
    复数代词分类模型
    支持统一的保存和加载
    """

    def __init__(self, model_name, tokenizer=None, num_labels=2, load_classifier=False):
        super().__init__()
        self.num_labels = num_labels
        self.tokenizer = tokenizer
        if self.tokenizer is None:
            self.tokenizer=AutoTokenizer.from_pretrained(model_name)

        # 添加特殊标记
        special_tokens_dict = {'additional_special_tokens': ['<target>', '</target>']}
        existing_tokens = tokenizer.get_vocab()
        new_tokens = [t for t in special_tokens_dict['additional_special_tokens'] if t not in existing_tokens]

        added_tokens_num=tokenizer.add_special_tokens(special_tokens_dict)
        if new_tokens:
            print(f"已添加{new_tokens}到词表")
        else:
            print(f"{special_tokens_dict['additional_special_tokens']}已存在，无需添加")

        self.roberta=None
        self.classifier=None
        if model_name:
            # 加载 RoBERTa 主体
            self.roberta = XLMRobertaForSequenceClassification.from_pretrained(
                model_name,
                num_labels=num_labels,
                output_hidden_states=True
            )
            # 扩展词表
            self.roberta.resize_token_embeddings(len(tokenizer))

            # 分类头
            self.classifier = nn.Linear(
                self.roberta.config.hidden_size,
                num_labels
            )

        # 加载分类头（如果需要）
        if load_classifier:
            self._load_classifier(model_name)

    def forward(self, input_ids, attention_mask, target_positions, labels=None):
        outputs = self.roberta.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True
        )
        last_hidden_state = outputs.last_hidden_state
        batch_size = last_hidden_state.size(0)
        target_embeddings = last_hidden_state[
            torch.arange(batch_size, device=last_hidden_state.device),
            target_positions
        ]
        logits = self.classifier(target_embeddings)

        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))

        return loss, logits

    # ============ 统一的保存方法 ============
    def save_pretrained(self, save_directory: str):
        """
        保存完整模型到目录
        包括：RoBERTa主体、分类头、tokenizer、配置
        """
        os.makedirs(save_directory, exist_ok=True)

        # 1. 保存 RoBERTa 主体
        self.roberta.save_pretrained(save_directory)

        # 2. 保存分类头
        torch.save({
            'weight': self.classifier.weight,
            'bias': self.classifier.bias,
        }, f'{save_directory}/classifier.pt')

        # 3. 保存 tokenizer
        self.tokenizer.save_pretrained(save_directory)

        # 4. 保存自定义配置
        custom_config = {
            'num_labels': self.num_labels,
            'vocab_size': len(self.tokenizer),
            'hidden_size': self.roberta.config.hidden_size,
            'special_tokens': ['<target>', '</target>'],
            'model_class': 'XLMRobertaForPronounClassification',
            'base_model': self.roberta.config._name_or_path,
        }
        with open(f'{save_directory}/custom_config.json', 'w', encoding='utf-8') as f:
            json.dump(custom_config, f, indent=2)

        # 5. ✅ 更新 config.json 确保词表大小正确
        config_path = f'{save_directory}/config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config['vocab_size'] = len(self.tokenizer)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

        print(f"✅ 模型已保存到: {save_directory}")
        print(f"   - 词表大小: {len(self.tokenizer)}")
        print(f"   - 分类头: 已保存")

    # ============ 统一的加载方法 ============
    @classmethod
    def from_pretrained(cls, model_path: str, tokenizer: Optional[AutoTokenizer] = None,
                        device: Optional[torch.device] = None):
        """
        从目录加载完整模型
        统一加载逻辑，适用于训练和推理
        """
        if device is None:
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # 1. 加载 tokenizer（如果没有提供）
        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(model_path)

        # 2. 加载自定义配置
        custom_config_path = f'{model_path}/custom_config.json'
        if os.path.exists(custom_config_path):
            with open(custom_config_path, 'r', encoding='utf-8') as f:
                custom_config = json.load(f)
            num_labels = custom_config.get('num_labels', 2)
        else:
            # 兼容旧格式
            config_path = f'{model_path}/config.json'
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            num_labels = config.get('num_labels', 2)

        # 3. 创建模型（从基础模型加载，因为自定义模型没有预训练版本）
        model = cls(
            model_name="",  # 从基础模型初始化
            tokenizer=tokenizer,
            num_labels=num_labels,
            load_classifier=False  # 先不加载，后面手动处理
        )

        # 4. ✅ 加载训练好的 RoBERTa 权重
        try:
            model.roberta = XLMRobertaForSequenceClassification.from_pretrained(
                model_path,
                num_labels=num_labels,
                output_hidden_states=True
            )
            # 扩展词表
            model.roberta.resize_token_embeddings(len(tokenizer))
            print(f"✅ RoBERTa 权重已加载: {model_path}")
        except Exception as e:
            print(f"⚠️ 加载 RoBERTa 权重失败: {e}")
            print("   使用基础模型权重")

        # 5. ✅ 加载分类头
        model.classifier = nn.Linear(
            model.roberta.config.hidden_size,
            num_labels
        )
        classifier_path = f'{model_path}/classifier.pt'
        if os.path.exists(classifier_path):
            state_dict = torch.load(classifier_path, map_location='cpu')
            model.classifier.weight.data = state_dict['weight']
            model.classifier.bias.data = state_dict['bias']
            print(f"✅ 分类头已加载: {classifier_path}")
        else:
            print("⚠️ 未找到分类头权重，使用随机初始化")

        # 6. 移到设备
        model.to(device)
        model.eval()

        return model

    def _load_classifier(self, model_path):
        """内部方法：加载分类头（用于 __init__）"""
        classifier_path = f'{model_path}/classifier.pt'
        if os.path.exists(classifier_path):
            state_dict = torch.load(classifier_path, map_location='cpu')
            self.classifier.weight.data = state_dict['weight']
            self.classifier.bias.data = state_dict['bias']
            return True
        return False

def predict_pronoun(text, char_start, char_end, model, tokenizer, device=None):
    """
    预测指定位置的代词是否为复数
    """
    if device is None:
        device = next(model.parameters()).device  # 自动获取模型设备

    # 1. 插入标记
    marked_text = insert_target_markers(text, char_start, char_end)

    # 2. Tokenize
    encoding = tokenizer(
        marked_text,
        truncation=True,
        max_length=512,
        return_tensors='pt'
    )

    # 3. 将输入移到相同设备
    input_ids = encoding['input_ids'].to(device)
    attention_mask = encoding['attention_mask'].to(device)

    # 4. 找 <target> 位置
    target_id = tokenizer.convert_tokens_to_ids('<target>')
    target_pos = input_ids[0].tolist().index(target_id)

    # 5. 推理
    model.eval()
    with torch.no_grad():
        loss, logits = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            target_positions=torch.tensor([target_pos]).to(device)
        )
        probs = torch.softmax(logits, dim=-1)
        pred = torch.argmax(logits, dim=-1).item()

    return {
        'label': pred,
        'confidence': probs[0][pred].item(),
        'prob_plural': probs[0][1].item()
    }

#插入<target> </target>标记
def insert_target_markers(text, char_start, char_end):
    """
    在指定字符区间前后插入 <target> 和 </target>
    返回: (marked_text, target_token_start_index)
    """
    # 确保 char_end 在文本长度内
    assert char_end <= len(text), f"char_end {char_end} 超出文本长度 {len(text)}"

    # 插入标记（注意：插入顺序从后往前，避免偏移）
    # 先插入结束标记（从后往前插，不影响前面的 char_start）
    text_parts = [
        text[:char_end],  # 目标代词之前的部分
        '</target>',  # 结束标记
        text[char_end:]  # 目标代词之后的部分
    ]
    text = ''.join(text_parts)

    # 再插入开始标记（在 char_start 位置插入，不受刚才插入的影响）
    text_parts = [
        text[:char_start],
        '<target>',
        text[char_start:]
    ]
    marked_text = ''.join(text_parts)

    return marked_text