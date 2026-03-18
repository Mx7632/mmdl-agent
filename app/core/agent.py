# LangGraph 工作流构建与编译入口
from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, END
from app.memory.state import DetectionState
from app.core.graph import load_data_node, anomaly_detect_node, summarize_node


def build_graph() -> Any:
    """构建并编译检测工作流图"""
    graph = StateGraph(DetectionState)
    graph.add_node("load_data", load_data_node)
    graph.add_node("anomaly_detect", anomaly_detect_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "anomaly_detect")
    graph.add_edge("anomaly_detect", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()
