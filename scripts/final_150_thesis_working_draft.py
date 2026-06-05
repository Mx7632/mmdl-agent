from __future__ import annotations

import sys

from docx import Document
from docx.shared import RGBColor


TEXT = (
    "因此，本文最终形成的是一个以真实项目为基础的可运行原型。"
    "它把算法、知识、流程和界面放在同一个系统中讨论，也为后续继续补实验、补截图和做性能评估留下了清晰入口。"
)


def main() -> int:
    doc = Document(sys.argv[1])
    anchor = next(p for p in doc.paragraphs if p.text.strip() == "系统不足")
    para = anchor.insert_paragraph_before(TEXT)
    try:
        para.style = "论文正文"
    except Exception:
        pass
    for run in para.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    doc.save(sys.argv[1])
    print(sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
