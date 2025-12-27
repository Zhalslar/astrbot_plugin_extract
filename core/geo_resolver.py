import aiohttp

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig


class GeoResolver:
    """GPS 逆地理解析"""

    def __init__(self, config: AstrBotConfig):
        self.proxy = config["proxy"] or None
        self.session = aiohttp.ClientSession()

    async def resolve(self, gps_info: dict) -> dict | None:
        """
        对外接口：解析 GPS 信息
        """
        try:
            lat, lon = self._parse_gps(gps_info)
            if lat is None or lon is None:
                return None
        except Exception as e:
            logger.warning(f"GPS 解析失败: {e}")
            return None

        try:
            async with self.session.get(
                url="https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lon,
                    "zoom": 18,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "AstrBot-ExtractPlugin/1.0.0"},
                proxy=self.proxy,
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"逆地理失败 HTTP {resp.status}")
                    return None

                data = await resp.json()
                return data.get("display_name")

        except Exception as e:
            logger.warning(f"获取地理位置异常: {e}")
            return None

    # ---------- 内部工具 ----------

    def _parse_gps(self, info: dict):
        try:
            lat_dms, lat_ref = info[2], info[1]
            lon_dms, lon_ref = info[4], info[3]

            lat = self._dms2dec(lat_dms, lat_ref)
            lon = self._dms2dec(lon_dms, lon_ref)

            return lat, lon
        except (KeyError, TypeError, ZeroDivisionError):
            return None, None

    @staticmethod
    def _dms2dec(dms, ref: str) -> float:
        deg, minute, sec = dms
        dec = float(deg) + float(minute) / 60 + float(sec) / 3600
        return -dec if ref in {"S", "W"} else dec

    async def close(self):
        await self.session.close()
