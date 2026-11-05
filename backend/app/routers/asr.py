"""语音识别（ASR）路由：音频文件 → 文本"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services import asr_client

router = APIRouter(prefix="/api/asr", tags=["语音识别"])


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(..., description="音频文件（wav/pcm/amr/m4a，建议60秒以内）"),
    format: str = Form("wav", description="音频格式: wav/pcm/amr/m4a"),
    sample_rate: int = Form(16000, description="采样率: 8000 或 16000"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传音频文件，调用百度 ASR 转写为文本

    返回:
        { "text": "识别出的文本", "duration_ms": 音频时长估算 }
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="音频文件为空")

    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="音频文件过大，请控制在 10MB 以内")

    text, err = await asr_client.transcribe(
        audio_bytes=audio_bytes,
        format=format,
        sample_rate=sample_rate,
    )

    if err:
        # 未配置用 503，其他识别错误用 500，前端按状态码区分提示
        code = 503 if "未配置" in err or "API Key" in err else 500
        raise HTTPException(status_code=code, detail=err)

    estimated_duration_ms = int(len(audio_bytes) / 32 if format == "wav" else len(audio_bytes) / 16)

    return {"text": text, "duration_ms": estimated_duration_ms}


@router.get("/status")
def asr_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """检查 ASR 服务是否可用（API Key 是否已配置）"""
    from app.config import settings
    configured = bool(settings.BAIDU_ASR_API_KEY and settings.BAIDU_ASR_SECRET_KEY)
    return {
        "configured": configured,
        "provider": "baidu" if configured else None,
        "message": "ASR 已就绪" if configured else "ASR 未配置，请在 .env 中设置 BAIDU_ASR_API_KEY 和 BAIDU_ASR_SECRET_KEY",
    }
