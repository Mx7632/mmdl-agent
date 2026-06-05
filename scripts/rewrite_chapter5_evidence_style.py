from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import RGBColor


BODY_STYLE = "论文正文"
H1_STYLE = "heading 1"
H2_STYLE = "heading 2"


CHAPTER_5_BLOCKS: list[tuple[str, str]] = [
    ("h1", "系统测试与实验分析"),
    (
        "p",
        "前几章已经说明了系统的需求、总体架构和关键模块实现。本章不再停留在“应该怎样测试”的层面，而是围绕当前项目已经形成的运行链路，对系统进行功能验证和案例分析。测试重点不是证明系统已经达到工业生产环境的全部要求，而是验证本文实现的多 Agent 调度、视觉检测、PatchCore 热力图、RAG 知识检索、few-shot 上下文注入、追问续接和前端展示等功能是否能够在同一套系统中协同运行。",
    ),
    (
        "p",
        "由于本系统仍属于本科毕业设计阶段的工程原型，本文采用“接口测试 + 页面操作 + 典型样本实验 + 日志观察”的方式进行验证。对于尚未完成大规模自动评测的部分，本文不编造准确率、召回率和吞吐量，而是在相应位置保留真实数据插入点。这样既能说明系统已经具备可执行链路，也能避免把少量样例误写成完整性能结论。",
    ),
    (
        "p",
        "[插入图5-1：系统测试链路示意图。建议画出“前端上传图像 -> FastAPI接口 -> LangGraph流程 -> VisionAgent/PatchCore/RAG -> 前端结果展示/报告生成”的测试闭环。]",
    ),
    ("h2", "测试环境与数据来源"),
    (
        "p",
        "本节首先说明测试使用的软硬件环境和数据来源。系统开发与前端调试主要在本地 Windows 环境完成，后端通过 FastAPI 启动，前端页面通过浏览器访问后端接口；PatchCore 训练和 MVTec 数据集实验可以在 AutoDL 服务器上完成。由于本项目同时涉及前端页面、后端接口、向量数据库、本地热力图文件和外部视觉模型，测试环境需要记录得足够具体，否则后续很难复现实验结果。",
    ),
    (
        "p",
        "本地环境主要用于验证前端交互、流式输出、RAG 建库按钮、热力图展示和多 Agent 时间线。服务器环境主要用于 PatchCore 的类别训练和推理测试。训练完成后，PatchCore 会在模型目录下生成 memory_bank.pt 和 metadata.json；后端推理时需要通过 APP_PATCHCORE_MODEL_ROOT 指向该模型目录。此前服务器测试中曾出现 CUDA 与 PyTorch 架构不兼容的问题，因此本文在记录环境时不仅写操作系统，还需要写 Python、PyTorch、CUDA 或 CPU 运行方式。",
    ),
    (
        "p",
        "数据集方面，本文以 MVTec AD 为主要测试数据来源。MVTec AD 的目录结构比较清晰，类别目录下通常包含 train/good、test/good、test/<defect_type> 和 ground_truth 等子目录，适合用于 PatchCore 正常样本训练和异常样本推理验证。RAG 知识库也可以从该数据集扫描样本，提取类别、缺陷类型、正常/异常标签和图像路径等元数据。",
    ),
    (
        "p",
        "[插入表5-1：测试环境记录表。需要填写：本地系统版本、Python版本、后端启动命令、前端访问地址、AutoDL系统版本、GPU/CPU信息、PyTorch版本、MVTec数据集路径、PatchCore模型路径、RAG向量库路径。]",
    ),
    (
        "p",
        "[插入图5-2：MVTec数据集目录截图。建议展示 bottle/train/good、bottle/test/good、bottle/test/broken_small 等目录，证明后续实验样本来源。]",
    ),
    ("h2", "接口与功能测试"),
    (
        "p",
        "接口测试用于验证后端主链路是否能够被前端和脚本正常调用。本文重点测试 /health、/v1/stream、/v1/chat、/v1/generate_report、/v1/rag/build/start、/v1/rag/build/status/{task_id}、/v1/rag/query 和 /v1/patchcore/categories 等接口。其中 /health 用于确认服务启动，/v1/stream 用于执行流式检测，/v1/chat 用于首轮检测后的追问，RAG 接口用于知识库构建和相似案例查询，PatchCore 类别接口用于检查哪些类别已经训练。",
    ),
    (
        "p",
        "测试时首先启动后端服务，并在浏览器中打开前端页面。当前端点击开始检测按钮后，浏览器向 /v1/stream 发送 multipart/form-data 请求；若上传了图像，后端会将图像编码为 base64，并写入 DetectionTask.parameters。随后 LangGraph 接管任务，Supervisor 生成执行计划，VisionAgent 或其他专家节点根据计划执行。前端通过 SSE 持续接收事件，并把运行摘要、最终回答和多 Agent 时间线展示出来。",
    ),
    (
        "p",
        "功能测试不只检查接口是否返回成功，还检查返回内容是否符合系统设计。例如，选择 PatchCore 后端时，metadata 中应包含 selected_backend、category、threshold、heatmap_path、overlay_path 等字段；RAG 查询成功时，应返回 results 和 prompt_context；追问接口调用后，系统应基于同一 task_id 读取上一轮上下文，而不是把追问当成完全新的任务。",
    ),
    (
        "p",
        "[插入表5-2：核心接口功能测试表。建议列：测试编号、接口、输入条件、预期结果、实际结果、是否通过。至少包含 /health、/v1/stream、/v1/chat、/v1/rag/build/start、/v1/rag/query、/v1/patchcore/categories。]",
    ),
    (
        "p",
        "[插入图5-3：前端主检测页面截图。需要包含上传图片、后端选择、开始检测按钮、检测结果区域。]",
    ),
    (
        "p",
        "[插入图5-4：浏览器开发者工具或后端日志截图。建议展示 /v1/stream 返回 200、trace_id、SSE事件或接口响应字段。]",
    ),
    ("h2", "PatchCore异常定位实验"),
    (
        "p",
        "PatchCore 实验用于验证本地热力图工具是否能够完成固定类别的训练和推理。本文以 MVTec AD 中已准备好的类别为例进行测试。训练阶段只使用 train/good 中的正常样本，脚本会提取图像 patch 特征并生成 memory bank；推理阶段输入 test/good 或 test/<defect_type> 下的图像，系统计算输入图像局部特征与正常 memory bank 之间的距离，并将距离结果转换为异常热力图。",
    ),
    (
        "p",
        "从工程运行角度看，PatchCore 需要验证三个问题。第一，类别检查是否正确：未训练类别不应被强行推理，而应提示用户先训练或切换后端。第二，模型文件是否正确加载：memory_bank.pt 和 metadata.json 必须存在于类别模型目录下。第三，推理结果是否可展示：系统应输出 heatmap、mask、overlay、bbox、location 和异常描述，前端应能通过静态路径加载这些文件。",
    ),
    (
        "p",
        "在前期实验中，阈值对结果影响明显。阈值偏低时，good 样本可能也被识别出异常区域；阈值提高后，正常样本误报会减少，但异常样本也需要重新观察是否仍能定位到缺陷。因此，本文不把单张图片的结果写成最终性能结论，而把 PatchCore 部分写成类别训练、可视化推理和阈值敏感性分析。这样的表达更符合当前项目证据，也更符合工业异常检测的实际调试过程。",
    ),
    (
        "p",
        "[插入代码块5-1：PatchCore训练命令。建议放 AutoDL 上实际执行过的命令，包括 --category、--dataset-root、--model-root、--image-size、--device、--backbone、--max-memory-bank、--pretrained-backbone。]",
    ),
    (
        "p",
        "[插入表5-3：PatchCore训练结果表。需要填写：category、image_size、backbone、pretrained_backbone、device、memory_bank_size、feature_dim、recommended_threshold、模型保存路径。]",
    ),
    (
        "p",
        "[插入代码块5-2：PatchCore推理命令与JSON返回摘要。建议分别放 good 样本和 broken_small 样本的推理命令，保留 threshold、anomalies数量、heatmap_path、overlay_path、mask_path。]",
    ),
    (
        "p",
        "[插入图5-5：PatchCore异常样本overlay图。建议使用 bottle/test/broken_small/000.png 的 overlay 输出，图注写“PatchCore异常样本热力图叠加结果”。]",
    ),
    (
        "p",
        "[插入图5-6：PatchCore正常样本对比图。建议使用 bottle/test/good/000.png 在最终选定阈值下的 overlay 或无强异常结果截图，用于说明误报控制。]",
    ),
    (
        "p",
        "[插入表5-4：PatchCore阈值对比表。建议列：样本类型、图像路径、threshold、异常区域数量、最高分、人工观察结论。]",
    ),
    ("h2", "RAG检索与Few-shot实验"),
    (
        "p",
        "RAG 实验用于验证系统是否能够从数据集中构建知识库，并在检测或追问过程中返回相似案例。建库阶段由前端或接口调用 /v1/rag/build/start，后端启动异步任务扫描数据集、生成样本描述并写入 Chroma 向量库。前端通过 /v1/rag/build/status/{task_id} 查询任务进度。当状态变为 success 后，说明样本已进入向量库，可以进行相似案例查询。",
    ),
    (
        "p",
        "查询阶段主要验证两类能力。第一类是普通 RAG 查询：用户输入产品类别、缺陷描述或问题，系统返回若干相似案例及 prompt_context。第二类是 few-shot 注入：系统从 RAG 返回结果中筛选正常样本和异常样本，由 FewShotPromptBuilder 构造紧凑上下文，再注入 VisionAgent 或 KnowledgeAgent。这样，检测和解释过程就不只依赖通用模型自身知识，而是能够参考项目数据集中的案例。",
    ),
    (
        "p",
        "本文对 RAG 的评价采用案例分析方式。原因是当前知识库规模和样本质量仍与数据集描述有关，尚未建立大规模专家评分集。因此，本节重点观察检索结果是否包含正确类别、是否区分 normal/anomaly、metadata 是否记录 category、anomaly_type、is_anomaly 等字段，以及 few_shot_examples 是否进入最终 metadata。若这些信息存在，说明“RAG相似案例 -> few-shot样本筛选 -> prompt构造 -> Agent注入”链路已经打通。",
    ),
    (
        "p",
        "[插入图5-7：RAG建库页面或接口状态截图。需要显示 task_id、phase、percent、processed、total 或 success 状态。]",
    ),
    (
        "p",
        "[插入表5-5：RAG建库结果表。需要填写：dataset_root、include_normal、indexed_rows、vector_count、正常样本数量、异常样本数量。]",
    ),
    (
        "p",
        "[插入图5-8：RAG查询结果截图。建议展示 query_text、category、返回的相似案例列表和 prompt_context 摘要。]",
    ),
    (
        "p",
        "[插入表5-6：Few-shot筛选结果表。建议列：query、返回样本id、category、anomaly_type、is_anomaly、是否被选为normal参考、是否被选为anomaly参考。]",
    ),
    (
        "p",
        "[插入代码块5-3：一次检测结果中 metadata 的 few_shot_examples / few_shot_context 片段。用于证明 few-shot 结果已经注入 Agent。]",
    ),
    ("h2", "多Agent流程与追问测试"),
    (
        "p",
        "多 Agent 流程测试用于验证 Supervisor 是否能够根据用户意图选择合适专家节点。首轮上传图像时，系统通常会规划 VisionAgent 执行视觉检测；用户追问“原因是什么”“有没有相似案例”“是否使用RAG”时，系统应调用或复用 KnowledgeAgent；用户请求报告时，系统应进入 ReportAgent。这个测试重点不只是最终回答是否合理，还要观察中间执行过程是否符合设计。",
    ),
    (
        "p",
        "本系统前端已经提供多 Agent 执行时间线，因此可以直接观察任务节点状态。时间线中应能看到 Supervisor 计划、专家 Agent 执行、结果合并、自我反思、最终回答等阶段。若某个节点失败，错误也应反映在时间线或日志中。对于长任务排障来说，这种可观测性比单纯最终答案更重要，因为它能告诉用户系统到底卡在图像分析、RAG检索、报告生成还是状态恢复环节。",
    ),
    (
        "p",
        "追问测试重点验证上下文是否真正被恢复。首轮检测完成后，用户继续询问“为什么会这样”时，系统应读取上一轮图像、异常区域、检测后端和 RAG 上下文，而不是重新开始一个空任务。若追问只返回上一轮 summary，说明聊天链路没有重新规划；若追问能够结合上一轮异常结果并补充原因、风险或相似案例，说明 task_id、checkpoint、conversation_history 和 Supervisor 规划共同发挥了作用。",
    ),
    (
        "p",
        "[插入图5-9：多Agent执行时间线截图。需要能看到 Supervisor、VisionAgent、KnowledgeAgent、AnswerNode 或 ReportAgent 的执行状态。]",
    ),
    (
        "p",
        "[插入表5-7：多Agent调度测试表。建议列：用户输入、期望触发Agent、实际触发Agent、关键metadata、结论。测试场景包括首轮检测、追问原因、询问RAG、重新分析、生成报告。]",
    ),
    (
        "p",
        "[插入图5-10：追问链路截图。建议展示首轮检测结果和后续追问回答，证明回答不是简单重复旧结果。]",
    ),
    (
        "p",
        "[插入代码块5-4：后端日志片段。建议包含同一 task_id 下首轮检测和追问的 trace_id、stream_detection、run_chat 或 stream_continue_detection 相关日志。]",
    ),
    ("h2", "本章小结"),
    (
        "p",
        "本章围绕系统实际运行链路展开测试与实验分析。接口测试说明后端检测、RAG、PatchCore类别检查和报告接口可以被调用；PatchCore实验说明本地固定类别热力图工具能够完成训练、推理和可视化输出；RAG与few-shot实验说明知识库能够提供相似案例，并将正常/异常参考样本注入后续分析；多 Agent流程与追问测试说明系统能够根据用户意图进行节点调度，并通过状态记忆支持多轮任务。",
    ),
    (
        "p",
        "从测试结果看，本文系统已经形成从前端操作到后端编排、从视觉检测到知识检索、从热力图展示到报告生成的完整原型链路。但也应看到，当前实验仍以典型样本和功能验证为主，尚未完成全类别、大规模、自动化的量化评测。后续工作需要继续补充更多类别的 PatchCore 阈值标定结果、RAG 检索质量评分、多 Agent 失败场景统计以及真实运行截图。",
    ),
    (
        "p",
        "[插入表5-8：本章测试结论汇总表。建议列：测试模块、是否通过、主要证据、仍需改进的问题。]",
    ),
]


def paragraph_text(paragraph) -> str:
    return paragraph.text.strip()


def style_name(paragraph) -> str:
    try:
        return paragraph.style.name.lower()
    except Exception:
        return ""


def find_h1(doc: Document, text: str):
    for paragraph in doc.paragraphs:
        if paragraph_text(paragraph) == text and style_name(paragraph) == H1_STYLE:
            return paragraph
    raise RuntimeError(f"heading not found: {text}")


def remove_between(start_para, stop_para) -> None:
    body = start_para._element.getparent()
    children = list(body)
    start = children.index(start_para._element)
    stop = children.index(stop_para._element)
    for element in children[start:stop]:
        body.remove(element)


def add_before(ref_para, kind: str, text: str) -> None:
    style = H1_STYLE if kind == "h1" else H2_STYLE if kind == "h2" else BODY_STYLE
    para = ref_para.insert_paragraph_before(text)
    try:
        para.style = style
    except Exception:
        pass
    for run in para.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: rewrite_chapter5_evidence_style.py <docx_path>")
        return 2
    path = Path(sys.argv[1])
    doc = Document(str(path))
    start = find_h1(doc, "系统测试与实验分析")
    stop = find_h1(doc, "总结与展望")
    remove_between(start, stop)
    for kind, text in CHAPTER_5_BLOCKS:
        add_before(stop, kind, text)
    doc.save(str(path))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
