"""
Æsirian Observability — OpenTelemetry + Logfire Integration

One-line setup: `configure_observability()` in main entry points.
Provides: structured logging, distributed traces, metrics, cost tracking.
"""

from __future__ import annotations
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Callable, Any
import os
import time
import logging
import inspect
import structlog

# 配置 structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


# ─── Logfire Configuration ───

_LOGFIRE_CONFIGURED = False


def configure_observability(
    service_name: str = "aesirian",
    environment: str = None,
    logfire_token: str = None,
    sample_rate: float = 1.0,
) -> bool:
    """
    配置全局观测性（Logfire + OTel）。

    Args:
        service_name: 服务名称
        environment: 环境
        logfire_token: Logfire API token（可选，从环境变量 LOGFIRE_TOKEN 读取）
        sample_rate: 采样率

    Returns:
        是否成功配置
    """
    global _LOGFIRE_CONFIGURED

    if _LOGFIRE_CONFIGURED:
        return True

    try:
        import logfire

        token = logfire_token or os.environ.get("LOGFIRE_TOKEN")
        if token:
            logfire.configure(
                service_name=service_name,
                environment=environment or os.environ.get("ENVIRONMENT", "development"),
                token=token,
                sample_rate=sample_rate,
                send_to_logfire=True,
            )
        else:
            # 本地模式：只输出到控制台
            # O2 兼容：logfire v5 的 ConsoleOptions 参数为 min_log_level，
            # 旧版使用 min_level；运行时探测签名，避免 TypeError。
            _console_kwargs = {"colors": True}
            try:
                _cs_params = set(inspect.signature(logfire.ConsoleOptions).parameters)
            except (ValueError, TypeError):
                _cs_params = set()
            if "min_log_level" in _cs_params:
                _console_kwargs["min_log_level"] = "info"
            elif "min_level" in _cs_params:
                _console_kwargs["min_level"] = "info"
            logfire.configure(
                service_name=service_name,
                environment=environment or os.environ.get("ENVIRONMENT", "development"),
                send_to_logfire=False,
                console=logfire.ConsoleOptions(**_console_kwargs),
            )

        # 设置全局属性（O2 兼容：logfire v5 移除 set_global_tags，改为 with_tags）
        _set_tags = getattr(logfire, "set_global_tags", None)
        if callable(_set_tags):
            _set_tags({
                "service": service_name,
                "version": "0.1.0",
            })

        _LOGFIRE_CONFIGURED = True
        log.info("observability_configured", service=service_name, has_token=bool(token))
        return True

    except ImportError:
        log.warning("logfire_not_installed", message="pip install logfire to enable")
        return False
    except Exception as e:
        log.error("observability_config_failed", error=str(e))
        return False


# ─── Tracing Decorators ───

def trace_span(name: str = None, attributes: dict = None):
    """
    装饰器：为函数创建追踪 span。

    Usage:
        @trace_span("chapter_generate", {"project_id": "xxx"})
        async def generate_chapter(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            try:
                import logfire
                with logfire.span(span_name, attributes=attributes or {}) as span:
                    start = time.perf_counter()
                    try:
                        result = func(*args, **kwargs)
                        span.set_attribute("success", True)
                        return result
                    except Exception as e:
                        span.set_attribute("success", False)
                        span.set_attribute("error", str(e))
                        span.record_exception(e)
                        raise
                    finally:
                        span.set_attribute("duration_ms", (time.perf_counter() - start) * 1000)
            except ImportError:
                return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            try:
                import logfire
                with logfire.span(span_name, attributes=attributes or {}) as span:
                    start = time.perf_counter()
                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("success", True)
                        return result
                    except Exception as e:
                        span.set_attribute("success", False)
                        span.set_attribute("error", str(e))
                        span.record_exception(e)
                        raise
                    finally:
                        span.set_attribute("duration_ms", (time.perf_counter() - start) * 1000)
            except ImportError:
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def trace_context(name: str, attributes: dict = None):
    """上下文管理器：手动创建 span"""
    try:
        import logfire
        with logfire.span(name, attributes=attributes or {}) as span:
            start = time.perf_counter()
            try:
                yield span
                span.set_attribute("success", True)
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                span.record_exception(e)
                raise
            finally:
                span.set_attribute("duration_ms", (time.perf_counter() - start) * 1000)
    except ImportError:
        yield None


# ─── Metrics Helpers ───

def metric_counter(name: str, value: float = 1, attributes: dict = None):
    """记录计数器指标"""
    try:
        import logfire
        logfire.metric(name, value, attributes=attributes or {})
    except ImportError:
        pass


def metric_histogram(name: str, value: float, attributes: dict = None):
    """记录直方图指标"""
    try:
        import logfire
        logfire.metric(name, value, attributes=attributes or {})
    except ImportError:
        pass


def metric_gauge(name: str, value: float, attributes: dict = None):
    """记录仪表盘指标"""
    try:
        import logfire
        logfire.metric(name, value, attributes=attributes or {})
    except ImportError:
        pass


# ─── Cost Tracking ───

def track_llm_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float = None,
    project_id: str = None,
    operation: str = "generate",
):
    """记录 LLM 调用成本"""
    attrs = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "operation": operation,
    }
    if project_id:
        attrs["project_id"] = project_id
    if cost_usd is not None:
        attrs["cost_usd"] = cost_usd

    metric_counter("llm_calls_total", 1, attrs)
    metric_counter("llm_tokens_total", input_tokens + output_tokens, attrs)
    if cost_usd is not None:
        metric_counter("llm_cost_usd_total", cost_usd, attrs)

    log.info("llm_call", **attrs)


# ─── Chapter Generation Tracing ───

@contextmanager
def trace_chapter_generation(project_id: str, chapter_num: int, premise: str = ""):
    """章节生成的完整追踪上下文"""
    with trace_context("chapter_generation", {
        "project_id": project_id,
        "chapter_number": chapter_num,
        "premise_length": len(premise),
    }) as span:
        yield span


@contextmanager
def trace_gate_audit(project_id: str, chapter_num: int, gate_ids: list[str]):
    """门禁审计追踪"""
    with trace_context("gate_audit", {
        "project_id": project_id,
        "chapter_number": chapter_num,
        "gate_count": len(gate_ids),
        "gate_ids": gate_ids,
    }) as span:
        yield span


@contextmanager
def trace_tom_query(project_id: str, operation: str):
    """ToM 引擎查询追踪"""
    with trace_context("tom_query", {
        "project_id": project_id,
        "operation": operation,
    }) as span:
        yield span


@contextmanager
def trace_kg_operation(project_id: str, operation: str, entity_count: int = 0):
    """知识图谱操作追踪"""
    with trace_context("kg_operation", {
        "project_id": project_id,
        "operation": operation,
        "entity_count": entity_count,
    }) as span:
        yield span


# ─── Health Check ───

def health_check() -> dict:
    """健康检查端点数据"""
    status = {
        "observability": "configured" if _LOGFIRE_CONFIGURED else "not_configured",
        "logfire": "available" if _LOGFIRE_CONFIGURED else "unavailable",
    }
    try:
        import logfire
        status["logfire"] = "connected"
    except ImportError:
        status["logfire"] = "not_installed"
    return status


# ─── Auto-configure on import (if token present) ───

if os.environ.get("LOGFIRE_TOKEN") or os.environ.get("AESIR_AUTO_OBSERVABILITY") == "1":
    configure_observability()