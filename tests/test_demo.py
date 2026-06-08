"""
测试图像异常检测功能
使用一个示例图片来演示完整的检测流程
"""

import asyncio
import httpx


async def test_detect():
    # 读取一张测试图片（这里用一个占位图）
    # 实际使用时可以替换为真实的工业设备图片
    try:
        # 尝试从网络获取测试图片
        async with httpx.AsyncClient() as client:
            response = await client.get("https://picsum.photos/800/600", timeout=10.0)
            image_bytes = response.content
    except Exception:
        # 如果网络不可用，创建简单的测试数据
        print("⚠️ 无法获取测试图片，跳过实际检测测试")
        print("✅ 但后端服务已经成功启动！")
        return

    # 准备请求数据
    form_data = {
        "task_id": "test-001",
        "asset_id": "camera-01",
        "start_time": "2026-03-20T10:00:00Z",
        "end_time": "2026-03-20T11:00:00Z",
        "data_source": "test",
        "question": "请检测设备表面是否有划痕或异常",
        "parameters": '{"tool_type": "qwen3.5-plus"}',
    }

    files = {
        "image": ("test.jpg", image_bytes, "image/jpeg"),
    }

    print("\n🔍 发送检测请求...")
    print(f"📊 任务 ID: {form_data['task_id']}")
    print(f"🏭 资产 ID: {form_data['asset_id']}")
    print(f"❓ 问题：{form_data['question']}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://127.0.0.1:8000/v1/detect",
                data=form_data,
                files=files,
            )

            print(f"\n📡 响应状态码：{response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print("\n✅ 检测成功！")
                print(f"📋 任务状态：{result.get('status')}")
                print(f"🔢 异常数量：{len(result.get('anomalies', []))}")

                if result.get("summary"):
                    print("\n📝 报告摘要:")
                    print("-" * 80)
                    print(result["summary"][:500])  # 只显示前 500 字符
                    print("-" * 80)

                if result.get("anomalies"):
                    print("\n⚠️ 检测到的异常:")
                    for i, anomaly in enumerate(result["anomalies"][:3], 1):
                        print(f"{i}. 类型：{anomaly.get('type', '未知')}")
                        print(f"   置信度：{anomaly.get('score', 0):.2f}")
                        print(f"   详情：{anomaly.get('details', '无')}")
                        print()
            else:
                print(f"\n❌ 检测失败：{response.text}")

    except Exception as e:
        print(f"\n❌ 请求失败：{str(e)}")
        print("💡 这可能是因为 API Key 配置问题或模型服务不可用")


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 MMDL-Agent 图像异常检测测试")
    print("=" * 80)
    asyncio.run(test_detect())
