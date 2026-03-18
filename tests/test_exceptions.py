# 异常体系行为测试。
"""
异常系统测试
测试 app/exceptions/base.py 中的异常类与创建工具
"""

from app.exceptions.base import (
    AppError,
    ModelError,
    ToolError,
    ToolNotFoundError,
    ToolExecutionError,
    ContextError,
    TokenLimitError,
    MaxTurnsError,
    ResponseParseError,
    ConfigurationError,
    StreamError,
    create_error_with_context,
)


class TestAppError:
    """测试基础异常类 AppError"""

    def test_app_error_creation_with_message(self):
        """创建基础异常，仅包含消息"""
        error = AppError("test error message")
        assert error.message == "test error message"
        assert error.details == {}
        assert error.original_error is None
        assert error.status_code == 500
        assert error.code == "app_error"

    def test_app_error_with_details(self):
        """创建异常并附加详情"""
        error = AppError(
            "test error",
            details={"key1": "value1", "key2": 123}
        )
        assert error.details == {"key1": "value1", "key2": 123}

    def test_app_error_with_original_error(self):
        """异常链传递"""
        original = ValueError("original error message")
        error = AppError("wrapper error", original_error=original)
        assert error.original_error is original
        assert "原因: original error message" in str(error)

    def test_app_error_str_representation(self):
        """测试异常字符串表示"""
        error = AppError("test message")
        assert str(error) == "test message"


class TestModelError:
    """测试模型错误 ModelError"""

    def test_model_error_creation(self):
        """创建模型错误"""
        error = ModelError(
            "Model API timeout",
            model_name="gpt-4",
            status_code=504
        )
        assert error.message == "Model API timeout"
        assert error.details["model_name"] == "gpt-4"
        assert error.details["status_code"] == 504

    def test_model_error_without_optional_params(self):
        """创建模型错误（不包含可选参数）"""
        error = ModelError("Model error")
        assert error.details["model_name"] is None
        assert error.details["status_code"] is None

    def test_model_error_with_original_error(self):
        """模型错误链传递"""
        original = TimeoutError("request timeout")
        error = ModelError(
            "Model call failed",
            model_name="claude-3",
            original_error=original
        )
        assert error.original_error is original


class TestToolError:
    """测试工具错误系列"""

    def test_tool_error_creation(self):
        """创建通用工具错误"""
        error = ToolError(
            "Tool execution failed",
            tool_name="anomaly_detector",
            arguments={"threshold": 0.5, "data": [1, 2, 3]}
        )
        assert error.details["tool_name"] == "anomaly_detector"
        assert error.details["arguments"]["threshold"] == 0.5

    def test_tool_not_found_error(self):
        """工具未找到错误"""
        error = ToolNotFoundError("missing_tool")
        assert "找不到工具: missing_tool" in error.message
        assert error.details["tool_name"] == "missing_tool"

    def test_tool_execution_error(self):
        """工具执行失败"""
        original = RuntimeError("execution failed in subprocess")
        error = ToolExecutionError(
            "my_tool",
            {"arg1": "val1", "arg2": "val2"},
            original
        )
        assert error.message == "工具 'my_tool' 执行失败"
        assert error.details["tool_name"] == "my_tool"
        assert error.original_error is original


class TestContextError:
    """测试上下文错误"""

    def test_context_error_creation(self):
        """创建上下文错误"""
        error = ContextError("Context overflow")
        assert error.message == "Context overflow"
        assert error.code == "context_error"


class TestTokenLimitError:
    """测试 Token 限制错误"""

    def test_token_limit_error_default_message(self):
        """Token 超限（默认消息）"""
        error = TokenLimitError(current_tokens=10000, max_tokens=4096)
        assert error.details["current_tokens"] == 10000
        assert error.details["max_tokens"] == 4096
        assert "Token 数量超过限制" in error.message
        assert "10000" in error.message

    def test_token_limit_error_custom_message(self):
        """Token 超限（自定义消息）"""
        error = TokenLimitError(
            current_tokens=5000,
            max_tokens=4096,
            message="Custom token limit message"
        )
        assert error.message == "Custom token limit message"


class TestMaxTurnsError:
    """测试最大轮次错误"""

    def test_max_turns_error(self):
        """达到最大轮次"""
        error = MaxTurnsError(max_turns=10)
        assert error.details["max_turns"] == 10
        assert "10" in error.message
        assert "无限循环" in error.message
        assert error.code == "max_turns"


class TestResponseParseError:
    """测试响应解析错误"""

    def test_response_parse_error(self):
        """响应解析失败"""
        raw_response = "invalid json {{"
        error = ResponseParseError(
            "Failed to parse response",
            raw_response=raw_response
        )
        assert error.message == "Failed to parse response"
        # raw_response 被截断至 500 字符
        assert "invalid json {{" in error.details["raw_response"]

    def test_response_parse_error_long_response(self):
        """响应过长时截断"""
        long_response = "x" * 1000
        error = ResponseParseError("Parse error", raw_response=long_response)
        # 应该被截断至 500 字符
        assert len(error.details["raw_response"]) == 500


class TestConfigurationError:
    """测试配置错误"""

    def test_configuration_error_with_key(self):
        """配置错误（含配置键）"""
        error = ConfigurationError(
            "Invalid configuration value",
            config_key="MODEL_NAME"
        )
        assert error.message == "Invalid configuration value"
        assert error.details["config_key"] == "MODEL_NAME"

    def test_configuration_error_without_key(self):
        """配置错误（不含配置键）"""
        error = ConfigurationError("Missing required setting")
        assert error.details == {}


class TestStreamError:
    """测试流式处理错误"""

    def test_stream_error_creation(self):
        """创建流式处理错误"""
        error = StreamError("Stream connection lost")
        assert error.message == "Stream connection lost"
        assert error.code == "stream_error"


class TestCreateErrorWithContext:
    """测试上下文错误创建工具函数"""

    def test_create_model_error_with_context(self):
        """创建带上文模型错误"""
        error = create_error_with_context(
            ModelError,
            "Model call failed",
            agent_name="anomaly_detector",
            user_input="process this data",
            model_name="gpt-4"
        )
        assert error.details["agent_name"] == "anomaly_detector"
        assert error.details["user_input"] == "process this data"
        assert error.details["model_name"] == "gpt-4"

    def test_create_error_with_context_user_input_truncation(self):
        """用户输入被截断至 100 字符"""
        long_input = "x" * 200
        error = create_error_with_context(
            ToolError,
            "Tool error",
            user_input=long_input,
            tool_name="test_tool"
        )
        assert len(error.details["user_input"]) == 100

    def test_create_error_with_original_error(self):
        """上下文函数支持原始错误链"""
        original = ValueError("original error")
        error = create_error_with_context(
            AppError,
            "Wrapper error",
            agent_name="test_agent",
            original_error=original
        )
        assert error.original_error is original
        assert error.details["agent_name"] == "test_agent"

    def test_create_error_without_optional_context(self):
        """不提供可选上下文"""
        error = create_error_with_context(
            ConfigurationError,
            "Config missing",
            config_key="API_KEY"
        )
        assert "agent_name" not in error.details
        assert "user_input" not in error.details
        assert error.details["config_key"] == "API_KEY"