from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


IMAGE_REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是工业设备图像异常检测专家，需要基于图像检测到的异常信息，结合用户的问题，"
                "生成一份可读的初始报告给运维工程师。请使用专业但易懂的中文，结构清晰，包含：\n"
                "1. 结论摘要（是否异常、严重程度）\n"
                "2. 发现的异常（逐条说明，必要时引用 bbox/score）\n"
                "3. 可能原因（给出 2-3 个候选）\n"
                "4. 建议的排查与处置步骤（可执行、按优先级）\n"
                "5. 针对用户问题的回答\n"
            ),
        ),
        (
            "user",
            (
                "任务ID: {task_id}\n"
                "资产ID: {asset_id}\n"
                "时间范围: {start_time} 至 {end_time}\n"
                "用户问题: {question}\n\n"
                "图像检测到的异常(JSON):\n"
                "{anomalies}\n"
            ),
        ),
    ]
)

