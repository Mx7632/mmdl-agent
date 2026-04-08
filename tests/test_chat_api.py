import httpx
import json
import base64
from pathlib import Path

def test_chat_endpoint():
    url = "http://localhost:8000/v1/chat"
    
    # 模拟图片（如果存在的话，否则只测试文字）
    image_path = Path("data/uploads/task-1774353057688-rkoxwuiyo.png")
    
    files = {}
    if image_path.exists():
        files["image"] = (image_path.name, image_path.read_bytes(), "image/png")
    
    data = {
        "task_id": "test-chat-001",
        "question": "这张图片里的零件有什么异常？请结合知识库给出分析建议。",
        "category": "metal_nut",
        "parameters": json.dumps({"asset_id": "NUT-X1"})
    }
    
    print(f"正在请求 {url}...")
    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, data=data, files=files)
            
            if response.status_code == 200:
                result = response.json()
                print("\n=== 执行步骤 ===")
                for step in result.get("steps", []):
                    print(f"[{step['step_name']}] {step['thought']}")
                
                print("\n=== 最终回答 ===")
                print(result.get("answer"))
            else:
                print(f"请求失败: {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    test_chat_endpoint()
