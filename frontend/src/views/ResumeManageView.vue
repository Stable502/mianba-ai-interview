<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">简历管理</div>
        <div class="page-sub">面试提问会基于你的简历定制，建议完善项目经历与量化成果</div>
      </div>
      <a-button type="primary" size="large" @click="openCreate">
        <template #icon><PlusOutlined /></template>
        新建简历
      </a-button>
    </div>

    <div v-if="loading" class="card empty-card">加载中…</div>
    <div v-else-if="!resumes.length" class="card empty-card">
      <div class="empty-icon">📄</div>
      <div class="empty-title">还没有简历</div>
      <div class="empty-desc">上传或粘贴你的简历，让面试提问更有针对性</div>
      <a-button type="primary" @click="openCreate">创建第一份简历</a-button>
    </div>

    <div v-else class="resume-grid">
      <div v-for="r in resumes" :key="r.id" class="card resume-card">
        <div class="resume-head">
          <div class="resume-title">{{ r.title }}</div>
          <a-tag v-if="r.is_default" color="blue">默认</a-tag>
        </div>
        <div class="resume-meta">
          <span>{{ r.experiences?.length || 0 }} 段经历</span>
          <span>·</span>
          <span>更新于 {{ formatTime(r.created_at) }}</span>
        </div>
        <div v-if="r.experiences?.length" class="resume-exps">
          <div v-for="e in r.experiences.slice(0, 2)" :key="e.id" class="exp-line">
            <a-tag :color="expColor(e.exp_type)">{{ expLabel(e.exp_type) }}</a-tag>
            <span>{{ e.company || e.title || '—' }}</span>
          </div>
        </div>
        <div class="resume-actions">
          <a-button size="small" @click="openEdit(r)">编辑</a-button>
          <a-button v-if="!r.is_default" size="small" @click="setDefault(r)">设为默认</a-button>
          <a-popconfirm title="该简历将移入回收站，7 天后自动清除，确认？" ok-text="移入回收站" cancel-text="取消" @confirm="removeResume(r)">
            <a-button size="small" danger>删除</a-button>
          </a-popconfirm>
        </div>
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? '编辑简历' : '新建简历'"
      width="720"
      :footer="null"
      destroy-on-close
    >
      <a-form layout="vertical" :model="form">
        <a-form-item label="简历版本名" required>
          <a-input v-model:value="form.title" placeholder="如：后端工程师 · 3 年经验" />
        </a-form-item>
        <a-form-item label="简历全文（可选）">
          <a-textarea v-model:value="form.raw_text" :rows="5" placeholder="粘贴简历文本，系统将基于此定制提问…" />
        </a-form-item>

        <div class="exp-head">
          <span class="exp-label">经历 / 项目（可选）</span>
          <a-button type="link" size="small" @click="addExp">+ 添加一段经历</a-button>
        </div>

        <div v-for="(exp, idx) in form.experiences" :key="idx" class="exp-block">
          <div class="exp-block-head">
            <span>经历 {{ idx + 1 }}</span>
            <a-button type="text" size="small" danger @click="removeExp(idx)">移除</a-button>
          </div>
          <a-form-item label="类型">
            <a-radio-group v-model:value="exp.exp_type" button-style="solid" size="small">
              <a-radio-button value="work">工作</a-radio-button>
              <a-radio-button value="project">项目</a-radio-button>
              <a-radio-button value="education">教育</a-radio-button>
            </a-radio-group>
          </a-form-item>
          <div class="exp-row">
            <a-form-item label="公司 / 学校" style="flex: 1">
              <a-input v-model:value="exp.company" placeholder="公司或学校名称" />
            </a-form-item>
            <a-form-item label="职位 / 项目名" style="flex: 1">
              <a-input v-model:value="exp.title" placeholder="职位或项目名" />
            </a-form-item>
          </div>
          <a-form-item label="描述">
            <a-textarea v-model:value="exp.description" :rows="3" placeholder="职责、成果、量化指标…" />
          </a-form-item>
          <div class="exp-row">
            <a-form-item label="技术栈（逗号分隔）" style="flex: 1">
              <a-input v-model:value="exp.tech_stack_text" placeholder="如：Python, FastAPI, MySQL" />
            </a-form-item>
            <a-form-item label="量化亮点（逗号分隔）" style="flex: 1">
              <a-input v-model:value="exp.highlights_text" placeholder="如：接口耗时降低 40%" />
            </a-form-item>
          </div>
        </div>

        <div class="modal-footer">
          <a-button @click="modalOpen = false">取消</a-button>
          <a-button type="primary" :loading="saving" @click="save">保存简历</a-button>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import { resumeApi } from '@/api/resume'

const resumes = ref([])
const loading = ref(true)
const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref(null)

const form = reactive({ title: '', raw_text: '', experiences: [] })

const EXP_LABEL = { work: '工作', project: '项目', education: '教育' }
const EXP_COLOR = { work: 'blue', project: 'purple', education: 'cyan' }

function expLabel(t) {
  return EXP_LABEL[t] || t
}
function expColor(t) {
  return EXP_COLOR[t] || 'default'
}
function formatTime(t) {
  return dayjs(t).format('YYYY-MM-DD')
}

function splitList(s) {
  return (s || '')
    .split(/[,，]/)
    .map((x) => x.trim())
    .filter(Boolean)
}

function addExp() {
  form.experiences.push({
    exp_type: 'work',
    company: '',
    title: '',
    description: '',
    tech_stack_text: '',
    highlights_text: '',
  })
}

function removeExp(idx) {
  form.experiences.splice(idx, 1)
}

function resetForm() {
  form.title = ''
  form.raw_text = ''
  form.experiences = []
}

function openCreate() {
  editingId.value = null
  resetForm()
  modalOpen.value = true
}

function openEdit(r) {
  editingId.value = r.id
  form.title = r.title
  form.raw_text = r.raw_text || ''
  form.experiences = (r.experiences || []).map((e) => ({
    exp_type: e.exp_type || 'work',
    company: e.company || '',
    title: e.title || '',
    description: e.description || '',
    tech_stack_text: (e.tech_stack || []).join(', '),
    highlights_text: (e.highlights || []).join(', '),
  }))
  modalOpen.value = true
}

async function save() {
  if (!form.title.trim()) {
    message.warning('请输入简历版本名')
    return
  }
  const experiences = form.experiences.map((e) => ({
    exp_type: e.exp_type,
    company: e.company || null,
    title: e.title || null,
    description: e.description || null,
    tech_stack: splitList(e.tech_stack_text),
    highlights: splitList(e.highlights_text),
  }))
  saving.value = true
  try {
    if (editingId.value) {
      await resumeApi.update(editingId.value, { title: form.title, raw_text: form.raw_text, experiences })
      message.success('简历已更新')
    } else {
      await resumeApi.create({ title: form.title, raw_text: form.raw_text, experiences })
      message.success('简历已创建')
    }
    modalOpen.value = false
    await load()
  } catch (e) {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

async function setDefault(r) {
  await resumeApi.setDefault(r.id)
  message.success('已设为默认简历')
  await load()
}

async function removeResume(r) {
  await resumeApi.remove(r.id)
  message.success('已移入回收站，7 天内可在回收站恢复')
  await load()
}

async function load() {
  loading.value = true
  try {
    resumes.value = await resumeApi.list()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
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
  padding: 80px 20px;
  text-align: center;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 6px;
}
.empty-desc {
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 16px;
}
.resume-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.resume-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
}
.resume-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.resume-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.resume-meta {
  display: flex;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 14px;
}
.resume-exps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  flex: 1;
}
.exp-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
}
.resume-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}
.exp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.exp-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.exp-block {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}
.exp-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 8px;
}
.exp-row {
  display: flex;
  gap: 12px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
@media (max-width: 1100px) {
  .resume-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
