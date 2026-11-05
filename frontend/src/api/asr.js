import request from './request'

/**
 * 语音识别 API
 * 将浏览器录音（Blob）上传到后端，后端调用百度 ASR 转写为文本
 */
export const asrApi = {
  /**
   * 上传音频文件进行语音识别
   * @param {Blob} audioBlob - 音频 Blob（建议 wav 格式，16kHz 单声道）
   * @param {string} format - 音频格式 wav/pcm/amr/m4a
   * @param {number} sampleRate - 采样率 8000 或 16000
   * @returns {Promise<{text: string, duration_ms: number}>}
   */
  transcribe: (audioBlob, format = 'wav', sampleRate = 16000) => {
    const formData = new FormData()
    formData.append('audio', audioBlob, `recording_${Date.now()}.wav`)
    formData.append('format', format)
    formData.append('sample_rate', String(sampleRate))
    return request.post('/asr/transcribe', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  /** 检查 ASR 服务是否已配置 */
  status: () => request.get('/asr/status'),
}
