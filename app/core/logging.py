import sys
import structlog
from structlog.processors import (
    TimeStamper,
    JSONRenderer,
    StackInfoRenderer,
    format_exc_info,
)
from structlog.types import Processor

from app.core.config import settings


def setup_logging() -> None:
    """配置结构化日志系统"""
    
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    
    if settings.LOG_JSON:
        # 生产环境：JSON 格式日志[reference:2][reference:3]
        processors.append(JSONRenderer())
    else:
        # 开发环境：彩色控制台输出
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """获取结构化日志实例"""
    return structlog.get_logger(name)


# 在模块导入时自动配置
setup_logging()