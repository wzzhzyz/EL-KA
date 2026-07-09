
import os
import sys
import json
import argparse
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import torch
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
    set_seed,
)
from datasets import Dataset

from datasets import Value

dataset = Dataset.from_list([{"label": 1}])
dataset = dataset.cast_column("label", Value("float32"))  # 强制转换列类型
print(type(dataset[0]["label"]))  # <class 'float'> ✅