"""
探索 AutoGen GroupChat 的流式输出能力
"""
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from config.model_client import create_model_client

async def main():
    model_client = create_model_client()
    
    agent = AssistantAgent(
        name="test_agent",
        model_client=model_client,
        system_message="你是一个测试助手。请输出一段 50 字左右的文字。",
    )

    print("=== 开始 run_stream 测试 ===")
    # 尝试捕获所有类型的事件
    async for msg in agent.run_stream(task="请讲一个简短的笑话。"):
        print(f"Type: {type(msg).__name__}")
        if hasattr(msg, "content"):
            content = getattr(msg, "content")
            print(f"Content: {str(content)[:20]}...")
        if hasattr(msg, "delta"): # 猜测 TokenChunk 可能有 delta
            print(f"Delta: {msg.delta}")
            
    await model_client.close()

if __name__ == "__main__":
    asyncio.run(main())
