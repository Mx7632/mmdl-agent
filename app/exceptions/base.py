"""
提供结构化的异常类型，帮助用户准确识别和处理错误
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type


class AppError(Exception):
    """应用统一异常基类，包含稳定错误码、HTTP 状态码、以及附加上下文信息"""

    code = "app_error"
    status_code = 500

    def __init__(
        self,
        message: str = "Application error",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: Dict[str, Any] = details or {}
        self.original_error = original_error

    def __str__(self) -> str:  # simple formatting
        if getattr(self, "original_error", None):
            return f"{self.message} (原因: {self.original_error})"
        return self.message


class TimeoutError(AppError):
    """下游调用或工作流步骤超时"""

    code = "timeout"
    status_code = 504


class DataMissingError(AppError):
    """必需输入数据缺失或无效"""

    code = "data_missing"
    status_code = 422


class ExternalServiceError(AppError):
    """外部算法服务失败或不可用。"""

    code = "external_service"
    status_code = 502


class ModelError(AppError):
    """模型调用相关错误，包含模型名与可选状态码"""

    code = "model_error"

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs,
    ) -> None:
        details = {"model_name": model_name, "status_code": status_code}
        details.update(kwargs.get("details") or {})
        super().__init__(message, details=details, original_error=kwargs.get("original_error"))


class ToolError(AppError):
    """工具执行相关错误，捕捉Agent的执行行为是否符合预期"""

    code = "tool_error"

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        details = {"tool_name": tool_name, "arguments": arguments}
        details.update(kwargs.get("details") or {})
        super().__init__(message, details=details, original_error=kwargs.get("original_error"))


class ToolNotFoundError(ToolError):
    """找不到指定的工具"""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"找不到工具: {tool_name}", tool_name=tool_name)


class ToolExecutionError(ToolError):
    """工具执行失败"""

    def __init__(self, tool_name: str, arguments: Optional[Dict[str, Any]], error: Exception) -> None:
        super().__init__(
            f"工具 '{tool_name}' 执行失败", tool_name=tool_name, arguments=arguments, original_error=error
        )


class ContextError(AppError):
    """上下文管理相关错误"""

    code = "context_error"


class TokenLimitError(ContextError):
    """Token 限制错误，对话太长，超过了模型的处理能力"""

    code = "token_limit"

    def __init__(self, current_tokens: int, max_tokens: int, message: Optional[str] = None) -> None:
        msg = message or f"Token 数量超过限制: {current_tokens} > {max_tokens}"
        details = {"current_tokens": current_tokens, "max_tokens": max_tokens}
        super().__init__(msg, details=details)


class MaxTurnsError(AppError):
    """熔断，达到最大执行轮次或Agent陷入死循环"""

    code = "max_turns"

    def __init__(self, max_turns: int) -> None:
        super().__init__(
            f"达到最大执行轮次 ({max_turns})，可能存在无限循环", details={"max_turns": max_turns}
        )


class ResponseParseError(AppError):
    """响应解析错误"""

    code = "response_parse"

    def __init__(self, message: str, raw_response: Any = None, **kwargs) -> None:
        # 限制长度以避免日志污染
        details = {"raw_response": str(raw_response)[:500]}
        details.update(kwargs.get("details") or {})
        super().__init__(message, details=details, original_error=kwargs.get("original_error"))


class ConfigurationError(AppError):
    """配置错误"""

    code = "configuration_error"

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs) -> None:
        details = {"config_key": config_key} if config_key else {}
        details.update(kwargs.get("details") or {})
        super().__init__(message, details=details, original_error=kwargs.get("original_error"))


class StreamError(AppError):
    """流式处理相关错误"""

    code = "stream_error"


# 工具函数：用于创建带上下文的异常
def create_error_with_context(
    error_class: Type[AppError],
    message: str,
    agent_name: Optional[str] = None,
    user_input: Optional[str] = None,
    **kwargs,
) -> AppError:
    """创建带有执行上下文的异常并保证 details 字段合并。

    参数:
    - error_class: 要创建的异常类型，必须是 `AppError` 的子类。
    - message: 异常消息。
    - agent_name: 可选，执行 agent 名称。
    - user_input: 可选，用户输入（会被截断以防过长）。
    - kwargs: 透传到异常构造器，支持 `details` 和 `original_error` 等参数。
    """
    # 创建错误实例
    details = dict(kwargs.get("details") or {})
    if agent_name:
        details["agent_name"] = agent_name
    if user_input:
        details["user_input"] = user_input[:100]

    # 构造最终 kwargs
    new_kwargs = dict(kwargs)
    new_kwargs["details"] = details

    return error_class(message, **new_kwargs)
