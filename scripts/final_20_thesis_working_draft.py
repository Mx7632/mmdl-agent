from __future__ import annotations
import sys
from docx import Document

doc = Document(sys.argv[1])
anchor = next(p for p in doc.paragraphs if p.text.strip() == "系统不足")
para = anchor.insert_paragraph_before("这也为后续论文完善留下了明确方向。")
try:
    para.style = "论文正文"
except Exception:
    pass
doc.save(sys.argv[1])
print(sys.argv[1])
