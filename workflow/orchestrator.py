"""
主工作流编排器

负责：
  1. 初始化所有工具和智能体
  2. 创建 SelectorGroupChat 团队
  3. 使用 run_stream 实时输出每条智能体消息
  4. 处理外层用户反馈循环（ok → 结束 / 纠正点 → 写入规则 → 重跑）

支持两种模式：
  - CLI 模式：直接在终端打印消息、通过 input() 获取反馈
  - Web 模式：通过 WorkflowBridge 与 Web UI 通信（支持取消）
"""
import asyncio
import os
from typing import Optional

from autogen_agentchat.base import TaskResult

from agents.figma_analyzer import create_figma_analyzer
from agents.info_gatherer import create_info_gatherer
from agents.code_writer import create_code_writer
from agents.code_reviewer import create_code_reviewer
from agents.result_reviewer import create_result_reviewer
from config import settings
from rules.rules_manager import RulesManager
from tools.browser_tools import get_browser_tools
from tools.figma_tools import get_figma_tools
from tools.knowledge_tools import search_knowledge, add_knowledge, get_knowledge_summary
from tools.file_tools import write_file, read_file, list_output_files, save_base64_image, download_image
from utils.image_compare import compare_screenshots_tool
from utils.input_parser import DesignInput
from workflow.group_chat import create_group_chat


# ============================================================
# 任务提示词构建
# ============================================================

def build_task_prompt(design_input: DesignInput, correction: Optional[str] = None) -> str:
    """根据设计稿输入参数构建任务提示词。"""
    parts: list[str] = [
        "请根据以下 Figma 设计稿生成前端页面代码。\n",
        f"**PC 端设计稿链接**: {design_input.pc_link}",
    ]

    pc_node_id = design_input.get_pc_node_id()
    if pc_node_id:
        parts.append(f"**PC 端节点 ID**: {pc_node_id}")

    if design_input.mobile_link:
        parts.append(f"**手机端设计稿链接**: {design_input.mobile_link}")
        mobile_node_id = design_input.get_mobile_node_id()
        if mobile_node_id:
            parts.append(f"**手机端节点 ID**: {mobile_node_id}")

    parts.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "工作流程",
        "━━━━━━━━━━━━━━━━━━━━",
        "1. **figma_analyzer**: 调用 Figma MCP 分析设计稿的页面结构和布局",
        "2. **code_writer**: 根据分析结果生成 HTML / CSS 代码，**必须调用 write_file** 保存文件到 output/",
        "3. **code_reviewer**: 读取 output/ 中的代码文件，审核是否符合编码规范",
        "4. **result_reviewer**: 获取设计稿图片和浏览器截图进行相似度对比",
        "5. 所有审核通过后结束任务",
    ])

    if correction:
        parts.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "⚠️ 用户上轮纠正点（已加入规则）",
            "━━━━━━━━━━━━━━━━━━━━",
            correction,
            "",
            "请特别注意以上纠正点进行针对性优化。",
        ])

    return "\n".join(parts)


# ============================================================
# 消息格式化
# ============================================================

def _format_message_content(msg) -> str:
    """将各类消息内容转换为文本。"""
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if hasattr(item, "name"):
                args_str = getattr(item, "arguments", "")
                # 截断过长的参数
                if len(str(args_str)) > 200:
                    args_str = str(args_str)[:200] + "..."
                parts.append(f"[调用工具] {item.name}({args_str})")
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


# ============================================================
# CLI 模式运行
# ============================================================

async def run_workflow(design_input: DesignInput, model_client) -> None:
    """CLI 模式：在终端运行工作流。"""
    await _run_workflow_internal(design_input, model_client, bridge=None)


# ============================================================
# Web 模式运行
# ============================================================

async def run_workflow_web(design_input: DesignInput, model_client, bridge) -> None:
    """Web 模式：通过 bridge 与 Web UI 通信。"""
    bridge.running = True
    bridge.reset_cancel()
    try:
        await _run_workflow_internal(design_input, model_client, bridge=bridge)
    except asyncio.CancelledError:
        await bridge.emit("system", "工作流已被用户停止。", msg_type="system")
    except Exception as e:
        await bridge.emit("system", f"工作流异常: {type(e).__name__}: {e}", msg_type="error")
    finally:
        bridge.running = False
        bridge.waiting_for_input = False
        # 推送最终状态
        await bridge.emit("system", "工作流已结束。", msg_type="workflow_complete")


# ============================================================
# 核心工作流（统一逻辑）
# ============================================================

async def _run_workflow_internal(design_input: DesignInput, model_client, bridge=None) -> None:
    """内部统一工作流逻辑。"""
    is_web = bridge is not None
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    # 辅助函数
    async def log(source: str, content: str, msg_type: str = "system"):
        if is_web:
            await bridge.emit(source, content, msg_type=msg_type)
        else:
            print(f"[{source}] {content}")

    async def get_input(prompt: str) -> str:
        if is_web:
            return await bridge.request_input(prompt)
        else:
            return input(f"\n{prompt}").strip()

    def check_cancel():
        """检查是否被取消。"""
        if is_web and bridge.is_cancelled:
            raise asyncio.CancelledError("用户取消了工作流")

    # ------------------------------------------------------------------
    # 初始化规则管理器
    # ------------------------------------------------------------------
    rules_manager = RulesManager(
        global_rules_path=settings.GLOBAL_RULES_PATH,
        coding_rules_path=settings.CODING_RULES_PATH,
    )

    # ------------------------------------------------------------------
    # 初始化 MCP 工具
    # ------------------------------------------------------------------
    await log("system", "正在启动 Figma MCP 服务...")
    try:
        figma_tools = await get_figma_tools()
        await log("system", f"Figma MCP 就绪，加载了 {len(figma_tools)} 个工具")
    except ValueError as e:
        await log("system", f"错误: {e}", msg_type="error")
        raise
    except Exception as e:
        await log("system", f"Figma MCP 启动失败: {type(e).__name__}: {e}", msg_type="error")
        raise

    check_cancel()

    await log("system", "正在启动 Browser MCP 服务...")
    try:
        browser_tools = await get_browser_tools()
        await log("system", f"Browser MCP 就绪，加载了 {len(browser_tools)} 个工具")
    except Exception as e:
        await log("system", f"Browser MCP 启动失败: {type(e).__name__}: {e}", msg_type="error")
        raise

    check_cancel()

    # ------------------------------------------------------------------
    # 本地工具
    # ------------------------------------------------------------------
    knowledge_tools = [search_knowledge, add_knowledge, get_knowledge_summary]
    file_tools = [write_file, read_file, list_output_files, save_base64_image, download_image]
    image_tools = [compare_screenshots_tool]

    # ------------------------------------------------------------------
    # 构建任务提示
    # ------------------------------------------------------------------
    task_prompt = build_task_prompt(design_input)

    # ==================================================================
    # 外层循环：用户反馈
    # ==================================================================
    iteration = 0
    while True:
        iteration += 1
        check_cancel()
        rules_manager.reload()

        # 创建智能体
        figma_analyzer = create_figma_analyzer(
            model_client=model_client,
            figma_tools=figma_tools,
            knowledge_tools=knowledge_tools,
            rules_manager=rules_manager,
        )
        if is_web:
            _loop = asyncio.get_running_loop()

            def _web_input_func(prompt: str) -> str:
                future = asyncio.run_coroutine_threadsafe(bridge.request_input(prompt), _loop)
                return future.result(timeout=600)

            info_gatherer = create_info_gatherer(input_func=_web_input_func)
        else:
            info_gatherer = create_info_gatherer()

        code_writer = create_code_writer(
            model_client=model_client,
            knowledge_tools=knowledge_tools,
            file_tools=file_tools,
            rules_manager=rules_manager,
        )
        code_reviewer = create_code_reviewer(
            model_client=model_client,
            file_tools=file_tools,
            rules_manager=rules_manager,
        )
        result_reviewer = create_result_reviewer(
            model_client=model_client,
            figma_tools=figma_tools,
            browser_tools=browser_tools,
            image_compare_tools=image_tools,
            file_tools=file_tools,
            rules_manager=rules_manager,
        )

        # 创建群聊
        team = create_group_chat(
            participants=[
                figma_analyzer,
                info_gatherer,
                code_writer,
                code_reviewer,
                result_reviewer,
            ],
            model_client=model_client,
            max_messages=settings.MAX_TOTAL_MESSAGES,
        )

        # 运行群聊 (流式)
        await log("system", f"═══ 第 {iteration} 轮工作流开始 ═══")

        async for msg in team.run_stream(task=task_prompt):
            check_cancel()

            if isinstance(msg, TaskResult):
                await log("system", f"═══ 第 {iteration} 轮执行完成（共 {len(msg.messages)} 条消息）═══")
                break

            source = getattr(msg, "source", "unknown")
            content = _format_message_content(msg)
            msg_type_name = type(msg).__name__

            if "ToolCall" in msg_type_name:
                display_type = "tool"
            else:
                display_type = "agent"

            if content:
                await log(source, content, msg_type=display_type)

        check_cancel()

        # 请求用户反馈
        await log("system", "审核流程已完成。生成的文件位于 output/ 目录。")
        user_input = await get_input("请输入 'ok' 结束任务，或输入需要纠正的内容: ")

        if user_input.lower() == "ok":
            await log("system", "任务已完成！文件保存在 output/ 目录中。")
            break
        else:
            rules_manager.add_user_correction(user_input)
            await log("system", f"已将纠正点写入规则: \"{user_input}\"")
            await log("system", "正在根据纠正点重新执行...")
            task_prompt = build_task_prompt(design_input, correction=user_input)
