"""
测试新的对话式 API 流程：
1. /v1/detect - 上传图片，只返回答案
2. /v1/chat - 多轮对话
3. /v1/generate_report - 生成完整报告
"""

import httpx
import json
from pathlib import Path

API_BASE = "http://127.0.0.1:8000"
IMAGE_PATH = r"C:/Users/simmer/Pictures/Camera Roll/anomaly.jpg"


def test_detect():
    """步骤1：首次检测，只返回答案"""
    print("=" * 50)
    print("步骤1: /v1/detect - 上传图片，只返回答案")
    print("=" * 50)

    img = Path(IMAGE_PATH)
    if not img.exists():
        print(f"图片不存在: {IMAGE_PATH}")
        return None

    files = {
        "task_id": (None, "chat-test-001"),
        "asset_id": (None, "asset-001"),
        "start_time": (None, "2026-04-18T11:00:00"),
        "end_time": (None, "2026-04-18T11:05:00"),
        "question": (None, "这张图片有什么异常？"),
        "image": (img.name, open(img, "rb"), "image/jpeg"),
    }

    with httpx.Client(timeout=120.0) as c:
        r = c.post(f"{API_BASE}/v1/detect", files=files)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(f"Response: {json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")

        if data.get("status") == "success":
            print("\n[OK] 检测成功！")
            print(f"回答: {data.get('answer', 'N/A')[:200]}...")
            print(f"异常数: {len(data.get('anomalies', []))}")
            print(f"has_report: {data.get('has_report')}")
            return "chat-test-001"
        else:
            print(f"\n[FAIL] 检测失败: {data}")
            return None


def test_chat(task_id: str):
    """步骤2：多轮对话"""
    print("\n" + "=" * 50)
    print("步骤2: /v1/chat - 多轮对话")
    print("=" * 50)

    questions = ["这个异常严重吗？", "可能是什么原因造成的？", "应该怎么处理？"]

    with httpx.Client(timeout=60.0) as c:
        for q in questions:
            print(f"\n[User] {q}")
            r = c.post(f"{API_BASE}/v1/chat", json={"task_id": task_id, "question": q})
            data = r.json()
            if data.get("status") == "success":
                print(f"[AI] {data.get('answer', 'N/A')[:200]}...")
            else:
                print(f"[Error] {data}")


def test_generate_report(task_id: str):
    """步骤3：生成完整报告"""
    print("\n" + "=" * 50)
    print("步骤3: /v1/generate_report - 生成完整报告")
    print("=" * 50)

    with httpx.Client(timeout=120.0) as c:
        r = c.post(f"{API_BASE}/v1/generate_report", json={"task_id": task_id})
        data = r.json()
        print(f"Status: {r.status_code}")

        if data.get("status") == "success":
            print("\n[OK] 报告生成成功！")
            print(f"has_report: {data.get('has_report')}")
            print(f"报告摘要: {data.get('summary', 'N/A')[:500]}...")
            print(f"\n完整报告长度: {len(data.get('summary', ''))} 字符")
        else:
            print(f"\n[FAIL] 报告生成失败: {data}")


if __name__ == "__main__":
    # 步骤1：检测
    task_id = test_detect()
    if not task_id:
        print("\n检测失败，停止测试")
        exit(1)

    # 步骤2：对话
    test_chat(task_id)

    # 步骤3：生成报告
    test_generate_report(task_id)

    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("=" * 50)
