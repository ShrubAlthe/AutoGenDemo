"""
工具调用诊断脚本

用于排查 write_file / save_base64_image / download_image 工具调用失败的问题。
运行方式: python test_tools.py
"""
import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

# ============================================================
# 测试 1: 基础路径和权限检查
# ============================================================
def test_paths():
    print("=" * 60)
    print("测试 1: 路径与权限检查")
    print("=" * 60)
    print(f"  PROJECT_ROOT : {settings.PROJECT_ROOT}")
    print(f"  OUTPUT_DIR   : {settings.OUTPUT_DIR}")
    print(f"  OUTPUT_DIR 存在: {os.path.exists(settings.OUTPUT_DIR)}")

    # 尝试创建 output 目录
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    print(f"  OUTPUT_DIR 创建/确认: OK")

    # 尝试写文件
    test_file = os.path.join(settings.OUTPUT_DIR, "_test_write.txt")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_file)
        print(f"  文件写入权限: OK")
    except Exception as e:
        print(f"  文件写入权限: FAILED - {e}")

    print()


# ============================================================
# 测试 2: 直接调用 write_file 函数
# ============================================================
def test_write_file_direct():
    print("=" * 60)
    print("测试 2: 直接调用 write_file")
    print("=" * 60)
    from tools.file_tools import write_file

    try:
        result = write_file("_test_direct.html", "<html><body>Hello</body></html>")
        print(f"  结果: {result}")
        # 验证文件是否存在
        path = os.path.join(settings.OUTPUT_DIR, "_test_direct.html")
        print(f"  文件存在: {os.path.exists(path)}")
        if os.path.exists(path):
            os.remove(path)
            print(f"  清理: OK")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {e}")
    print()


# ============================================================
# 测试 3: 直接调用 save_base64_image
# ============================================================
def test_save_base64_image_direct():
    print("=" * 60)
    print("测试 3: 直接调用 save_base64_image")
    print("=" * 60)
    from tools.file_tools import save_base64_image
    import base64

    # 创建一个 1x1 红色 PNG
    # 最小有效 PNG: 1x1 像素红色
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    b64 = base64.b64encode(png_data).decode()

    try:
        result = save_base64_image("_test_image.png", b64)
        print(f"  结果: {result}")
        path = os.path.join(settings.OUTPUT_DIR, "_test_image.png")
        print(f"  文件存在: {os.path.exists(path)}")
        if os.path.exists(path):
            os.remove(path)
            print(f"  清理: OK")
    except Exception as e:
        print(f"  失败: {type(e).__name__}: {e}")

    # 测试带 data URI 前缀
    try:
        result = save_base64_image("_test_image2.png", f"data:image/png;base64,{b64}")
        print(f"  带前缀结果: {result}")
        path = os.path.join(settings.OUTPUT_DIR, "_test_image2.png")
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"  带前缀失败: {type(e).__name__}: {e}")
    print()


# ============================================================
# 测试 4: 检查 FunctionTool 包装
# ============================================================
def test_function_tool_wrapping():
    print("=" * 60)
    print("测试 4: AutoGen FunctionTool 包装检查")
    print("=" * 60)
    from tools.file_tools import write_file, save_base64_image, download_image

    try:
        from autogen_core.tools import FunctionTool
        print(f"  FunctionTool 导入: OK")
    except ImportError as e:
        print(f"  FunctionTool 导入失败: {e}")
        print()
        return

    for func in [write_file, save_base64_image, download_image]:
        name = func.__name__
        try:
            tool = FunctionTool(func, description=func.__doc__ or "")
            schema = tool.schema
            print(f"  [{name}] 包装: OK")
            print(f"    schema name: {schema.get('name', 'N/A') if isinstance(schema, dict) else schema}")
            # 尝试获取参数信息
            if hasattr(tool, 'args_type'):
                print(f"    args_type: {tool.args_type}")
        except Exception as e:
            print(f"  [{name}] 包装失败: {type(e).__name__}: {e}")
    print()


# ============================================================
# 测试 5: 检查 FallbackChatCompletionClient 协议兼容性
# ============================================================
def test_model_client_protocol():
    print("=" * 60)
    print("测试 5: FallbackChatCompletionClient 协议兼容性")
    print("=" * 60)
    from config.model_client import FallbackChatCompletionClient
    from autogen_core.models import ChatCompletionClient

    print(f"  FallbackChatCompletionClient 父类: {FallbackChatCompletionClient.__bases__}")
    print(f"  是否继承 ChatCompletionClient: {issubclass(FallbackChatCompletionClient, ChatCompletionClient)}")

    # 检查 ChatCompletionClient 是 Protocol 还是 ABC
    print(f"  ChatCompletionClient 类型: {type(ChatCompletionClient)}")
    print(f"  ChatCompletionClient 是否 Protocol: {hasattr(ChatCompletionClient, '_is_protocol')}")

    # 检查 ChatCompletionClient 要求的方法
    required_methods = []
    for name, method in inspect.getmembers(ChatCompletionClient):
        if not name.startswith('_') and callable(method):
            required_methods.append(name)
    print(f"  ChatCompletionClient 方法: {required_methods}")

    # 检查 FallbackChatCompletionClient 实现的方法
    implemented = []
    for name, method in inspect.getmembers(FallbackChatCompletionClient):
        if not name.startswith('_') and (callable(method) or isinstance(method, property)):
            implemented.append(name)
    print(f"  FallbackClient 方法: {implemented}")

    # 找出缺失的方法
    missing = set(required_methods) - set(implemented)
    if missing:
        print(f"  ⚠ 缺失方法: {missing}")
    else:
        print(f"  方法覆盖: OK")
    print()


# ============================================================
# 测试 6: 尝试用 FunctionTool 实际执行工具调用
# ============================================================
async def test_function_tool_execution():
    print("=" * 60)
    print("测试 6: FunctionTool 实际执行")
    print("=" * 60)
    from tools.file_tools import write_file

    try:
        from autogen_core.tools import FunctionTool
        from autogen_core import CancellationToken
    except ImportError as e:
        print(f"  导入失败: {e}")
        print()
        return

    tool = FunctionTool(write_file, description=func.__doc__ or "no doc")

    try:
        # 模拟 AutoGen 的工具调用方式
        ct = CancellationToken()
        result = await tool.run_json(
            {"file_path": "_test_tool_exec.html", "content": "<h1>Test</h1>"},
            ct
        )
        print(f"  执行结果: {result}")
        path = os.path.join(settings.OUTPUT_DIR, "_test_tool_exec.html")
        if os.path.exists(path):
            os.remove(path)
            print(f"  清理: OK")
    except Exception as e:
        print(f"  执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    print()


# ============================================================
# 测试 7: 检查 AssistantAgent 工具注册
# ============================================================
def test_agent_tool_registration():
    print("=" * 60)
    print("测试 7: AssistantAgent 工具注册检查")
    print("=" * 60)
    from tools.file_tools import write_file, read_file
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from config import settings

    cfg = settings.MODEL_FALLBACK_CHAIN[0]
    client = OpenAIChatCompletionClient(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=settings.MODEL_TEMPERATURE,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": False,
            "family": cfg.get("family", "unknown"),
        },
    )

    try:
        agent = AssistantAgent(
            name="test_agent",
            model_client=client,
            tools=[write_file, read_file],
        )
        print(f"  Agent 创建: OK")
        print(f"  Agent name: {agent.name}")
        # 检查工具是否正确注册
        if hasattr(agent, '_tools'):
            print(f"  注册工具数: {len(agent._tools)}")
            for t in agent._tools:
                print(f"    - {t.name if hasattr(t, 'name') else t}")
        elif hasattr(agent, 'tools'):
            print(f"  注册工具数: {len(agent.tools)}")
    except Exception as e:
        print(f"  Agent 创建失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    print()


# ============================================================
# 测试 8: 实际调用模型进行工具调用 (可选)
# ============================================================
async def test_model_tool_call():
    print("=" * 60)
    print("测试 8: 实际模型工具调用（需要网络）")
    print("=" * 60)
    from tools.file_tools import write_file
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from config import settings

    cfg = settings.MODEL_FALLBACK_CHAIN[0]
    client = OpenAIChatCompletionClient(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=0.1,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": False,
            "family": cfg.get("family", "unknown"),
        },
    )

    agent = AssistantAgent(
        name="test_writer",
        model_client=client,
        tools=[write_file],
        system_message="你是一位助手。当用户要求写入文件时，请使用 write_file 工具。",
        reflect_on_tool_use=True,
    )

    try:
        response = await agent.on_messages(
            [TextMessage(
                content='请调用 write_file 工具，将以下内容写入 "_test_model.txt"：\n\nHello World 测试',
                source="user",
            )],
            cancellation_token=None,
        )
        print(f"  模型响应类型: {type(response).__name__}")
        if hasattr(response, 'chat_message'):
            print(f"  消息内容: {str(response.chat_message.content)[:200]}")
        if hasattr(response, 'inner_messages') and response.inner_messages:
            print(f"  内部消息数: {len(response.inner_messages)}")
            for msg in response.inner_messages:
                msg_type = type(msg).__name__
                print(f"    - {msg_type}: {str(getattr(msg, 'content', ''))[:100]}")

        path = os.path.join(settings.OUTPUT_DIR, "_test_model.txt")
        if os.path.exists(path):
            print(f"  文件写入成功: {path}")
            with open(path, "r") as f:
                print(f"  文件内容: {f.read()}")
            os.remove(path)
        else:
            print(f"  ⚠ 文件未被创建 - 工具调用可能失败!")
    except Exception as e:
        print(f"  测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()
    print()


# ============================================================
# 主函数
# ============================================================
def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       AutoGenDemo 工具调用诊断                         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    test_paths()
    test_write_file_direct()
    test_save_base64_image_direct()
    test_function_tool_wrapping()
    test_model_client_protocol()
    test_agent_tool_registration()

    print("=" * 60)
    print("基础测试完成。是否要进行实际模型调用测试？(y/n)")
    print("=" * 60)
    answer = input("> ").strip().lower()
    if answer == "y":
        asyncio.run(test_function_tool_execution())
        asyncio.run(test_model_tool_call())
    else:
        print("跳过模型调用测试。")

    print()
    print("诊断完成！")


if __name__ == "__main__":
    main()
