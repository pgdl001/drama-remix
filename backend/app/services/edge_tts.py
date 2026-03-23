"""Edge TTS 配音服务 - 微软 Edge 在线语音合成，支持多角色中文配音。"""

import asyncio
import logging
import os
from pathlib import Path

import edge_tts
from edge_tts import Communicate

from app.config import settings

logger = logging.getLogger("edge_tts")

ZH_VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓 (女声-温柔)", "女"),
    ("zh-CN-XiaoyiNeural", "小艺 (女声-活泼)", "女"),
    ("zh-CN-YunxiNeural", "云希 (男声-自然)", "男"),
    ("zh-CN-YunyangNeural", "云扬 (男声-新闻)", "男"),
    ("zh-CN-liaoning-YunxiaNeural", "辽宁小霞 (女声-东北)", "女"),
    ("zh-CN-shaanxi-XiaoniNeural", "陕西小妮 (女声-陕西方言)", "女"),
    ("zh-CN-XiaohanNeural", "晓涵 (女声-成熟)", "女"),
    ("zh-CN-XiaomoNeural", "晓墨 (女声-正式)", "女"),
    ("zh-CN-XiaoqiuNeural", "晓秋 (女声-知性)", "女"),
    ("zh-CN-XiaoshuangNeural", "晓双 (女声-亲切)", "女"),
    ("zh-CN-XiaoyanNeural", "晓艳 (女声-甜美)", "女"),
    ("zh-CN-XiaoyouNeural", "晓悠 (女声-轻松)", "女"),
    ("zh-CN-YunxiNeural", "云希 (男声-自然)", "男"),
    ("zh-CN-YunyangNeural", "云扬 (男声-播音)", "男"),
    ("zh-CN-YunzeNeural", "云泽 (男声-稳重)", "男"),
    ("zh-HK-HiuGaaiNeural", "香港小嘉 (女声-粤语)", "女"),
    ("zh-HK-HiuMaaiNeural", "香港小Maai (女声-粤语)", "女"),
    ("zh-HK-WanLungNeural", "香港云龙 (男声-粤语)", "男"),
    ("zh-TW-HsiaoChenNeural", "台湾晓晨 (女声-台湾)", "女"),
    ("zh-TW-YunJheNeural", "台湾云喆 (男声-台湾)", "男"),
]


async def _synthesize_async(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bool:
    """异步合成语音。"""
    try:
        comm = Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        await comm.save(output_path)
        return Path(output_path).exists()
    except Exception as e:
        logger.error(f"Edge TTS synthesis error: {e}")
        return False


def synthesize_sync(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bool:
    """同步合成语音（阻塞）。"""
    return asyncio.run(_synthesize_async(text, voice, output_path, rate, pitch))


async def synthesize_async(
    text: str,
    voice: str,
    output_path: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> bool:
    """异步合成语音。"""
    return await _synthesize_async(text, voice, output_path, rate, pitch)


def get_voices() -> list[dict]:
    """获取所有可用的中文配音角色。"""
    return [
        {
            "id": short_name,
            "name": friendly_name,
            "gender": gender,
            "short_name": short_name,
        }
        for short_name, friendly_name, gender in ZH_VOICES
    ]


def is_available() -> bool:
    """检查 Edge TTS 是否可用（需要联网）。"""
    try:
        return asyncio.run(_synthesize_async("测试", "zh-CN-XiaoxiaoNeural", os.devnull))
    except Exception:
        return False
