"""
图片相似度对比工具

使用 SSIM（结构相似性指数）算法对比 Figma 设计稿截图与浏览器渲染截图。
"""
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim


def compare_screenshots(
    img1_path: str,
    img2_path: str,
    target_size: tuple[int, int] = (800, 600),
) -> float:
    """比较两张截图的相似度。

    Args:
        img1_path: 第一张图片的文件路径
        img2_path: 第二张图片的文件路径
        target_size: 统一缩放的目标尺寸 (width, height)

    Returns:
        0‑1 之间的 SSIM 相似度分数
    """
    img1 = Image.open(img1_path).convert("L").resize(target_size)
    img2 = Image.open(img2_path).convert("L").resize(target_size)

    arr1 = np.array(img1)
    arr2 = np.array(img2)

    score = ssim(arr1, arr2)
    return float(score)


def compare_screenshots_tool(
    figma_screenshot_path: str,
    browser_screenshot_path: str,
) -> str:
    """对比 Figma 设计稿截图与浏览器渲染截图的相似度。

    Args:
        figma_screenshot_path: Figma 设计稿截图的文件路径
        browser_screenshot_path: 浏览器渲染截图的文件路径

    Returns:
        对比结果文本，包含相似度百分比和是否通过
    """
    try:
        similarity = compare_screenshots(figma_screenshot_path, browser_screenshot_path)
        passed = similarity >= 0.70
        return (
            f"相似度: {similarity:.2%}\n"
            f"阈值: 70%\n"
            f"结果: {'通过 ✓' if passed else '未通过 ✗'}\n"
            f"{'页面还原度达标' if passed else '页面还原度不足，需要代码编写智能体优化'}"
        )
    except FileNotFoundError as e:
        return f"截图文件不存在: {e}"
    except Exception as e:
        return f"截图对比失败: {type(e).__name__}: {e}"
