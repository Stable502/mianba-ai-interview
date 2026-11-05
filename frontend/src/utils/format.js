// 面试类型中文映射
export const INTERVIEW_TYPES = {
  tech: '技术岗专业面',
  behavioral: '行为面·综合面',
  case: '案例面·管理面',
  hr: 'HR面·薪资谈判',
}

export const INTERVIEW_TYPE_SHORT = {
  tech: '技术面',
  behavioral: '行为面',
  case: '案例面',
  hr: 'HR面',
}

export function typeName(type) {
  return INTERVIEW_TYPES[type] || type || '综合'
}

export function typeShort(type) {
  return INTERVIEW_TYPE_SHORT[type] || type || '综合'
}

export function typeColor(type) {
  const map = { tech: 'blue', behavioral: 'green', case: 'purple', hr: 'orange' }
  return map[type] || 'blue'
}

// 分数评级
export function scoreRate(score) {
  if (score == null) return { label: '—', color: '#9CA3AF' }
  if (score >= 4.5) return { label: '优秀', color: '#16A34A' }
  if (score >= 4.0) return { label: '良好', color: '#3B5BFF' }
  if (score >= 3.0) return { label: '中等', color: '#D97706' }
  return { label: '待提升', color: '#EF4444' }
}

// 会话状态
export const SESSION_STATUS = {
  1: '待开始',
  2: '进行中',
  3: '正常结束',
  4: '提前结束',
  5: '中断',
}

export function sessionStatus(status) {
  return SESSION_STATUS[status] || '未知'
}

// 价格分转元
export function centsToYuan(cents) {
  return (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2)
}
