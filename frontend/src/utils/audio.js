/**
 * 音频处理工具
 * 浏览器 MediaRecorder 默认录的是 webm/opus，但百度 ASR 只支持 pcm/wav/amr/m4a。
 * 所以这里用 Web Audio API 把录音解码 → 重采样到 16kHz 单声道 → 编码为 WAV(PCM16)。
 */

/**
 * 将音频 Blob（webm/ogg/m4a 等）转换为 16kHz 单声道 WAV Blob
 * @param {Blob} blob - MediaRecorder 产出的音频 Blob
 * @param {number} targetSampleRate - 目标采样率，百度 ASR 要求 8000 或 16000
 * @returns {Promise<Blob>} WAV 格式 Blob
 */
export async function convertToWav(blob, targetSampleRate = 16000) {
  const arrayBuffer = await blob.arrayBuffer()

  // 用离线 AudioContext 解码（注意：解码用的 context 采样率不影响后续重采样）
  const decodeCtx = new (window.AudioContext || window.webkitAudioContext)()
  const audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer)
  decodeCtx.close()

  // 混合为单声道
  const channelCount = audioBuffer.numberOfChannels
  let inputData = audioBuffer.getChannelData(0)
  if (channelCount > 1) {
    const mixed = new Float32Array(audioBuffer.length)
    for (let ch = 0; ch < channelCount; ch++) {
      const data = audioBuffer.getChannelData(ch)
      for (let i = 0; i < data.length; i++) mixed[i] += data[i] / channelCount
    }
    inputData = mixed
  }

  // 重采样到 targetSampleRate（线性插值）
  const inputSampleRate = audioBuffer.sampleRate
  let resampled = inputData
  if (inputSampleRate !== targetSampleRate) {
    const ratio = inputSampleRate / targetSampleRate
    const newLength = Math.round(inputData.length / ratio)
    resampled = new Float32Array(newLength)
    for (let i = 0; i < newLength; i++) {
      const srcIndex = i * ratio
      const index0 = Math.floor(srcIndex)
      const index1 = Math.min(index0 + 1, inputData.length - 1)
      const frac = srcIndex - index0
      resampled[i] = inputData[index0] * (1 - frac) + inputData[index1] * frac
    }
  }

  // 编码为 16-bit PCM WAV
  return encodeWav(resampled, targetSampleRate)
}

/**
 * 把 Float32 单声道 PCM 编码为 WAV(PCM16) Blob
 */
function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  // RIFF 头
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')

  // fmt 子块
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // 子块大小
  view.setUint16(20, 1, true) // PCM 格式
  view.setUint16(22, 1, true) // 单声道
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // 字节率 = 采样率 × 通道数 × 位深/8
  view.setUint16(32, 2, true) // 块对齐
  view.setUint16(34, 16, true) // 16 位

  // data 子块
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)

  // 写入 PCM 采样（Float32 → Int16）
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += 2
  }

  return new Blob([view], { type: 'audio/wav' })
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i))
  }
}
