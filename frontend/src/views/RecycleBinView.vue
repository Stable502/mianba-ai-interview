<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">回收站</div>
        <div class="page-sub">已删除的简历与面试记录保留 {{ retentionDays }} 天，到期自动彻底删除</div>
      </div>
      <a-popconfirm
        title="清空回收站？所有项目将被彻底删除且无法恢复！"
        ok-text="清空"
        cancel-text="取消"
        :ok-button-props="{ danger: true }"
        @confirm="clearAll"
      >
        <a-button danger :disabled="!resumes.length && !reports.length">清空回收站</a-button>
      </a-popconfirm>
    </div>

    <div v-if="loading" class="card empty-card">加载中…</div>

    <a-tabs v-else v-model:activeKey="activeTab">
      <a-tab-pane key="report" :tab="`面试记录 (${reports.length})`">
        <div v-if="!reports.length" class="card empty-card">
          <div class="empty-icon">🗂️</div>
          <div class="empty-title">回收站中没有面试记录</div>
        </div>
        <div v-else class="item-list">
          <div v-for="it in reports" :key="it.id" class="card item-card">
            <div class="item-icon report-icon"><FileTextOutlined /></div>
            <div class="item-main">
              <div class="item-title-row">
                <a-tag :color="typeColor(it.meta?.interview_type)">{{ typeShort(it.meta?.interview_type) }}</a-tag>
                <span class="item-title">{{ it.title }}</span>
                <span v-if="it.meta?.overall_score != null" class="item-score">{{ it.meta.overall_score }} 分</span>
              </div>
              <div class="item-meta">
                删除于 {{ formatTime(it.deleted_at) }} ·
                <span :class="{ urgent: it.days_left <= 1 }">{{ expiryText(it) }}</span>
              </div>
            </div>
            <div class="item-actions">
              <a-button size="small" type="primary" @click="restore(it)">恢复</a-button>
              <a-popconfirm
                title="彻底删除后无法恢复，确认？"
                ok-text="彻底删除"
                cancel-text="取消"
                :ok-button-props="{ danger: true }"
                @confirm="purge(it)"
              >
                <a-button size="small" danger>彻底删除</a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </a-tab-pane>

      <a-tab-pane key="resume" :tab="`简历 (${resumes.length})`">
        <div v-if="!resumes.length" class="card empty-card">
          <div class="empty-icon">📄</div>
          <div class="empty-title">回收站中没有简历</div>
        </div>
        <div v-else class="item-list">
          <div v-for="it in resumes" :key="it.id" class="card item-card">
            <div class="item-icon resume-icon"><IdcardOutlined /></div>
            <div class="item-main">
              <div class="item-title-row">
                <span class="item-title">{{ it.title }}</span>
              </div>
              <div class="item-meta">
                删除于 {{ formatTime(it.deleted_at) }} ·
                <span :class="{ urgent: it.days_left <= 1 }">{{ expiryText(it) }}</span>
              </div>
            </div>
            <div class="item-actions">
              <a-button size="small" type="primary" @click="restore(it)">恢复</a-button>
              <a-popconfirm
                title="彻底删除后无法恢复，确认？"
                ok-text="彻底删除"
                cancel-text="取消"
                :ok-button-props="{ danger: true }"
                @confirm="purge(it)"
              >
                <a-button size="small" danger>彻底删除</a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { FileTextOutlined, IdcardOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import { recycleApi } from '@/api/recycle'
import { typeShort, typeColor } from '@/utils/format'

const loading = ref(true)
const activeTab = ref('report')
const retentionDays = ref(7)
const resumes = ref([])
const reports = ref([])

function formatTime(t) {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function expiryText(it) {
  if (it.days_left <= 0) return '即将自动清除'
  return `${it.days_left} 天后自动清除`
}

async function load() {
  loading.value = true
  try {
    const data = await recycleApi.list()
    retentionDays.value = data.retention_days ?? 7
    resumes.value = data.resumes || []
    reports.value = data.reports || []
  } finally {
    loading.value = false
  }
}

async function restore(it) {
  await recycleApi.restore(it.item_type, it.id)
  message.success(it.item_type === 'resume' ? '简历已恢复' : '面试记录已恢复')
  await load()
}

async function purge(it) {
  await recycleApi.purge(it.item_type, it.id)
  message.success('已彻底删除')
  await load()
}

async function clearAll() {
  await recycleApi.clear()
  message.success('回收站已清空')
  await load()
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}
.page-sub {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.empty-card {
  padding: 60px 20px;
  text-align: center;
}
.empty-icon {
  font-size: 36px;
  margin-bottom: 10px;
}
.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #6b7280;
}
.item-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
}
.item-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.report-icon {
  background: var(--brand-soft);
  color: var(--brand);
}
.resume-icon {
  background: #f0f5ff;
  color: #2f54eb;
}
.item-main {
  flex: 1;
  min-width: 0;
}
.item-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.item-score {
  font-size: 13px;
  font-weight: 700;
  color: var(--brand);
}
.item-meta {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
.item-meta .urgent {
  color: #ef4444;
  font-weight: 600;
}
.item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>
