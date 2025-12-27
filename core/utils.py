import aiohttp

from astrbot import logger
from astrbot.core.message.components import File, Image, Record, Reply, Video
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


def get_reply_id(event: AiocqhttpMessageEvent) -> int | None:
    """获取被引用消息的id"""
    for seg in event.get_messages():
        if isinstance(seg, Reply):
            return int(seg.id)


async def get_media(event: AstrMessageEvent) -> str | None:
    """获取媒体文件"""
    Media = Image | Record | Video | File
    chain = event.get_messages()
    url = None

    def extract_media_url(seg):
        url_ = (
            getattr(seg, "url", None)
            or getattr(seg, "file", None)
            or getattr(seg, "path", None)
        )
        return url_ if url_ and str(url_).startswith("http") else None

    # 遍历引用消息
    reply_seg = next((seg for seg in chain if isinstance(seg, Reply)), None)
    if reply_seg and reply_seg.chain:
        for seg in reply_seg.chain:
            if isinstance(seg, Media):
                url = extract_media_url(seg)

    # 遍历原始消息
    if url is None:
        for seg in chain:
            if isinstance(seg, Media):
                url = extract_media_url(seg)

    # 从原始的引用消息中获取
    if url is None and isinstance(event, AiocqhttpMessageEvent):
        if msg_id := get_reply_id(event):
            raw = await event.bot.get_msg(message_id=msg_id)
            messages = raw.get("message", [])
            for seg in messages:
                if isinstance(seg, dict):
                    if seg_url := seg.get("data", {}).get("url"):
                        url = seg_url

    return url

async def download_file(url: str) -> bytes | None:
    """下载文件"""
    url = url.replace("https://", "http://")
    try:
        async with aiohttp.ClientSession() as client:
            response = await client.get(url)
            date = await response.read()
            return date
    except Exception as e:
        logger.error(f"下载失败: {e}")


def get_storage_size(img_bytes: bytes) -> str:
    """字节大小转 KB/MB"""

    if not img_bytes:
        logger.warning("无法获取图片大小（bytes为空）")
        return ""

    size = len(img_bytes)

    if size > 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / 1024:.2f} KB"
