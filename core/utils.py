import io
import os
import re

import aiohttp
from PIL import Image as PILImage

from astrbot import logger
from astrbot.core.message.components import At, Image, Reply
from astrbot.core.platform.astr_message_event import AstrMessageEvent


def get_dirs(path: str) -> list[str]:
    """
    获取指定目录下的所有子目录路径（不包括文件）
    """
    directories = []
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir():
                directories.append(entry.path)
    return directories


async def download_file(url: str) -> bytes | None:
    """下载图片"""
    url = url.replace("https://", "http://")
    try:
        async with aiohttp.ClientSession() as client:
            response = await client.get(url)
            img_bytes = await response.read()
            return img_bytes
    except Exception as e:
        logger.error(f"图片下载失败: {e}")


async def get_nickname(event: AstrMessageEvent, target_id: str):
    """从消息平台获取参数"""
    if event.get_platform_name() == "aiocqhttp":
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
            AiocqhttpMessageEvent,
        )

        assert isinstance(event, AiocqhttpMessageEvent)
        client = event.bot
        user_info = await client.get_stranger_info(user_id=int(target_id))
        return user_info.get("nickname")
    # TODO 适配更多消息平台
    return f"{target_id}"


async def get_image(event: AstrMessageEvent, reply: bool = True) -> str | None:
    """获取图片"""
    chain = event.get_messages()
    # 遍历引用消息
    if reply:
        reply_seg = next((seg for seg in chain if isinstance(seg, Reply)), None)
        if reply_seg and reply_seg.chain:
            for seg in reply_seg.chain:
                if isinstance(seg, Image):
                    if img_url := seg.url:
                        return img_url

    # 遍历原始消息
    for seg in chain:
        if isinstance(seg, Image):
            if img_url := seg.url:
                return img_url


def filter_text(text: str, max_length: int = 128) -> str:
    """过滤字符，只保留中文、数字和字母, 并截短非数字字符串"""
    f_str = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text)
    return f_str if f_str.isdigit() else f_str[:max_length]


async def get_args(event: AstrMessageEvent):
    """获取参数"""
    # 初始化默认值
    sender_id = filter_text(event.get_sender_id())
    sender_name = filter_text(event.get_sender_name())

    # 解析消息文本
    args = event.message_str.strip().split()[1:]
    texts: list[str] = []
    numbers: list[int] = []
    at_names: list[str] = []

    for arg in args:
        if arg.isdigit():
            num = int(arg)
            if 0 < num < 10000:
                numbers.append(num)  # 满足条件的数字加入 indexs
            else:
                texts.append(arg)  # 不满足条件的数字加入 texts
        else:  # 如果是文本
            if filtered_arg := filter_text(arg):
                if arg.startswith("@"):
                    at_names.append(filtered_arg)
                else:
                    texts.append(filtered_arg)

    # 获取消息链
    chain = event.get_messages().copy()

    # 去除开头的Reply和At
    while chain and (isinstance(chain[0], Reply) or isinstance(chain[0], At)):
        chain.pop(0)

    # 获取@列表
    at_ids = [str(seg.qq) for seg in chain if isinstance(seg, At)]

    # 获取回复信息
    reply_seg = next(
        (seg for seg in event.get_messages() if isinstance(seg, Reply)), None
    )
    reply_name = (
        filter_text(await get_nickname(event, str(reply_seg.sender_id)))
        if reply_seg
        else None
    )
    names = at_ids or texts or [sender_id]
    labels = [name for name in (at_names, reply_name, sender_name, sender_id) if name]

    # 返回参数字典
    return {
        "texts": texts,
        "numbers": numbers or [0],
        "names": names,
        "labels": labels,
    }


def compress_image(image: bytes, max_size: int = 512) -> bytes | None:
    """压缩图片"""
    try:
        with PILImage.open(io.BytesIO(image)) as img:
            # GIF 不压缩
            if img.format == "GIF":
                return image
            # 尺寸不超过 max_size，不压缩
            if img.width <= max_size and img.height <= max_size:
                return image
            # 执行压缩
            img.thumbnail((max_size, max_size), PILImage.Resampling.LANCZOS)
            output = io.BytesIO()
            img.save(output, format=img.format)
            return output.getvalue()
    except Exception as e:
        logger.error(f"压缩图片失败：{e}")
        return None
