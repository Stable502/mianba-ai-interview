<template>
  <div v-if="report" class="report-detail">
    <!-- 总分头卡 -->
    <div class="card hero-card">
      <div class="hero-score-block">
        <div class="hero-score" :style="{ color: scoreRate(report.overall_score).color }">
          {{ report.overall_score }}
        </div>
        <div class="hero-score-label" :style="{ color: scoreRate(report.overall_score).color }">
          {{ scoreRate(report.overall_score).label }}
        </div>
      </div>
      <div class="hero-info">
        <div class="hero-tags">
          <a-tag :color="typeColor(report.interview_type)">{{ typeName(report.interview_type) }}</a-tag>
          <a-tag>{{ report.persona_name || '综合' }}</a-tag>
          <a-tag v-if="report.position_title">{{ report.position_title }}</a-tag>
        </div>
        <div class="hero-summary">{{ report.summary }}</div>
        <div class="hero-meta">
          编号 {{ report.session_no }} · {{ report.planned_minutes }} 分钟 · {{ formatTime(report.generated_at) }}
        </div>
      </div>
    </div>

    <!-- 优势 / 短板 -->
    <div class="two-col">
      <div class="card side-card">
        <div class="side-title green">✅ 你的优势</div>
        <ul class="side-list">
          <li v-for="(s, i) in report.strengths || []" :key="i">{{ s }}</li>
        </ul>
      </div>
      <div class="card side-card">
        <div class="side-title orange">⚠️ 待改进</div>
        <ul class="side-list">
          <li v-for="(w, i) in report.weaknesses || []" :key="i">{{ w }}</li>
        </ul>
      </div>
    </div>

    <!-- JD 匹配度 -->
    <div v-if="report.jd_match?.length" class="card section-card">
      <div class="section-title">岗位匹配度</div>
      <a-table
        :data-source="report.jd_match"
        :columns="jdColumns"
        :pagination="false"
        row-key="requirement"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'level'">
            <a-tag :color="levelColor(record.level)">{{ record.level }}</a-tag>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 逐题点评 -->
    <div class="card section-card">
      <div class="section-title">逐题点评</div>
      <div v-if="!report.evaluations?.length" class="text-muted">暂无逐题评估</div>
      <div v-else class="eval-list">
        <div v-for="e in report.evaluations" :key="e.id" class="eval-item">
          <div class="eval-q">
            <a-tag color="blue">Q{{ e.id }}</a-tag>
            <span>{{ e.question_text || '（未记录题目）' }}</span>
          </div>
          <div class="eval-scores">
            <div class="score-chip"><span class="chip-label">内容</span><span>{{ e.content_score ?? '—' }}</span></div>
            <div class="score-chip"><span class="chip-label">逻辑</span><span>{{ e.logic_score ?? '—' }}</span></div>
            <div class="score-chip"><span class="chip-label">匹配</span><span>{{ e.match_score ?? '—' }}</span></div>
            <div class="score-chip"><span class="chip-label">表达</span><span>{{ e.delivery_score ?? '—' }}</span></div>
          </div>
          <!-- 作答分析：答得好 / 欠缺 分段显示 -->
          <div v-if="e.comment" class="eval-analysis">
            <div class="analysis-row good">
              <span class="analysis-tag">✅ 答得好的地方</span>
              <span class="analysis-text">{{ parseAnalysis(e.comment).good }}</span>
            </div>
            <div class="analysis-row weak">
              <span class="analysis-tag">⚠️ 欠缺/待改进</span>
              <span class="analysis-text">{{ parseAnalysis(e.comment).weak }}</span>
            </div>
          </div>
          <!-- 参考标准答案 -->
          <div v-if="e.improved_answer" class="eval-improved">
            <div class="improved-label">💡 参考标准答案</div>
            <div class="improved-text">{{ e.improved_answer }}</div>
            <a-button
              size="small"
              type="primary"
              ghost
              class="retrain-btn"
              @click="retrainByType(report.interview_type)"
            >
              针对本类题型再练一轮
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <div class="back-row">
      <a-button @click="router.push('/reports')">返回列表</a-button>
      <a-button type="primary" @click="router.push('/create')">再练一场</a-button>
    </div>
  </div>
  <div v-else class="card empty-card">{{ loading ? '加载中…' : '报告不存在' }}</div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { reportApi } from '@/api/report'
import { typeName, typeColor, scoreRate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const report = ref(null)
const loading = ref(true)

const jdColumns = [
  { title: '考察项', dataIndex: 'requirement', key: 'requirement' },
  { title: '匹配度', dataIndex: 'level', key: 'level' },
  { title: '差距说明', dataIndex: 'gap', key: 'gap' },
]

function levelColor(level) {
  if (level === '匹配') return 'green'
  if (level === '部分匹配') return 'orange'
  return 'red'
}

function formatTime(t) {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

// 从后端 comment 文本中提取"答得好 / 欠缺"两部分
function parseAnalysis(comment) {
  if (!comment) return { good: '', weak: '' }
  // 后端格式示例：
  // ✅ 答得好的地方：xxx
  // ⚠️ 欠缺/待改进：xxx
  let good = ''
  let weak = ''
  const lines = comment.split(/\n/)
  for (const line of lines) {
    const l = line.trim()
    // 去掉开头的 emoji 和空白字符
    const stripped = l.replace(/^[\p{Extended_Pictographic}\p{Emoji}\s]+/u, '')
    if (stripped.includes('答得好')) {
      // 找第一个冒号后的内容
      const idx = stripped.indexOf('：')
      const idx2 = stripped.indexOf(':')
      const colonIdx = idx >= 0 ? idx : idx2
      good = colonIdx >= 0 ? stripped.slice(colonIdx + 1).trim() : stripped
    } else if (stripped.includes('欠缺') || stripped.includes('待改进')) {
      const idx = stripped.indexOf('：')
      const idx2 = stripped.indexOf(':')
      const colonIdx = idx >= 0 ? idx : idx2
      weak = colonIdx >= 0 ? stripped.slice(colonIdx + 1).trim() : stripped
    }
  }
  // 如果没有明确标记，则整段视为 weak
  if (!good && !weak) {
    weak = comment.trim()
  }
  return { good, weak }
}

// 跳转到创建面试页，预填面试类型
function retrainByType(type) {
  router.push({ path: '/create', query: { type: type || '' } })
}

onMounted(async () => {
  loading.value = true
  try {
    report.value = await reportApi.get(Number(route.params.id))
  } catch (e) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.report-detail {
  max-width: 980px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.hero-card {
  padding: 28px;
  display: flex;
  gap: 28px;
  align-items: center;
}
.hero-score-block {
  text-align: center;
  flex-shrink: 0;
  width: 140px;
}
.hero-score {
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
}
.hero-score-label {
  font-size: 15px;
  font-weight: 700;
  margin-top: 6px;
}
.hero-info {
  flex: 1;
}
.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.hero-summary {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text);
  margin-bottom: 12px;
}
.hero-meta {
  font-size: 12px;
  color: #9ca3af;
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.side-card {
  padding: 20px;
}
.side-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}
.side-title.green {
  color: var(--green);
}
.side-title.orange {
  color: var(--orange);
}
.side-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 4px;
}
.side-list li {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
  padding-left: 14px;
  position: relative;
}
.side-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  width: 6px;
  height: 6px;
  border-radius: 3px;
  background: var(--brand);
}
.section-card {
  padding: 24px;
}
.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 16px;
}
.eval-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.eval-item {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 16px;
}
.eval-q {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.6;
  margin-bottom: 12px;
}
.eval-scores {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.score-chip {
  background: var(--brand-soft);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--brand);
  display: flex;
  gap: 6px;
}
.chip-label {
  font-weight: 500;
  opacity: 0.7;
}
.eval-comment {
  font-size: 13px;
  color: var(--text);
  line-height: 1.7;
}
.eval-analysis {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.analysis-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border-radius: 8px;
  padding: 10px 12px;
}
.analysis-row.good {
  background: var(--green-soft);
}
.analysis-row.weak {
  background: #fff7ed;
}
.analysis-tag {
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
  padding-top: 1px;
}
.analysis-row.good .analysis-tag {
  color: var(--green);
}
.analysis-row.weak .analysis-tag {
  color: #ea580c;
}
.analysis-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
}
.eval-improved {
  margin-top: 12px;
  background: var(--green-soft);
  border-radius: 8px;
  padding: 12px;
}
.improved-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--green);
  margin-bottom: 6px;
}
.improved-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.8;
  white-space: pre-wrap;
}
.retrain-btn {
  margin-top: 10px;
}
.back-row {
  display: flex;
  justify-content: space-between;
}
.empty-card {
  padding: 60px 20px;
  text-align: center;
  color: #9ca3af;
}
</style>
