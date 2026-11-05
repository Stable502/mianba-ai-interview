<template>
  <div class="room">
    <!-- 顶部栏 -->
    <div class="room-header">
      <div class="room-left">
        <a-button type="text" @click="backHome">
          <ArrowLeftOutlined /> 返回
        </a-button>
        <div class="room-meta">
          <div class="room-title">{{ session?.persona_name || '模拟面试间' }}</div>
          <div class="room-sub">
            {{ typeName(session?.interview_type) }}
            <template v-if="session?.position_title"> · {{ session.position_title }}</template>
          </div>
        </div>
      </div>
      <div class="room-right">
        <div class="timer" :class="{ warn: remaining <= 0 }">
          <ClockCircleOutlined /> {{ timerText }}
        </div>
        <a-button v-if="!finished" danger size="small" @click="confirmEnd">提前结束</a-button>
      </div>
    </div>

    <!-- 对话区 -->
    <div ref="listRef" class="message-list">
      <div v-if="loading" class="center-hint">正在进入面试间…</div>
      <template v-else>
        <div
          v-for="m in messages"
          :key="m.id"
          class="msg-row"
          :class="m.role === 'candidate' ? 'candidate' : 'interviewer'"
        >
          <div class="bubble">
            <div class="bubble-role">
              {{ m.role === 'candidate' ? '我' : '面试官' }}
            </div>
            <div class="bubble-text">{{ m.content_text }}</div>
          </div>
        </div>

        <div v-if="typing" class="msg-row interviewer">
          <div class="bubble typing">面试官正在思考…</div>
        </div>

        <div v-if="finished" class="center-hint finished-hint">
          <div class="finished-icon">🎉</div>
          <div class="finished-title">面试已结束</div>
          <div class="finished-desc">已生成本次面试的诊断报告</div>
          <a-button type="primary" size="large" :loading="ending" @click="goReport">
            查看诊断报告
          </a-button>
        </div>
      </template>
    </div>

    <!-- 输入区 -->
    <div class="input-bar">
      <!-- 识别中提示 -->
      <div v-if="recognizing" class="recognizing-hint">
        <LoadingOutlined /> 正在识别语音，请稍候…
      </div>

      <!-- 录音中提示 -->
      <div v-if="recording" class="recording-hint">
        <span class="rec-dot"></span>
        录音中 {{ recordingTimeText }} · 松开按钮结束录音
      </div>

      <a-textarea
        v-model:value="draft"
        :rows="2"
        :disabled="finished || sending || recognizing"
        placeholder="输入你的回答，或按住下方麦克风按钮说话…"
        @keydown.enter.exact.prevent="send"
      />
      <div class="input-actions">
        <div class="input-left">
          <!-- 麦克风按钮 -->
          <a-tooltip :title="recording ? '松开结束录音' : '按住录音（语音识别）'">
            <a-button
              shape="circle"
              :type="recording ? 'primary' : 'default'"
              danger
              :disabled="finished || sending || recognizing"
              @mousedown.prevent="startRecording"
              @mouseup.prevent="stopRecording"
              @mouseleave.prevent="stopRecording"
              @touchstart.prevent="startRecording"
              @touchend.prevent="stopRecording"
            >
              <AudioOutlined v-if="!recording" />
              <LoadingOutlined v-else />
            </a-button>
          </a-tooltip>
          <div class="input-hint">
            {{ recording ? '录音中…' : '🎙️ 按住麦克风录音 · ⌨️ Enter 发送' }}
          </div>
        </div>
        <a-button type="primary" :loading="sending" :disabled="finished || !draft.trim() || recognizing" @click="send">
          发送回答
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { ArrowLeftOutlined, AudioOutlined, ClockCircleOutlined, LoadingOutlined } from '@ant-design/icons-vue'
import { interviewApi } from '@/api/interview'
import { asrApi } from '@/api/asr'
import { convertToWav } from '@/utils/audio'
import { typeName } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const sessionId = Number(route.params.id)
const session = ref(null)
const messages = ref([])
const loading = ref(true)
const sending = ref(false)
const typing = ref(false)
const finished = ref(false)
const ending = ref(false)
const finishedReportId = ref(null)
const draft = ref('')
const listRef = ref(null)

// 计时器
const elapsed = ref(0)
let timerHandle = null

// 录音相关
const recording = ref(false)
const recognizing = ref(false)
const recordingElapsed = ref(0)
let recordingTimerHandle = null
let mediaRecorder = null
let audioChunks = []
let audioStream = null

const remaining = computed(() => (session.value?.planned_minutes || 0) * 60 - elapsed.value)
const timerText = computed(() => {
  const abs = Math.max(remaining.value, 0)
  const m = Math.floor(abs / 60)
  const s = abs % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const recordingTimeText = computed(() => {
  const m = Math.floor(recordingElapsed.value / 60)
  const s = recordingElapsed.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

async function load() {
  loading.value = true
  try {
    const [s, msgs] = await Promise.all([
      interviewApi.get(sessionId),
      interviewApi.messages(sessionId),
    ])
    session.value = s
    messages.value = msgs
    if (s.status !== 2) {
      finished.value = true
    }
    if (s.started_at) {
      const start = new Date(s.started_at).getTime()
      elapsed.value = Math.floor((Date.now() - start) / 1000)
      startTimer()
    }
  } catch (e) {
    message.error('面试间加载失败')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function startTimer() {
  if (timerHandle) return
  timerHandle = setInterval(() => {
    elapsed.value += 1
  }, 1000)
}

function scrollToBottom() {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight
    }
  })
}

async function send() {
  const text = draft.value.trim()
  if (!text || sending.value || finished.value) return
  sending.value = true
  draft.value = ''
  messages.value.push({
    id: `local-${Date.now()}`,
    role: 'candidate',
    content_text: text,
  })
  scrollToBottom()
  typing.value = true
  try {
    // 当前回答对应的问题 = 最后一条面试官消息的 question_id
    const lastInterviewer = [...messages.value].reverse().find((m) => m.role === 'interviewer')
    const res = await interviewApi.sendMessage(sessionId, {
      content_text: text,
      question_id: lastInterviewer?.question_id ?? null,
    })
    const localIdx = messages.value.findIndex((m) => m.id?.toString().startsWith('local-'))
    if (localIdx >= 0 && res.candidate_message) {
      messages.value[localIdx] = res.candidate_message
    }
    typing.value = false
    if (res.interviewer_message) {
      messages.value.push(res.interviewer_message)
    }
    if (res.session_finished) {
      finished.value = true
      // 自然结束时后端已生成报告，直接记录 report_id
      if (res.report_id) {
        finishedReportId.value = res.report_id
      }
    }
    scrollToBottom()
  } catch (e) {
    typing.value = false
  } finally {
    sending.value = false
  }
}

// ============ 语音录音 & 识别 ============

async function startRecording() {
  if (recording.value || recognizing.value || finished.value || sending.value) return

  try {
    // 请求麦克风权限
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        sampleSize: 16,
      },
    })

    // 选择 MIME type（优先 webm/wav 兼容）
    let mimeType = 'audio/webm'
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus'
    }

    mediaRecorder = new MediaRecorder(audioStream, { mimeType })
    audioChunks = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunks.push(e.data)
      }
    }

    mediaRecorder.onstop = handleRecordingStop

    mediaRecorder.start()
    recording.value = true
    recordingElapsed.value = 0
    recordingTimerHandle = setInterval(() => {
      recordingElapsed.value += 1
      // 最长录音 60 秒自动停止
      if (recordingElapsed.value >= 60) {
        stopRecording()
      }
    }, 1000)
  } catch (err) {
    console.error('麦克风访问失败:', err)
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      message.error('麦克风权限被拒绝，请在浏览器设置中允许麦克风访问')
    } else if (err.name === 'NotFoundError') {
      message.error('未检测到麦克风设备')
    } else {
      message.error('录音启动失败：' + (err.message || err.name))
    }
  }
}

async function stopRecording() {
  if (!recording.value) return

  recording.value = false
  if (recordingTimerHandle) {
    clearInterval(recordingTimerHandle)
    recordingTimerHandle = null
  }

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }

  // 停止麦克风轨道
  if (audioStream) {
    audioStream.getTracks().forEach((t) => t.stop())
    audioStream = null
  }
}

async function handleRecordingStop() {
  if (audioChunks.length === 0) return

  const audioBlob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
  audioChunks = []

  if (audioBlob.size < 500) {
    // 录音太短
    return
  }

  recognizing.value = true
  try {
    // 浏览器录音是 webm/opus，百度 ASR 不支持，先转成 16kHz 单声道 WAV
    const wavBlob = await convertToWav(audioBlob, 16000)
    const result = await asrApi.transcribe(wavBlob, 'wav', 16000)
    if (result && result.text) {
      // 追加到输入框（保留用户可能已输入的内容）
      draft.value = draft.value ? `${draft.value} ${result.text}` : result.text
      message.success('语音识别成功')
    } else {
      message.warning('未能识别出语音内容，请再试一次')
    }
  } catch (err) {
    console.error('ASR 识别失败:', err)
    // 后端返回的具体错误信息
    const detail = err?.response?.data?.detail || ''
    if (err?.response?.status === 503) {
      message.error(detail || '语音识别服务不可用，请检查后端配置')
    } else if (err?.response?.status === 500) {
      message.error('语音识别服务出错：' + detail)
    } else {
      message.error('语音识别失败，请检查网络或稍后重试')
    }
  } finally {
    recognizing.value = false
  }
}

function confirmEnd() {
  Modal.confirm({
    title: '提前结束面试？',
    content: '结束后将根据当前回答生成诊断报告。',
    okText: '结束面试',
    cancelText: '继续面试',
    onOk: endInterview,
  })
}

async function endInterview() {
  ending.value = true
  try {
    const res = await interviewApi.end(sessionId)
    finished.value = true
    router.push(`/reports/${res.report_id}`)
  } catch (e) {
    // 拦截器已提示
  } finally {
    ending.value = false
  }
}

async function goReport() {
  ending.value = true
  try {
    // 自然结束时已有 report_id，直接跳转；否则调用 end 接口（幂等，会补生成报告）
    if (finishedReportId.value) {
      router.push(`/reports/${finishedReportId.value}`)
      return
    }
    const res = await interviewApi.end(sessionId).catch(() => null)
    if (res?.report_id) {
      router.push(`/reports/${res.report_id}`)
    } else {
      router.push('/reports')
    }
  } finally {
    ending.value = false
  }
}

function backHome() {
  if (finished.value) {
    router.push('/reports')
  } else {
    confirmEnd()
  }
}

onMounted(load)
onBeforeUnmount(() => {
  if (timerHandle) clearInterval(timerHandle)
  if (recordingTimerHandle) clearInterval(recordingTimerHandle)
  // 确保离开页面时关闭麦克风
  if (audioStream) {
    audioStream.getTracks().forEach((t) => t.stop())
  }
})
</script>

<style scoped>
.room {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.room-header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}
.room-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.room-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-left: 8px;
}
.room-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.room-sub {
  font-size: 12px;
  color: #6b7280;
}
.room-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.timer {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.timer.warn {
  color: var(--red);
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
.center-hint {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
  font-size: 14px;
}
.msg-row {
  display: flex;
}
.msg-row.interviewer {
  justify-content: flex-start;
}
.msg-row.candidate {
  justify-content: flex-end;
}
.bubble {
  max-width: 72%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
}
.msg-row.interviewer .bubble {
  background: #fff;
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}
.msg-row.candidate .bubble {
  background: var(--brand);
  color: #fff;
  border-top-right-radius: 4px;
}
.bubble-role {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
  opacity: 0.7;
}
.bubble-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble.typing {
  color: #9ca3af;
}
.finished-hint {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px;
}
.finished-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.finished-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 6px;
}
.finished-desc {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 16px;
}
.input-bar {
  border-top: 1px solid var(--border);
  background: #fff;
  padding: 16px 24px;
  flex-shrink: 0;
  max-width: 820px;
  width: 100%;
  margin: 0 auto;
}
.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.input-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.input-hint {
  font-size: 12px;
  color: #9ca3af;
}
.recording-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #ef4444;
  margin-bottom: 6px;
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}
.recognizing-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #3b82f6;
  margin-bottom: 6px;
}
</style>
