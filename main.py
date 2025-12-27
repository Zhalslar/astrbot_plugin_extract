from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .core.extractor import AudioExtractor, ImageExtractor, VideoExtractor
from .core.file_type import FileExt
from .core.geo_resolver import GeoResolver
from .core.utils import download_file, get_media, get_reply_id


class ExtractPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.extract_types = self.config["extract_types"]
        self.geo_resolver = GeoResolver(config)
        self.image_extractor = ImageExtractor(config, self.geo_resolver)
        self.audio_extractor = AudioExtractor(config)
        self.video_extractor = VideoExtractor(config)

    async def terminate(self):
        await self.geo_resolver.close()

    @filter.command("raw")
    async def raw(self, event: AstrMessageEvent):
        """查看消息的原始结构"""
        if isinstance(event, AiocqhttpMessageEvent):
            if msg_id := get_reply_id(event):
                msg = await event.bot.get_msg(message_id=msg_id)
                yield event.plain_result(str(msg))
        else:
            yield event.plain_result(str(event.message_obj.raw_message))

    @filter.command("解析")
    async def parse(self, event: AstrMessageEvent):
        """解析媒体的信息"""
        url = await get_media(event)
        if not url:
            yield event.plain_result("没解析到有效的URL")
            return
        logger.debug(f"解析媒体: {url}")
        data = await download_file(url)
        if not data:
            yield event.plain_result("媒体下载失败")
            return

        ext = FileExt.from_bytes(data)
        logger.debug(f"媒体类型: {ext}")

        if ext.is_image() and "image" in self.extract_types:
            info = await self.image_extractor.get_image_info(data, ext)

        elif ext.is_audio() and "audio" in self.extract_types:
            info = await self.audio_extractor.get_audio_info(data, ext)

        elif ext.is_video() and "video" in self.extract_types:
            info = await self.video_extractor.get_video_info(data, ext)

        else:
            yield event.plain_result("不支持的媒体类型")
            return

        if not info:
            yield event.plain_result("解析信息时出错")
            return

        yield event.plain_result(info)
