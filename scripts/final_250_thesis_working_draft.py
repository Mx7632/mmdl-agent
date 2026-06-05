from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import RGBColor


TEXT = (
    "从完成过程看，系统的难点并不只在某一个算法，而在多种能力之间的衔接。"
    "视觉模型、PatchCore、RAG、状态记忆和前端展示各自解决一部分问题，只有把它们放进同一条任务链路中，"
    "用户才能从上传图片一路走到异常定位、原因解释、追问复核和报告生成。"
    "这也是本文系统设计相较于单独算法实验更值得总结的地方。"
)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    doc = Document(sys.argv[1])
    stop = None
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == "系统不足":
            stop = paragraph
            break
    if stop is None:
        raise RuntimeError("anchor not found")
    para = stop.insert_paragraph_before(TEXT)
    try:
        para.style = "论文正文"
    except Exception:
        pass
    for run in para.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    doc.save(sys.argv[1])
    print(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
