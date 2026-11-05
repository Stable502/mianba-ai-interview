"""百度语音识别 ASR 客户端封装

使用百度智能云「语音识别 - 短语音识别」接口：
1. 用 API Key + Secret Key 换取 access_token
2. 将音频 base64 编码后 POST 到 ASR 接口

音频要求：pcm/wav/amr/m4a，采样率 8000 或 16000，单声道，60 秒以内。
"""
import base64
import json
import time
from typing import Optional

import httpx

from app.config import settings

_TOKEN_CACHE: dict = {"token": None, "expires_at": 0}


def is_configured() -> bool:
    """ASR 是否已配置 API Key"""
    return bool(settings.BAIDU_ASR_API_KEY and settings.BAIDU_ASR_SECRET_KEY)


async def _get_access_token() -> tuple[Optional[str], Optional[str]]:
    """获取百度 API access_token（带进程内缓存）

    Returns: (token, error)；成功时 error=None，失败时 token=None
    """
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
        return _TOKEN_CACHE["token"], None

    if not is_configured():
        return None, "未配置 BAIDU_ASR_API_KEY / BAIDU_ASR_SECRET_KEY"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://aip.baidubce.com/oauth/2.0/token",
                params={
                    "grant_type": "client_credentials",
                    "client_id": settings.BAIDU_ASR_API_KEY,
                    "client_secret": settings.BAIDU_ASR_SECRET_KEY,
                },
            )
            r.raise_for_status()
            data = r.json()
            token = data.get("access_token")
            if not token:
                err = data.get("error_description") or data.get("error") or "token 返回为空"
                return None, f"百度鉴权失败：{err}（请检查 API Key / Secret Key 是否正确）"
            expires_in = data.get("expires_in", 2592000)
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return token, None
    except Exception as e:
        return None, f"百度鉴权网络异常：{e}"


async def transcribe(
    audio_bytes: bytes,
    format: str = "wav",
    sample_rate: int = 16000,
    channel: int = 1,
    timeout: float = 15.0,
) -> tuple[Optional[str], Optional[str]]:
    """将音频字节转写为文本

    Returns: (text, error)；成功时 error=None 且 text 为识别结果；
             失败时 text=None 且 error 为可直接展示给用户的中文错误信息。
    """
    if not is_configured():
        return None, "未配置百度 ASR API Key，请在 backend/.env 中填写 BAIDU_ASR_API_KEY 和 BAIDU_ASR_SECRET_KEY"
    if not audio_bytes:
        return None, "音频内容为空"

    token, err = await _get_access_token()
    if err:
        return None, err

    try:
        payload = {
            "format": format,
            "rate": sample_rate,
            "channel": channel,
            "cuid": "interview-ai-web",
            "token": token,
            "speech": base64.b64encode(audio_bytes).decode("utf-8"),
            "len": len(audio_bytes),
            "dev_pid": int(settings.BAIDU_ASR_DEV_PID),
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://vop.baidu.com/server_api",
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload).encode("utf-8"),
            )
            r.raise_for_status()
            data = r.json()

        if data.get("err_no") == 0:
            result_list = data.get("result", [])
            text = "".join(result_list).strip()
            return (text if text else None), (None if text else "未识别到语音内容")

        # 百度返回的常见错误码翻译
        err_no = data.get("err_no")
        err_msg = data.get("err_msg", "")
        hint = {
            3300: "请求参数错误（音频格式/采样率不匹配）",
            3301: "音频质量不佳或格式不支持，请重新录音",
            3302: "语音识别服务认证失败，请检查 API Key",
            3303: "语音识别服务后端错误，请稍后重试",
            3304: "请求超时，请缩短录音时长后重试",
            3305: "音频过长（限制 60 秒以内）",
        }.get(err_no, f"百度识别错误({err_no})：{err_msg}")
        return None, hint
    except Exception as e:
        return None, f"语音识别请求异常：{e}"
