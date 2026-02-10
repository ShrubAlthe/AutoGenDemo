"""
文件读写与图片保存工具函数

供智能体使用，所有路径相对于 output/ 目录。
包含：文件读写、图片下载保存、base64 图片保存。
"""
import base64
import os
import urllib.request

from config import settings


# ============================================================
# 文本文件读写
# ============================================================


def write_file(file_path: str, content: str) -> str:
    """将内容写入指定文件（相对于输出目录）。

    Args:
        file_path: 文件路径，相对于 output/ 目录（如 'index.html'）
        content: 文件内容

    Returns:
        操作结果文本
    """
    full_path = os.path.join(settings.OUTPUT_DIR, file_path)
    parent = os.path.dirname(full_path)
    os.makedirs(parent if parent else settings.OUTPUT_DIR, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"文件已写入: {full_path}"


def read_file(file_path: str) -> str:
    """读取指定文件的内容（相对于输出目录）。

    Args:
        file_path: 文件路径，相对于 output/ 目录（如 'index.html'）

    Returns:
        文件内容或错误提示
    """
    full_path = os.path.join(settings.OUTPUT_DIR, file_path)
    if not os.path.exists(full_path):
        return f"文件不存在: {full_path}"
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def list_output_files() -> str:
    """列出输出目录中的所有文件。

    Returns:
        文件列表文本
    """
    if not os.path.exists(settings.OUTPUT_DIR):
        return "输出目录为空"
    files = []
    for root, _dirs, filenames in os.walk(settings.OUTPUT_DIR):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), settings.OUTPUT_DIR)
            files.append(rel_path)
    return "\n".join(files) if files else "输出目录为空"


# ============================================================
# 图片保存工具
# ============================================================


def save_base64_image(filename: str, base64_data: str) -> str:
    """将 base64 编码的图片数据保存到输出目录。

    Args:
        filename: 保存的文件名（如 'figma-screenshot.png'），保存在 output/ 目录下
        base64_data: base64 编码的图片数据（可以包含 data:image/png;base64, 前缀）

    Returns:
        保存后的完整文件路径
    """
    # 去掉可能的 data URI 前缀
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]

    image_bytes = base64.b64decode(base64_data)
    full_path = os.path.join(settings.OUTPUT_DIR, filename)
    os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else settings.OUTPUT_DIR, exist_ok=True)

    with open(full_path, "wb") as f:
        f.write(image_bytes)
    return f"图片已保存: {full_path}"


def download_image(url: str, filename: str) -> str:
    """从 URL 下载图片并保存到输出目录。

    Args:
        url: 图片的下载 URL
        filename: 保存的文件名（如 'design-screenshot.png'），保存在 output/ 目录下

    Returns:
        保存后的完整文件路径
    """
    full_path = os.path.join(settings.OUTPUT_DIR, filename)
    os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else settings.OUTPUT_DIR, exist_ok=True)

    try:
        urllib.request.urlretrieve(url, full_path)
        return f"图片已下载保存: {full_path}"
    except Exception as e:
        return f"图片下载失败: {type(e).__name__}: {e}"
