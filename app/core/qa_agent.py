from __future__ import annotations

import json
import logging
import operator
from typing import Any, Annotated, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import SecretStr

from app.config.settings import settings
from app.prompts.qa_agent import PLANNER_PROMPT, QA_SYNTHESIZER_PROMPT
from app.rag.service import get_rag_service
from app.schemas.chat import ChatRequest, ChatStep
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool

logger = logging.getLogger(__name__)


class QAState(TypedDict):
    """Q&A Agent 状态模型"""
    request: ChatRequest
    steps: Annotated[List[ChatStep], operator.add]
    rag_context: str
    cv_result: Optional[Dict[str, Any]]
    final_answer: str
    metadata: Dict[str, Any]


async def planner_node(state: QAState) -> QAState:
    """规划者节点：制定任务执行计划"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.1,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.llm_base_url,
    )
    
    messages = PLANNER_PROMPT.format_messages(
        task_id=state["request"].task_id,
        category=state["request"].category or "通用工业件",
        question=state["request"].question,
    )
    
    response = await llm.ainvoke(messages)
    content = response.content
    try:
        # 解析 JSON 列表
        plan_data = json.loads(content)
        steps = [ChatStep(**step) for step in plan_data]
        logger.info(f"Agent 规划完成: {len(steps)} 个步骤")
        return {"steps": steps}
    except Exception as e:
        logger.error(f"解析规划结果失败: {e}, Raw: {content}")
        return {
            "steps": [
                ChatStep(step_name="基础分析", action="通用诊断流程", thought="解析规划失败，回退到基础流程")
            ]
        }


async def execute_rag_node(state: QAState) -> dict[str, Any]:
    """RAG 执行节点：检索相似案例和知识"""
    if not settings.rag_enabled:
        return {"rag_context": "RAG 未启用。"}
        
    try:
        service = get_rag_service()
        # 基于用户问题进行检索
        query_text = state["request"].question
        category = state["request"].category
        
        # 如果有图片，可以使用图片路径检索
        image_path = state["request"].parameters.get("image_path")
        
        rag_context = service.query_similar(
            query_text=query_text,
            category=category,
            top_k=settings.rag_top_k,
            image_path=image_path
        )
        
        # 更新步骤列表中的执行状态（由于 steps 是 Annotated[list, operator.add]，我们需要提供增量）
        # 但这里是对原有步骤的修改。在 LangGraph 中，如果 reducer 是 operator.add，
        # 我们很难修改原有的 list 元素，除非我们重新返回整个 list。
        # 更好的做法是在 final synthesizer 节点统一处理，或者这里只返回 rag_context。
        return {"rag_context": rag_context}
    except Exception as e:
        logger.error(f"RAG 执行失败: {e}")
        return {"rag_context": "RAG 检索过程中发生错误。"}


async def execute_cv_node(state: QAState) -> dict[str, Any]:
    """CV 执行节点：分析图像异常特征"""
    if not state["request"].image_base64:
        return {"cv_result": None}
        
    try:
        tool = ImageAnomalyDetectionTool()
        from app.schemas.detection import DetectionTask
        
        # 将请求中的图片数据注入参数，供工具使用
        parameters = dict(state["request"].parameters or {})
        if state["request"].image_base64:
            parameters["image_base64"] = state["request"].image_base64
        if state["request"].image_mime:
            parameters["image_mime"] = state["request"].image_mime
            
        task = DetectionTask(
            task_id=state["request"].task_id,
            asset_id=parameters.get("asset_id", "QA-ASSET"),
            start_time="2026-04-06T00:00:00Z",
            end_time="2026-04-06T00:00:00Z",
            question=state["request"].question,
            parameters=parameters
        )
        
        response = await tool.run(task)
        if response.success and response.result:
            return {"cv_result": response.result.model_dump()}
        else:
            return {"cv_result": {"error": response.error}}
    except Exception as e:
        logger.error(f"CV 执行失败: {e}")
        return {"cv_result": {"error": str(e)}}


async def synthesizer_node(state: QAState) -> dict[str, Any]:
    """综合报告节点：整合所有信息给出最终回答"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.llm_base_url,
    )
    
    # 构造执行过程的摘要供 LLM 参考
    steps_results = []
    # 如果有 cv_result，在此补充进摘要
    if state["cv_result"]:
        steps_results.append({"step": "视觉检测", "result": "已完成视觉扫描"})
    if state["rag_context"]:
        steps_results.append({"step": "知识检索", "result": "已获取相关参考"})
        
    messages = QA_SYNTHESIZER_PROMPT.format_messages(
        task_id=state["request"].task_id,
        question=state["request"].question,
        steps_results=json.dumps(steps_results, ensure_ascii=False),
        rag_context=state["rag_context"],
    )
    
    response = await llm.ainvoke(messages)
    return {"final_answer": response.content}


def build_qa_graph() -> Any:
    """构建自动规划 Q&A 工作流图"""
    graph = StateGraph(QAState)
    
    graph.add_node("planner", planner_node)
    graph.add_node("rag_exec", execute_rag_node)
    graph.add_node("cv_exec", execute_cv_node)
    graph.add_node("synthesizer", synthesizer_node)
    
    graph.set_entry_point("planner")
    
    # 目前简化为顺序执行核心能力（由 Planner 决定具体内容展示，但在图中保证能力全覆盖）
    graph.add_edge("planner", "rag_exec")
    graph.add_edge("rag_exec", "cv_exec")
    graph.add_edge("cv_exec", "synthesizer")
    graph.add_edge("synthesizer", END)
    
    return graph.compile()
