"""统一的项目异常基类。"""


class EntityLinkerError(Exception):
    """项目级基础异常。"""

    pass


class ValidationError(EntityLinkerError):
    """参数校验失败。"""

    pass


class DatabaseError(EntityLinkerError):
    """数据库写入/读取失败。"""

    pass


class PipelineError(EntityLinkerError):
    """Pipeline 处理异常。"""

    pass


class CandidateError(EntityLinkerError):
    """候选生成相关错误。"""

    pass
