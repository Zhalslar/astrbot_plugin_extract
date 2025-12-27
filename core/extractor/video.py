import json
import os
import subprocess
from tempfile import NamedTemporaryFile

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from ..file_type import FileExt
from ..utils import get_storage_size


class VideoExtractor:
    """视频信息提取器（ffprobe 优先）"""

    def __init__(self, config: AstrBotConfig):
        self.conf = config

    async def get_video_info(self, video: bytes, ext: FileExt) -> str | None:
        details = self._parse_by_ffprobe(video)
        logger.debug(f"[视频信息] 解析结果: {details}")
        return self._format_details(details, ext) if details else None

    # -------------------- ffprobe 解析 --------------------

    def _parse_by_ffprobe(self, data: bytes) -> dict | None:
        tmp_path = None
        try:
            with NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(data)
                f.flush()
                tmp_path = f.name

            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                tmp_path,
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5,
            )

            # --- 调试信息 ---
            logger.debug(
                f"ffprobe returncode={proc.returncode}, stdout_len={len(proc.stdout or b'')}, stderr_len={len(proc.stderr or b'')}"
            )

            if proc.stderr:
                logger.debug(f"ffprobe stderr: {proc.stderr[:500]!r}")

            if proc.returncode != 0:
                logger.warning("ffprobe 执行失败")
                return None

            if not proc.stdout:
                logger.warning("ffprobe 无 stdout 输出")
                return None

            try:
                info = json.loads(proc.stdout)
            except json.JSONDecodeError as e:
                logger.warning(
                    "ffprobe JSON 解析失败: %s, raw=%r",
                    e,
                    proc.stdout[:500],
                )
                return None

        except Exception as e:
            logger.error(f"ffprobe 调用异常: {e}")
            return None

        finally:
            if tmp_path:
                os.remove(tmp_path)

        return self._parse_ffprobe_result(info, data)

    # -------------------- 解析结构 --------------------

    def _parse_ffprobe_result(self, info: dict, data: bytes) -> dict:
        video_stream = None
        audio_stream = None

        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video" and not video_stream:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and not audio_stream:
                audio_stream = stream

        result = {
            "format": info.get("format", {}).get("format_name"),
            "file_size": get_storage_size(data),
        }

        if duration := info.get("format", {}).get("duration"):
            result["duration"] = round(float(duration), 2)

        if video_stream:
            result.update(
                {
                    "width": video_stream.get("width"),
                    "height": video_stream.get("height"),
                    "fps": self._calc_fps(video_stream),
                    "video_codec": video_stream.get("codec_name"),
                }
            )

        if audio_stream:
            result.update(
                {
                    "audio_codec": audio_stream.get("codec_name"),
                    "channels": audio_stream.get("channels"),
                    "sample_rate": audio_stream.get("sample_rate"),
                }
            )

        return result

    # -------------------- 工具方法 --------------------

    def _calc_fps(self, stream: dict) -> float | None:
        rate = stream.get("avg_frame_rate")
        if not rate or rate == "0/0":
            return None
        try:
            num, den = map(int, rate.split("/"))
            return round(num / den, 2) if den else None
        except Exception:
            return None

    # -------------------- 输出格式化 --------------------

    def _format_details(self, info: dict, ext: FileExt) -> str:
        lines = ["【视频信息】："]

        lines.append(f"格式: {ext}")
        if size := info.get("file_size"):
            lines.append(f"大小: {size}")
        if dur := info.get("duration"):
            lines.append(f"时长: {dur}s")

        if res := (info.get("width"), info.get("height")):
            if all(res):
                lines.append(f"分辨率: {res[0]}×{res[1]}")

        if fps := info.get("fps"):
            lines.append(f"帧率: {fps} fps")

        if vcodec := info.get("video_codec"):
            lines.append(f"视频编码: {vcodec}")

        if acodec := info.get("audio_codec"):
            lines.append(f"音频编码: {acodec}")

        if ch := info.get("channels"):
            lines.append(f"声道数: {ch}")

        return "\n".join(lines).strip()
