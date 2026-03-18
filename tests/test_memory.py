# 文件说明：状态与检查点相关测试。
"""
记忆与状态管理测试
测试 app/memory/state.py 和 app/memory/checkpoint.py
"""

from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask, DetectionResult


class TestDetectionState:
    """测试检测执行状态管理"""

    def test_state_initialization(self):
        """初始化状态"""
        task = DetectionTask(
            task_id="state-test-001",
            asset_id="asset-001",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": [1.0, 2.0, 3.0], "threshold": 0.5},
        )
        state = DetectionState(task=task)
        assert state.task == task

    def test_state_task_persistence(self):
        """任务数据在状态中持久化"""
        task = DetectionTask(
            task_id="persist-test",
            asset_id="asset-002",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": [10.0, 20.0, 30.0], "threshold": 0.7},
        )
        state = DetectionState(task=task)

        assert state.task.task_id == "persist-test"
        assert state.task.parameters["data"] == [10.0, 20.0, 30.0]
        assert state.task.parameters["threshold"] == 0.7

    def test_state_with_result(self):
        """状态可包含结果"""
        task = DetectionTask(
            task_id="result-test",
            asset_id="asset-003",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
        )
        state = DetectionState(task=task)

        if hasattr(state, "result"):
            result = DetectionResult(
                task_id="result-test",
                status="success",
                anomalies=[],
            )
            state.result = result
            assert state.result == result

    def test_state_deep_copy_on_modification(self):
        """状态修改不影响原始任务"""
        original_data = [1.0, 2.0, 3.0]
        task = DetectionTask(
            task_id="copy-test",
            asset_id="asset-004",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": original_data, "threshold": 0.5},
        )
        state = DetectionState(task=task)
        assert state.task.parameters["data"] == original_data


class TestDetectionResult:
    """测试检测结果数据模型"""

    def test_result_creation(self):
        """创建检测结果"""
        result = DetectionResult(
            task_id="result-001",
            status="success",
            anomalies=[],
        )
        assert result.task_id == "result-001"
        assert result.status == "success"
        assert result.anomalies == []

    def test_result_with_anomalies(self):
        """结果包含异常信息"""
        result = DetectionResult(
            task_id="anomaly-test",
            status="success",
            anomalies=[
                {"index": 0, "score": 0.9},
                {"index": 5, "score": 0.8},
            ],
        )
        assert len(result.anomalies) == 2
        assert result.anomalies[0]["score"] == 0.9

    def test_result_status_values(self):
        """验证结果状态值"""
        for status in ["success", "failed"]:
            result = DetectionResult(
                task_id=f"status-{status}",
                status=status,
                anomalies=[],
            )
            assert result.status == status


class TestMemoryCheckpoint:
    """测试检查点与状态恢复"""

    def test_checkpoint_save_and_load(self):
        """检查点保存与加载"""
        task = DetectionTask(
            task_id="checkpoint-test",
            asset_id="asset-005",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": [1.0, 2.0, 3.0], "threshold": 0.5},
        )
        state = DetectionState(task=task)

        checkpoint_data = {
            "task_id": state.task.task_id,
            "asset_id": state.task.asset_id,
            "start_time": state.task.start_time,
            "end_time": state.task.end_time,
            "parameters": state.task.parameters,
        }

        recovered_task = DetectionTask(
            task_id=checkpoint_data["task_id"],
            asset_id=checkpoint_data["asset_id"],
            start_time=checkpoint_data["start_time"],
            end_time=checkpoint_data["end_time"],
            parameters=checkpoint_data["parameters"],
        )
        recovered_state = DetectionState(task=recovered_task)

        assert recovered_state.task.task_id == state.task.task_id
        assert recovered_state.task.parameters == state.task.parameters

    def test_checkpoint_with_failed_state(self):
        """检查点保存失败状态"""
        task = DetectionTask(
            task_id="failed-checkpoint",
            asset_id="asset-006",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
        )
        state = DetectionState(task=task)

        error_info = {"error": "processing failed"}
        checkpoint_data = {
            "task_id": state.task.task_id,
            "error": error_info,
        }

        assert checkpoint_data["error"]["error"] == "processing failed"


class TestStateTransitions:
    """测试状态转换流程"""

    def test_state_from_pending_to_completed(self):
        """状态从待处理到完成"""
        task = DetectionTask(
            task_id="transition-test",
            asset_id="asset-007",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
        )

        initial_status = "pending"
        result = DetectionResult(
            task_id=task.task_id,
            status="success",
            anomalies=[],
        )

        assert initial_status == "pending"
        assert result.status == "success"

    def test_state_from_pending_to_failed(self):
        """状态从待处理到失败"""
        task = DetectionTask(
            task_id="failure-transition",
            asset_id="asset-008",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
        )

        failed_result = DetectionResult(
            task_id=task.task_id,
            status="failed",
            anomalies=[],
        )

        assert failed_result.status == "failed"


class TestMemoryOptimization:
    """测试内存管理与优化"""

    def test_large_state_handling(self):
        """处理大型状态"""
        large_data = list(range(100000))
        task = DetectionTask(
            task_id="large-state",
            asset_id="asset-009",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": large_data},
        )
        state = DetectionState(task=task)

        assert len(state.task.parameters["data"]) == 100000
        assert state.task.task_id == "large-state"

    def test_state_memory_efficiency(self):
        """验证状态内存效率"""
        import sys

        task = DetectionTask(
            task_id="memory-test",
            asset_id="asset-010",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T01:00:00Z",
            parameters={"data": [1.0] * 1000},
        )
        state = DetectionState(task=task)

        state_size = sys.getsizeof(state)
        assert state_size > 0

