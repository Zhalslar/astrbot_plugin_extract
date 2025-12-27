import re
from io import BytesIO

from PIL import ExifTags, Image

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from ..file_type import FileExt
from ..geo_resolver import GeoResolver
from ..utils import get_storage_size

# 中英文映射
KEY_MAP = {
    "ImageWidth": "图像宽度",
    "ImageLength": "图像长度",
    "GPSInfo": "GPS信息",
    "ResolutionUnit": "分辨率单位",
    "ExifOffset": "EXIF偏移量",
    "Make": "制造商",
    "Model": "型号",
    "Orientation": "方向",
    "DateTime": "日期时间",
    "YCbCrPositioning": "YCbCr定位",
    "XResolution": "X方向分辨率",
    "YResolution": "Y方向分辨率",
    "ExifVersion": "EXIF版本",
    "SceneType": "场景类型",
    "ApertureValue": "光圈值",
    "ColorSpace": "颜色空间",
    "ExposureBiasValue": "曝光偏差",
    "MaxApertureValue": "最大光圈值",
    "ExifImageHeight": "EXIF图像高度",
    "BrightnessValue": "亮度值",
    "DateTimeOriginal": "原始日期时间",
    "FlashPixVersion": "FlashPix版本",
    "WhiteBalance": "白平衡",
    "ExifInteroperabilityOffset": "EXIF互操作性偏移量",
    "Flash": "闪光灯",
    "ExifImageWidth": "EXIF图像宽度",
    "ComponentsConfiguration": "组件配置",
    "MeteringMode": "测光模式",
    "OffsetTime": "时区偏移",
    "SubsecTimeOriginal": "原始亚秒时间",
    "SubsecTime": "亚秒时间",
    "SubsecTimeDigitized": "数字化亚秒时间",
    "OffsetTimeOriginal": "原始时区偏移",
    "DateTimeDigitized": "数字化日期时间",
    "OffsetTimeDigitized": "数字化时区偏移",
    "ShutterSpeedValue": "快门速度值",
    "SensingMethod": "感光方法",
    "ExposureTime": "曝光时间",
    "FNumber": "F值",
    "ExposureProgram": "曝光程序",
    "ISOSpeedRatings": "ISO速度等级",
    "ISOSpeed": "ISO速度",
    "ExposureMode": "曝光模式",
    "LightSource": "光源",
    "FocalLengthIn35mmFilm": "35mm胶片焦距",
    "SceneCaptureType": "场景捕获类型",
    "FocalLength": "焦距",
    "Software": "软件",
    "SensitivityType": "敏感度类型",
    "RecommendedExposureIndex": "推荐曝光指数",
    "DigitalZoomRatio": "数字缩放比",
    "UserComment": "用户备注",
    "MakerNote": "制造商备注",
    "JpegIFOffset": "JPEG IF偏移量",
    "JpegIFByteCount": "JPEG IF字节数",
    "filter": "滤镜",
    "filterIntensity": "滤镜强度",
    "filterMask": "滤镜掩码",
    "captureOrientation": "拍摄方向",
    "highlight": "高光增强",
    "algolist": "算法列表",
    "multi-frame": "多帧合成",
    "brp_mask": "BRP掩码",
    "brp_del_th": "BRP阈值",
    "brp_del_sen": "BRP灵敏度",
    "motionLevel": "运动等级",
    "delta": "Delta变化",
    "module": "模块",
    "hw-remosaic": "重采样硬件",
    "touch": "触摸对焦点",
    "sceneMode": "场景模式",
    "cct_value": "色温值",
    "AI_Scene": "AI场景",
    "aec_lux": "曝光光照值",
    "aec_lux_index": "曝光指数",
    "HdrStatus": "HDR状态",
    "albedo": "反照率",
    "confidence": "置信度",
    "weatherinfo": "天气信息",
    "temperature": "温度",
    "fileterIntensity": "滤镜强度",
    "ImageDescription": "图片描述",
    "BitsPerSample": "每样本位数",
    "Compression": "压缩方式",
    "PhotometricInterpretation": "光度解释",
    "StripOffsets": "条带偏移量",
    "SamplesPerPixel": "每像素样本数",
    "RowsPerStrip": "每条带行数",
    "StripByteCounts": "条带字节数",
    "Artist": "艺术家",
    "HostComputer": "主机计算机",
    "Copyright": "版权",
    "ColorMap": "颜色映射表",
    "ISOspeed ratings": "ISO速度等级",
    "CompressedBitsPerPixel": "每像素压缩位数",
    "SubjectDistance": "主体距离",
    "RelatedSoundFile": "相关声音文件",
    "InteroperabilityOffset": "EXIF互操作性偏移量",
    "FocalPlaneXResolution": "焦平面X分辨率",
    "FocalPlaneYResolution": "焦平面Y分辨率",
    "FocalPlaneResolutionUnit": "焦平面分辨率单位",
    "FileSource": "文件源",
    "CFAPattern": "CFA模式",
    "CustomRendered": "自定义渲染",
    "GainControl": "增益控制",
    "Contrast": "对比度",
    "Saturation": "饱和度",
    "Sharpness": "锐度",
    "DeviceSettingDescription": "设备设置描述",
    "SubjectDistanceRange": "主体距离范围",
    "LensMake": "镜头制造商",
    "LensModel": "镜头型号",
    "LensSpecification": "镜头规格",
}


class ImageExtractor:
    """图片信息提取器"""

    def __init__(self, config: AstrBotConfig, geo_resolver: GeoResolver):
        self.conf = config
        self.geo_resolver = geo_resolver
        self.key_map = KEY_MAP

    async def get_image_info(self, image: bytes, ext: FileExt) -> str | None:
        """对外统一入口：返回格式化后的图片信息字符串"""
        details = await self._get_image_details(image)
        logger.debug(f"[图片信息] 解析结果: {details}")
        return self._format_details(details) if details else None

    async def _get_image_details(self, img_bytes: bytes) -> dict:
        """提取图片的详细信息"""

        with Image.open(BytesIO(img_bytes)) as img:
            info = {
                "actual_format": img.format,
                "size": img.size,
                "file_size": get_storage_size(img_bytes),
                "mode": img.mode,
            }

            # DPI
            dpi = img.info.get("dpi")
            if dpi:
                info["dpi"] = dpi

            # 内置缩略图
            thumb = img.info.get("thumbnail")
            if thumb:
                info["thumbnail"] = {"size": thumb.size, "mode": thumb.mode}

            # EXIF
            exif_data = getattr(img, "_getexif", lambda: None)()
            if exif_data:
                exif_info = {
                    ExifTags.TAGS.get(k, k): v
                    for k, v in exif_data.items()
                    if k in ExifTags.TAGS
                }
                # 处理GPS信息
                if "GPSInfo" in exif_info:
                    gps_raw = exif_info.pop("GPSInfo")
                    if self.conf["enable_geo_resolver"]:
                        info["gps_info"] = (
                            await self.geo_resolver.resolve(gps_raw) or gps_raw
                        )
                    else:
                        info["gps_info"] = gps_raw

                # 用户备注
                if "UserComment" in exif_info:
                    raw_comment = exif_info.pop("UserComment")
                    exif_info["UserComment"] = (
                        self._parse_and_join(raw_comment) or raw_comment
                    )
                # 转中文标签
                exif_chinese = {
                    self.key_map.get(tag, tag): value
                    for tag, value in exif_info.items()
                }
                info["exif"] = exif_chinese

            return info

    def _parse_and_join(self, text: str) -> str:
        """解析调试字符串 → 映射中文 → 拼接为一个整字符串"""
        result = {}

        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8")
            except UnicodeDecodeError:
                text = text.decode("latin-1", errors="ignore")
        # 按 ; 分割，过滤掉空字段
        parts = [p.strip() for p in text.split(";") if p.strip()]

        for part in parts:
            if ":" not in part:
                continue

            key, value = part.split(":", 1)
            key = key.strip()
            value = value.strip()

            # === 值解析 ===
            if value.lower() == "null" or value == "":
                value = None

            # (x, y) → tuple
            elif re.match(r"\(-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?\)", value):
                nums = re.findall(r"-?\d+\.?\d*", value)
                value = tuple(float(n) for n in nums)

            # 数字转换 → int/float
            else:
                if re.fullmatch(r"-?\d+", value):
                    value = int(value)
                elif re.fullmatch(r"-?\d+\.\d+", value):
                    value = float(value)

            # === 字段名中英文转换 ===
            cn_key = self.key_map.get(key, key)  # 没定义就用原英文
            result[cn_key] = value

        return "\n" + "\n".join(f"{k}: {v}" for k, v in result.items())

    def _format_details(self, info: dict) -> str:
        """将图片信息整理为可读文本"""

        s = "【图片信息】：\n"
        s += f"格式: {info.get('actual_format')}\n"
        s += f"尺寸: {info.get('size')}\n"
        s += f"大小: {info.get('file_size')}\n"
        s += f"颜色模式: {info.get('mode')}"

        if dpi := info.get("dpi"):
            s += f"\nDPI: {dpi}"

        if thumb := info.get("thumbnail"):
            s += f"\n缩略图: 尺寸 {thumb['size']}，模式 {thumb['mode']}"

        if gps := info.get("gps_info"):
            s += f"\nGPS信息: {gps}"

        if exif := info.get("exif"):
            s += "\n"
            for k, v in exif.items():
                s += f"{k}: {v}\n"

        return s.strip()
