import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def get_logger(
    name: str, level: Optional[str] = None, log_file: Optional[str] = None
) -> logging.Logger:
    """创建全局可复用 logger。

    - `level` 如 'INFO'、'DEBUG'；若为 None 则读取环境变量 `ELKA_LOG_LEVEL`。
    - `log_file` 若提供则启用文件滚动日志。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    level = (level or os.environ.get("ELKA_LOG_LEVEL", "INFO")).upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    fmt = os.environ.get(
        "ELKA_LOG_FMT", "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    formatter = logging.Formatter(fmt)

    # 控制台输出
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, level, logging.INFO))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # 可选文件输出（滚动）
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setLevel(getattr(logging, level, logging.INFO))
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    logger.propagate = False
    return logger
