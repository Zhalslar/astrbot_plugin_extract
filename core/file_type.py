from enum import Enum


class FileExt(str, Enum):
    JPG = "jpg"
    PNG = "png"
    GIF = "gif"
    WEBP = "webp"

    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"
    AMR = "amr"

    MP4 = "mp4"
    MKV = "mkv"

    UNKNOWN = "unknown"

    # ---------- 分类集合 ----------

    @classmethod
    def image_types(cls) -> set["FileExt"]:
        return {
            cls.JPG,
            cls.PNG,
            cls.GIF,
            cls.WEBP,
        }

    @classmethod
    def audio_types(cls) -> set["FileExt"]:
        return {
            cls.MP3,
            cls.WAV,
            cls.OGG,
            cls.FLAC,
            cls.AMR,
        }

    @classmethod
    def video_types(cls) -> set["FileExt"]:
        return {
            cls.MP4,
            cls.MKV,
        }

    # ---------- 实例判断 ----------

    def is_image(self) -> bool:
        return self in self.image_types()

    def is_audio(self) -> bool:
        return self in self.audio_types()

    def is_video(self) -> bool:
        return self in self.video_types()

    def is_known(self) -> bool:
        return self is not FileExt.UNKNOWN

    @classmethod
    def from_bytes(cls, data: bytes) -> "FileExt":
        if not data:
            return cls.UNKNOWN

        head = data[:16]

        # --- image ---
        if head.startswith(b"\xff\xd8\xff"):
            return cls.JPG
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return cls.PNG
        if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
            return cls.GIF
        if head.startswith(b"RIFF") and b"WEBP" in head:
            return cls.WEBP

        # --- audio ---
        if head.startswith(b"ID3") or head[:2] == b"\xff\xfb":
            return cls.MP3
        if head.startswith(b"RIFF") and b"WAVE" in head:
            return cls.WAV
        if head.startswith(b"OggS"):
            return cls.OGG
        if head.startswith(b"fLaC"):
            return cls.FLAC
        if head.startswith(b"#!AMR"):
            return cls.AMR

        # --- video ---
        if b"ftyp" in head:
            return cls.MP4
        if head.startswith(b"\x1a\x45\xdf\xa3"):
            return cls.MKV

        return cls.UNKNOWN
