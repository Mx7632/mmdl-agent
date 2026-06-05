from __future__ import annotations

import sys
from docx import Document


TEXT = "这一点也使论文后续修改可以继续沿着代码证据、运行截图和实验记录逐步完善。"


doc = Document(sys.argv[1])
anchor = next(p for p in doc.paragraphs if p.text.strip() == "系统不足")
para = anchor.insert_paragraph_before(TEXT)
try:
    para.style = "论文正文"
except Exception:
    pass
doc.save(sys.argv[1])
print(sys.argv[1])
