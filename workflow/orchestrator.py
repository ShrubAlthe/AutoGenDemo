"""
主工作流编排器 — 分阶段执行

4 个阶段：
  Stage 1: Figma 分析 — figma_analyzer (+ info_gatherer 提问)
  Stage 2: 代码编写 — code_writer 根据分析报告生成代码
  Stage 3: 代码审核循环 — code_writer ↔ code_reviewer (最多 N 轮)
  Stage 4: 结果审核循环 — code_writer ↔ result_reviewer (最多 N 轮)

支持两种模式：
  - CLI 模式：直接在终端打印消息、通过 input() 获取反馈
  - Web 模式：通过 WorkflowBridge 与 Web UI 通信（支持取消）
"""
import asyncio
import os
from typing import Optional

from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat

from agents.figma_analyzer import create_figma_analyzer
from agents.info_gatherer import create_info_gatherer
from agents.code_writer import create_code_writer
from agents.code_reviewer import create_code_reviewer
from agents.result_reviewer import create_result_reviewer
from agents.group_admin import create_selector_prompt, custom_selector_func
from config import settings
from rules.rules_manager import RulesManager
from tools.knowledge_tools import search_knowledge, add_knowledge, get_knowledge_summary
from tools.file_tools import write_file, read_file, list_output_files, save_base64_image, download_image
from tools.mcp_manager import McpManager
from utils.image_compare import compare_screenshots_tool
from utils.input_parser import DesignInput


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

async def run_workflow(design_input: DesignInput, model_client, mcp_mgr: McpManager) -> None:
    """CLI 模式：在终端运行工作流。"""
    await _run_workflow_internal(design_input, model_client, mcp_mgr=mcp_mgr, bridge=None)


# ============================================================
# Web 模式运行
# ============================================================

async def run_workflow_web(design_input: DesignInput, model_client, mcp_mgr: McpManager, bridge) -> None:
    """Web 模式：通过 bridge 与 Web UI 通信。"""
    bridge.running = True
    bridge.reset_cancel()
    try:
        await _run_workflow_internal(design_input, model_client, mcp_mgr=mcp_mgr, bridge=bridge)
    except asyncio.CancelledError:
        await bridge.emit("system", "工作流已被用户停止。", msg_type="system")
    except Exception as e:
        await bridge.emit("system", f"工作流异常: {type(e).__name__}: {e}", msg_type="error")
    finally:
        bridge.running = False
        bridge.waiting_for_input = False
        await bridge.emit("system", "工作流已结束。", msg_type="workflow_complete")


# ============================================================
# 通用：运行一个阶段并收集消息
# ============================================================

async def _run_stage(team, task: str, stage_name: str, log_fn, check_cancel_fn) -> str:
    """运行一个阶段（team.run_stream），收集所有消息内容，返回最后一条有效消息。

    Args:
        team: AutoGen team (SelectorGroupChat / RoundRobinGroupChat)
        task: 阶段的任务提示
        stage_name: 阶段名称（用于日志）
        log_fn: 日志函数 async (source, content, msg_type)
        check_cancel_fn: 取消检查函数

    Returns:
        最后一条有效消息的内容文本
    """
    last_content = ""
    msg_count = 0

    async for msg in team.run_stream(task=task):
        check_cancel_fn()

        if isinstance(msg, TaskResult):
            await log_fn("system", f"[{stage_name}] 阶段完成（共 {msg_count} 条消息）")
            break

        source = getattr(msg, "source", "unknown")
        content = _format_message_content(msg)
        msg_type_name = type(msg).__name__

        if "ToolCall" in msg_type_name:
            display_type = "tool"
        else:
            display_type = "agent"

        if content:
            await log_fn(source, content, msg_type=display_type)
            last_content = content
            msg_count += 1

    return last_content


# ============================================================
# 核心工作流（4 阶段分步执行）
# ============================================================

async def _run_workflow_internal(design_input: DesignInput, model_client, mcp_mgr: McpManager, bridge=None) -> None:
    """内部统一工作流逻辑 — 分阶段执行。"""
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
    # 通过 McpManager 获取 MCP 工具（复用持久连接）
    # ------------------------------------------------------------------
    await log("system", "正在连接 Figma MCP 服务...")
    try:
        figma_tools = await mcp_mgr.get_figma_tools()
        await log("system", f"Figma MCP 就绪，加载了 {len(figma_tools)} 个工具")
    except ValueError as e:
        await log("system", f"错误: {e}", msg_type="error")
        raise
    except Exception as e:
        await log("system", f"Figma MCP 连接失败: {type(e).__name__}: {e}", msg_type="error")
        raise

    check_cancel()

    await log("system", "正在连接 Browser MCP 服务...")
    try:
        browser_tools = await mcp_mgr.get_browser_tools()
        await log("system", f"Browser MCP 就绪，加载了 {len(browser_tools)} 个工具")
    except Exception as e:
        await log("system", f"Browser MCP 连接失败: {type(e).__name__}: {e}", msg_type="error")
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

        # 创建智能体（每轮重建以获取最新规则）
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

        await log("system", f"═══ 第 {iteration} 轮工作流开始 ═══")

        # ==============================================================
        # Stage 1: Figma 分析
        # ==============================================================
        await log("system", "📐 Stage 1/4: 分析 Figma 设计稿...", msg_type="stage")

        # 用 SelectorGroupChat 处理 figma_analyzer + info_gatherer 的交互
        analysis_termination = (
            TextMentionTermination("## 编码建议")      # 分析报告完成标记
            | TextMentionTermination("分析报告")        # 备用标记
            | MaxMessageTermination(15)                 # 防止无限循环
        )
        roles_info = "\n".join([
            f"- **{p.name}**: {p.description}"
            for p in [figma_analyzer, info_gatherer]
        ])
        analysis_team = SelectorGroupChat(
            participants=[figma_analyzer, info_gatherer],
            model_client=model_client,
            selector_prompt=create_selector_prompt(roles_info),
            termination_condition=analysis_termination,
            allow_repeated_speaker=True,
        )
        analysis_result = await _run_stage(
            analysis_team, task_prompt, "Figma 分析", log, check_cancel
        )

        check_cancel()

        # ==============================================================
        # Stage 2: 代码编写
        # ==============================================================
        await log("system", "💻 Stage 2/4: 编写前端代码...", msg_type="stage")

        code_task = (
            f"根据以下 Figma 分析报告生成 HTML/CSS 代码，"
            f"**必须调用 write_file 保存文件**。\n\n{analysis_result}"
        )
        code_termination = (
            TextMentionTermination("文件已写入")
            | MaxMessageTermination(10)
        )
        code_team = RoundRobinGroupChat(
            participants=[code_writer],
            termination_condition=code_termination,
        )
        await _run_stage(code_team, code_task, "代码编写", log, check_cancel)

        check_cancel()

        # ==============================================================
        # Stage 3: 代码审核循环
        # ==============================================================
        await log("system", "🔍 Stage 3/4: 代码审核...", msg_type="stage")

        max_review_rounds = settings.MAX_REFLECTION_ROUNDS
        review_termination = (
            TextMentionTermination("REVIEW_APPROVED")
            | MaxMessageTermination(max_review_rounds * 2)
        )
        review_team = RoundRobinGroupChat(
            participants=[code_reviewer, code_writer],
            termination_condition=review_termination,
        )
        review_task = "请审核 output/ 目录中的 index.html 和 styles.css，检查是否符合编码规范。"
        await _run_stage(review_team, review_task, "代码审核", log, check_cancel)

        check_cancel()

        # ==============================================================
        # Stage 4: 结果审核循环
        # ==============================================================
        await log("system", "🎨 Stage 4/4: 页面还原度审核...", msg_type="stage")

        result_termination = (
            TextMentionTermination("RESULT_APPROVED")
            | MaxMessageTermination(max_review_rounds * 2)
        )
        result_team = RoundRobinGroupChat(
            participants=[result_reviewer, code_writer],
            termination_condition=result_termination,
        )
        result_task = (
            "请对比 Figma 设计稿与浏览器渲染效果的还原度。"
            "使用 get_images 获取设计稿图片，用 browser 工具截图，然后对比。"
        )
        await _run_stage(result_team, result_task, "结果审核", log, check_cancel)

        check_cancel()

        # ------------------------------------------------------------------
        # 请求用户反馈
        # ------------------------------------------------------------------
        await log("system", "═══ 所有审核流程已完成。文件位于 output/ 目录 ═══")
        user_input = await get_input("请输入 'ok' 结束任务，或输入需要纠正的内容: ")

        if user_input.lower() == "ok":
            await log("system", "✅ 任务已完成！文件保存在 output/ 目录中。")
            break
        else:
            rules_manager.add_user_correction(user_input)
            await log("system", f"已将纠正点写入规则: \"{user_input}\"")
            await log("system", "正在根据纠正点重新执行...")
            task_prompt = build_task_prompt(design_input, correction=user_input)
