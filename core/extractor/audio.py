from io import BytesIO

from mutagen._file import File as MutagenFile

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from ..file_type import FileExt
from ..utils import get_storage_size


class AudioExtractor:
    """音频信息提取器（AMR 兜底 + mutagen）"""

    def __init__(self, config: AstrBotConfig):
        self.conf = config

    async def get_audio_info(self, audio: bytes, ext: FileExt) -> str | None:
        details = self._get_audio_details(audio, ext)
        logger.debug(f"[音频信息] 解析结果: {details}")
        return self._format_details(details) if details else None

    # -------------------- 内部逻辑 --------------------
    def _get_audio_details(self, audio: bytes, ext: FileExt) -> dict | None:
        # 1. AMR 裸流特殊处理
        if ext == FileExt.AMR:
            return self._parse_amr(audio)

        # 2. 其它格式交给 mutagen
        try:
            file = MutagenFile(BytesIO(audio))
            if not file:
                return None
        except Exception as e:
            logger.debug(f"mutagen 解析失败: {e}")
            return None

        info = {
            "format": file.mime[0] if file.mime else None,
            "file_size": get_storage_size(audio),
        }
        if file.info:
            info.update(
                {
                    "duration": round(getattr(file.info, "length", 0), 2),
                    "bitrate": getattr(file.info, "bitrate", None),
                    "sample_rate": getattr(file.info, "sample_rate", None),
                    "channels": getattr(file.info, "channels", None),
                }
            )
        if file.tags:
            info["tags"] = {
                k: ", ".join(map(str, v)) if isinstance(v, list | tuple) else str(v)
                for k, v in file.tags.items()
            }
        return info

    # --------------- AMR-NB 专用解析 ---------------
    def _parse_amr(self, data: bytes) -> dict:
        # AMR-NB 固定参数
        FRAME_MS = 20 / 1000  # 20 ms
        FRAME_SIZE = 32  # 字节/帧
        frames = (len(data) - 6) // FRAME_SIZE
        return {
            "format": "AMR-NB",
            "file_size": get_storage_size(data),
            "duration": round(frames * FRAME_MS, 2),
            "sample_rate": 8000,  # 标准固定值
            "channels": 1,  # 单声道
            "bitrate": 12.2,  # 平均 12.2 kbps
        }

    # --------------- 统一格式化 ---------------
    def _format_details(self, info: dict) -> str:
        lines = ["【音频信息】："]
        if fmt := info.get("format"):
            lines.append(f"格式: {fmt}")
        if size := info.get("file_size"):
            lines.append(f"大小: {size}")
        if dur := info.get("duration"):
            lines.append(f"时长: {dur}s")
        if br := info.get("bitrate"):
            lines.append(f"比特率: {br} kbps")
        if sr := info.get("sample_rate"):
            lines.append(f"采样率: {sr} Hz")
        if ch := info.get("channels"):
            lines.append(f"声道数: {ch}")
        if tags := info.get("tags"):
            lines.append("\n标签信息:")
            lines.extend(f"{k}: {v}" for k, v in tags.items())
        return "\n".join(lines).strip()
