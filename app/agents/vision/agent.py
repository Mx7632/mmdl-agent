from __future__ import annotations

from app.orchestration import AgentEnvelope
from app.schemas.detection import DetectionTask
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool


class VisionAgent:
    name = "vision"

    def __init__(self, tool: ImageAnomalyDetectionTool | None = None) -> None:
        self.tool = tool or ImageAnomalyDetectionTool()

    async def run(self, task: DetectionTask) -> AgentEnvelope:
        response = await self.tool.run(task)
        result = response.result
        anomalies = result.anomalies if result else []
        metadata = result.metadata if result else {}
        summary = result.summary if result else None
        status = "success" if response.success else "failed"

        if not summary:
            if status != "success":
                summary = response.error or "视觉分析执行失败，未得到可靠的检测结果。"
            elif anomalies:
                summary = f"Detected {len(anomalies)} visual anomaly item(s)."
            else:
                summary = "No obvious visual anomaly was detected."

        return AgentEnvelope(
            agent_name=self.name,
            status=status,
            summary=summary,
            payload={
                "anomalies": anomalies,
                "metadata": metadata,
                "answer": result.answer if result else None,
                "error": response.error,
                "heatmap_path": metadata.get("heatmap_path"),
                "overlay_path": metadata.get("overlay_path"),
                "mask_path": metadata.get("mask_path"),
                "category": metadata.get("category"),
            },
            confidence=float(metadata.get("confidence", 0.0) or 0.0),
        )
