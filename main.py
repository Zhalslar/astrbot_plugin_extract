from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from .core.image_extract import ImageInfoExtractor
from .core.utils import download_file, get_image


class ExtractPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.image_extractor = ImageInfoExtractor(config)

    @filter.command("解析")
    async def parse(self, event: AstrMessageEvent):
        """解析图片的信息"""
        image_url = await get_image(event)
        if not image_url:
            yield event.plain_result("未指定要解析的图片")
            return
        image = await download_file(image_url)
        if not image:
            yield event.plain_result("图片下载失败")
            return
        info_str = await self.image_extractor.get_image_info(image)
        if not info_str:
            yield event.plain_result("解析信息时出错")
            return
        yield event.plain_result(info_str)
