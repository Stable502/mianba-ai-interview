<template>
  <div class="create-page">
    <!-- 左侧配置区 -->
    <div class="config-col">
      <div class="card config-card">
        <div class="card-title">1 · 选择面试类型</div>
        <div class="type-grid">
          <div
            v-for="t in interviewTypes"
            :key="t.value"
            class="type-item"
            :class="{ active: form.interview_type === t.value }"
            @click="form.interview_type = t.value"
          >
            <div class="type-icon" :style="{ background: t.soft, color: t.color }">
              <component :is="t.icon" />
            </div>
            <div class="type-name">{{ t.label }}</div>
          </div>
        </div>
      </div>

      <div class="card config-card">
        <div class="card-title">2 · 选择面试官风格</div>
        <div class="persona-grid">
          <div
            v-for="p in personas"
            :key="p.id"
            class="persona-item"
            :class="{ active: form.persona_id === p.id }"
            @click="selectPersona(p)"
          >
            <div class="persona-head">
              <span class="persona-name">{{ p.name }}</span>
              <a-tag v-if="p.is_premium" color="gold">PRO</a-tag>
            </div>
            <div class="persona-desc">{{ p.description }}</div>
          </div>
        </div>
      </div>

      <div class="card config-card">
        <div class="card-title">3 · 面试对象</div>
        <a-form layout="vertical">
          <a-form-item label="目标岗位（JD，可选）">
            <a-select
              v-model:value="form.job_position_id"
              placeholder="选择已保存的岗位 JD"
              allow-clear
              style="width: 100%"
            >
              <a-select-option
                v-for="p in positions"
                :key="p.id"
                :value="p.id"
              >
                {{ p.position_title }}{{ p.company_name ? ' · ' + p.company_name : '' }}
              </a-select-option>
            </a-select>
            <a-button type="link" size="small" style="padding-left: 0" @click="openJdModal">
              + 粘贴新的岗位 JD
            </a-button>
          </a-form-item>

          <a-form-item label="我的简历（可选）">
            <a-select
              v-model:value="form.resume_id"
              placeholder="选择用于定制提问的简历"
              allow-clear
              style="width: 100%"
            >
              <a-select-option v-for="r in resumes" :key="r.id" :value="r.id">
                {{ r.title }}{{ r.is_default ? '（默认）' : '' }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </div>

      <div class="card config-card">
        <div class="card-title">4 · 难度与时长</div>
        <a-form layout="vertical">
          <a-form-item label="对标职级">
            <a-radio-group v-model:value="form.difficulty" button-style="solid">
              <a-radio-button value="easy">初级</a-radio-button>
              <a-radio-button value="mid">中级</a-radio-button>
              <a-radio-button value="hard">高级</a-radio-button>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="面试时长">
            <a-radio-group v-model:value="form.planned_minutes" button-style="solid">
              <a-radio-button :value="15">15 分钟</a-radio-button>
              <a-radio-button :value="30">30 分钟</a-radio-button>
              <a-radio-button :value="45">45 分钟</a-radio-button>
              <a-radio-button :value="60">60 分钟</a-radio-button>
            </a-radio-group>
          </a-form-item>
        </a-form>
      </div>

      <a-button type="primary" size="large" block class="start-btn" :loading="creating" @click="startInterview">
        开始面试
      </a-button>
    </div>

    <!-- 右侧方案预览区 -->
    <div class="preview-col">
      <div class="card preview-card">
        <div class="preview-head">
          <div class="preview-title">面试方案预览</div>
          <a-button v-if="!plan" type="primary" ghost size="small" :loading="previewing" @click="preview">
            生成预览
          </a-button>
        </div>

        <div v-if="!plan" class="preview-empty">
          <div class="preview-empty-icon">📋</div>
          <div>完成左侧配置后，点击「生成预览」查看考察重点与流程</div>
        </div>

        <template v-else>
          <div class="preview-section">
            <div class="preview-label">预计题量</div>
            <div class="preview-count">{{ plan.question_count_range }}</div>
          </div>
          <div class="preview-section">
            <div class="preview-label">考察重点</div>
            <div class="focus-tags">
              <a-tag v-for="(f, i) in plan.focus_points" :key="i" color="blue">{{ f }}</a-tag>
            </div>
          </div>
          <div class="preview-section">
            <div class="preview-label">面试流程</div>
            <div class="timeline">
              <div v-for="(t, i) in plan.timeline" :key="i" class="timeline-item">
                <div class="timeline-dot"></div>
                <div>
                  <div class="timeline-time">{{ t.time }}</div>
                  <div class="timeline-title">{{ t.title }}</div>
                  <div class="timeline-desc">{{ t.desc }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 粘贴 JD 弹窗 -->
    <a-modal v-model:open="jdModalOpen" title="粘贴岗位 JD" :footer="null" width="560">
      <a-form layout="vertical" @finish="saveJd">
        <a-form-item label="岗位名称" name="position_title" :rules="[{ required: true, message: '请输入岗位名称' }]">
          <a-input v-model:value="jdForm.position_title" placeholder="如：高级后端工程师" />
        </a-form-item>
        <a-form-item label="公司名称（选填）" name="company_name">
          <a-input v-model:value="jdForm.company_name" placeholder="如：字节跳动" />
        </a-form-item>
        <a-form-item label="JD 原文" name="jd_text" :rules="[{ required: true, message: '请粘贴 JD 原文' }]">
          <a-textarea v-model:value="jdForm.jd_text" :rows="6" placeholder="粘贴岗位职责与任职要求…" />
        </a-form-item>
        <a-button type="primary" html-type="submit" block :loading="savingJd">保存并选中</a-button>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  CodeOutlined,
  CommentOutlined,
  PieChartOutlined,
  TeamOutlined,
  AimOutlined,
} from '@ant-design/icons-vue'
import { interviewApi } from '@/api/interview'
import { positionApi, personaApi } from '@/api/position'
import { resumeApi } from '@/api/resume'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const interviewTypes = [
  { value: 'tech', label: '技术岗专业面', icon: CodeOutlined, color: '#3B5BFF', soft: '#EEF4FF' },
  { value: 'behavioral', label: '行为面·综合面', icon: CommentOutlined, color: '#16A34A', soft: '#E6F7EE' },
  { value: 'case', label: '案例面·管理面', icon: PieChartOutlined, color: '#8B5CF6', soft: '#F3EEFF' },
  { value: 'hr', label: 'HR面·薪资谈判', icon: TeamOutlined, color: '#D97706', soft: '#FFF3E0' },
]

const form = reactive({
  interview_type: 'tech',
  persona_id: null,
  resume_id: null,
  job_position_id: null,
  difficulty: 'mid',
  planned_minutes: 30,
})

const personas = ref([])
const positions = ref([])
const resumes = ref([])
const plan = ref(null)
const previewing = ref(false)
const creating = ref(false)

const jdModalOpen = ref(false)
const savingJd = ref(false)
const jdForm = reactive({ position_title: '', company_name: '', jd_text: '' })

function selectPersona(p) {
  if (p.is_premium && !userStore.isMember) {
    message.info('该风格为会员专属，请先升级会员')
    return
  }
  form.persona_id = p.id
}

async function loadOptions() {
  const [p, pos, res] = await Promise.all([
    personaApi.list(),
    positionApi.list(),
    resumeApi.list(),
  ])
  personas.value = p
  positions.value = pos
  resumes.value = res
  if (p.length) {
    const firstFree = p.find((x) => !x.is_premium) || p[0]
    form.persona_id = firstFree.id
  }
}

async function preview() {
  if (!form.persona_id) {
    message.warning('请先选择面试官风格')
    return
  }
  previewing.value = true
  try {
    plan.value = await interviewApi.preview(buildPayload())
  } catch (e) {
    // 拦截器已提示
  } finally {
    previewing.value = false
  }
}

function buildPayload() {
  return {
    resume_id: form.resume_id || null,
    job_position_id: form.job_position_id || null,
    persona_id: form.persona_id,
    interview_type: form.interview_type,
    difficulty: form.difficulty,
    planned_minutes: form.planned_minutes,
  }
}

async function startInterview() {
  if (!form.persona_id) {
    message.warning('请先选择面试官风格')
    return
  }
  creating.value = true
  try {
    const res = await interviewApi.create(buildPayload())
    message.success('面试已创建，进入面试间')
    router.push(`/interview/${res.session.id}`)
  } catch (e) {
    // 拦截器已提示
  } finally {
    creating.value = false
  }
}

function openJdModal() {
  Object.assign(jdForm, { position_title: '', company_name: '', jd_text: '' })
  jdModalOpen.value = true
}

async function saveJd() {
  savingJd.value = true
  try {
    const pos = await positionApi.create({
      position_title: jdForm.position_title,
      company_name: jdForm.company_name || null,
      jd_text: jdForm.jd_text,
    })
    positions.value.unshift(pos)
    form.job_position_id = pos.id
    jdModalOpen.value = false
    message.success('岗位 JD 已保存')
  } catch (e) {
    // 拦截器已提示
  } finally {
    savingJd.value = false
  }
}

onMounted(async () => {
  await loadOptions()
  // 支持从报告页"针对本类题型再练一轮"跳转：预选面试类型
  const qType = route.query.type
  if (qType && interviewTypes.some((t) => t.value === qType)) {
    form.interview_type = qType
  }
  if (route.query.focus === 'retrain') {
    message.info('已为你预选薄弱题型，开始针对性训练吧')
  }
})
</script>

<style scoped>
.create-page {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 20px;
  align-items: start;
}
.config-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.config-card {
  padding: 20px;
}
.card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 16px;
}
.type-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.type-item {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s;
}
.type-item:hover {
  border-color: var(--brand);
}
.type-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.type-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin: 0 auto 8px;
}
.type-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.persona-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.persona-item {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.persona-item:hover {
  border-color: var(--brand);
}
.persona-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
}
.persona-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.persona-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}
.persona-desc {
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}
.start-btn {
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 10px;
}
.preview-col {
  position: sticky;
  top: 0;
}
.preview-card {
  padding: 24px;
}
.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.preview-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
}
.preview-empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 20px;
  font-size: 13px;
}
.preview-empty-icon {
  font-size: 36px;
  margin-bottom: 12px;
}
.preview-section {
  margin-bottom: 20px;
}
.preview-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 10px;
}
.preview-count {
  font-size: 22px;
  font-weight: 700;
  color: var(--brand);
}
.focus-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.timeline-item {
  display: flex;
  gap: 12px;
}
.timeline-dot {
  width: 10px;
  height: 10px;
  background: var(--brand);
  border-radius: 5px;
  margin-top: 5px;
  flex-shrink: 0;
}
.timeline-time {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
}
.timeline-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.timeline-desc {
  font-size: 12px;
  color: #6b7280;
}
</style>
