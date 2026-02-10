"""测试 FunctionTool 到 模型调用 的完整链路"""
import sys
import os
import asyncio
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.file_tools import write_file
from autogen_core.tools import FunctionTool
from autogen_core import CancellationToken


async def main():
    # === FunctionTool 包装测试 ===
    print("=== FunctionTool 包装测试 ===")
    ft = FunctionTool(write_file, description="写入文件")
    print(f"schema: {ft.schema}")

    try:
        r = await ft.run_json(
            {"file_path": "diag_ft.txt", "content": "FunctionTool test"},
            cancellation_token=CancellationToken(),
        )
        print(f"FunctionTool 结果: {r}")
    except Exception:
        traceback.print_exc()

    # === 模型实际工具调用 ===
    print()
    print("=== 模型实际工具调用 ===")
    from config.model_client import create_model_client
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage

    client = create_model_client()
    agent = AssistantAgent(
        name="test_agent",
        model_client=client,
        tools=[write_file],
        reflect_on_tool_use=True,
        system_message="你是一个测试助手。当用户要求写文件时，必须调用 write_file 工具。",
    )
    print(f"Agent 创建成功: {agent.name}")

    try:
        response = await agent.on_messages(
            [TextMessage(
                content="请调用 write_file 工具写入文件。file_path 为 'model_test.txt'，content 为 '模型工具调用测试成功'。",
                source="user",
            )],
            cancellation_token=CancellationToken(),
        )
        print(f"响应类型: {type(response).__name__}")
        if response.chat_message:
            content = response.chat_message.content
            if isinstance(content, str):
                print(f"响应内容: {content[:300]}")
            else:
                print(f"响应内容: {content}")
        if response.inner_messages:
            for msg in response.inner_messages:
                print(f"  内部消息: {type(msg).__name__} - {str(msg)[:200]}")
    except Exception:
        traceback.print_exc()

    # === 检查生成的文件 ===
    print()
    print("=== 文件检查 ===")
    from config import settings

    for fname in ["diag_ft.txt", "model_test.txt"]:
        fpath = os.path.join(settings.OUTPUT_DIR, fname)
        exists = os.path.exists(fpath)
        print(f"{fname}: {'存在 ✓' if exists else '不存在 ✗'}")
        if exists:
            with open(fpath, "r", encoding="utf-8") as f:
                print(f"  内容: {f.read()}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
