"""
Figma 设计稿转前端代码 — 多智能体工作流入口

支持两种运行模式：

  CLI 模式（默认）：
    python main.py <pc端链接> [手机端链接]
    python main.py <pc端链接> <pc端节点ID> <手机端链接> <手机端节点ID>

  Web 模式：
    python main.py --web [--port 8000]
    启动 Web 界面后在浏览器中操作
"""
import argparse
import asyncio
import json
import logging
import sys
import os
from contextlib import asynccontextmanager

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("autogen_core").setLevel(logging.DEBUG)


# ============================================================
# CLI 模式
# ============================================================

async def run_cli(args: list[str]) -> None:
    """CLI 模式入口。"""
    from utils.input_parser import parse_args
    from config.model_client import create_model_client
    from workflow.orchestrator import run_workflow
    from tools.mcp_manager import McpManager

    try:
        design_input = parse_args(args)
    except ValueError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Figma 设计稿 → 前端代码  多智能体工作流 (CLI)")
    print("=" * 60)
    print(f"  PC 端链接   : {design_input.pc_link}")
    if design_input.pc_node_id:
        print(f"  PC 端节点ID : {design_input.pc_node_id}")
    if design_input.mobile_link:
        print(f"  手机端链接  : {design_input.mobile_link}")
    if design_input.mobile_node_id:
        print(f"  手机端节点ID: {design_input.mobile_node_id}")
    print("=" * 60)

    model_client = create_model_client()
    async with McpManager() as mcp_mgr:
        try:
            await run_workflow(design_input, model_client, mcp_mgr)
        except KeyboardInterrupt:
            print("\n\n[中断] 用户取消了工作流。")
        finally:
            await model_client.close()


# ============================================================
# Web 模式
# ============================================================

def run_web(port: int = 8000) -> None:
    """Web 模式入口：启动 FastAPI 服务并在后台监听工作流启动请求。"""
    import uvicorn
    from web.app import app, bridge
    from config.model_client import create_model_client
    from workflow.orchestrator import run_workflow_web
    from utils.input_parser import DesignInput
    from tools.mcp_manager import McpManager

    # 确保 output 目录存在
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    # 应用级 MCP 管理器（整个服务期间复用）
    mcp_mgr = McpManager()

    async def workflow_listener():
        """后台任务：监听 Web UI 发来的启动信号并运行工作流。"""
        while True:
            # 等待启动信号（从 WebSocket 的 start 消息传入）
            raw = await bridge.input_queue.get()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(data, dict) or "pc_link" not in data:
                continue

            pc_link = data["pc_link"]
            mobile_link = data.get("mobile_link")

            design_input = DesignInput(
                pc_link=pc_link,
                mobile_link=mobile_link if mobile_link else None,
            )

            # 每次启动前重置状态
            bridge.reset_cancel()
            await bridge.emit("system", f"工作流启动: PC={pc_link}", msg_type="system")

            model_client = create_model_client(on_token=bridge.emit_chunk)
            try:
                # 将工作流包装为 task 以便取消
                task = asyncio.create_task(
                    run_workflow_web(design_input, model_client, mcp_mgr, bridge)
                )
                bridge._workflow_task = task
                await task
            except asyncio.CancelledError:
                await bridge.emit("system", "工作流已被停止。", msg_type="system")
            except Exception as e:
                await bridge.emit("system", f"工作流异常: {type(e).__name__}: {e}", msg_type="error")
            finally:
                await model_client.close()
                bridge.running = False
                bridge.waiting_for_input = False
                bridge._workflow_task = None
                # 通知前端工作流结束
                await bridge._emit_status()

    # 使用 FastAPI lifespan 替代弃用的 on_event
    @asynccontextmanager
    async def lifespan(app):
        # 启动时
        listener_task = asyncio.create_task(workflow_listener())
        print("[启动] 工作流监听器已启动")
        yield
        # 关闭时
        listener_task.cancel()
        await mcp_mgr.close()
        print("[关闭] MCP 连接已释放")

    app.router.lifespan_context = lifespan

    print()
    print("=" * 60)
    print("  Figma2Code 多智能体工作流 — Web 模式")
    print(f"  打开浏览器访问: http://localhost:{port}")
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Figma 设计稿 → 前端代码 多智能体工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  CLI: python main.py https://figma.com/design/xxx/... https://figma.com/design/yyy/...\n"
            "  Web: python main.py --web\n"
            "  Web: python main.py --web --port 9000\n"
        ),
    )
    parser.add_argument("--web", action="store_true", help="启动 Web 界面模式")
    parser.add_argument("--port", type=int, default=8000, help="Web 模式端口号 (默认 8000)")
    parser.add_argument("links", nargs="*", help="Figma 设计稿链接和节点 ID")

    args = parser.parse_args()

    if args.web:
        run_web(port=args.port)
    else:
        if not args.links:
            parser.print_help()
            sys.exit(1)
        asyncio.run(run_cli(args.links))


if __name__ == "__main__":
    main()
