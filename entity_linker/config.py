import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import yaml
except Exception:
    yaml = None


@dataclass
class ConfigBase:
    """简单的全局配置读取基类：
    - 优先从指定 `config_path` 加载（YAML/JSON），
    - 否则从环境变量读取，以 `ELKA_` 为前缀。
    可按需扩展为 pydantic、BaseSettings 等更严格实现。
    """

    env: str = "development"
    log_level: str = "INFO"
    db_path: str = "data/trace.db"
    kb_path: str = "data/kb.json"
    model_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, config_path: Optional[str] = None) -> "ConfigBase":
        path = config_path or os.environ.get("ELKA_CONFIG_PATH")
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            if yaml and (path.endswith(".yml") or path.endswith(".yaml")):
                data = yaml.safe_load(text)
            else:
                try:
                    data = json.loads(text)
                except Exception:
                    raise RuntimeError("Unsupported config format or missing PyYAML")
            return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        # fallback to env
        return cls.from_env()

    @classmethod
    def from_env(cls) -> "ConfigBase":
        kwargs = {}
        for k in cls.__annotations__.keys():
            env_key = "ELKA_" + k.upper()
            if env_key in os.environ:
                val = os.environ[env_key]
                # attempt simple type conversions
                ann = cls.__annotations__[k]
                if ann == int:
                    val = int(val)
                elif ann == float:
                    val = float(val)
                elif ann == bool:
                    val = val.lower() in ("1", "true", "yes")
                elif ann == dict or ann == Dict[str, Any]:
                    try:
                        val = json.loads(val)
                    except Exception:
                        val = {"raw": val}
                kwargs[k] = val
        return cls(**kwargs)

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__annotations__.keys()}
