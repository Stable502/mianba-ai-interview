-- =====================================================================
-- AI 模拟面试助手 数据库设计 v1.1（含全链路种子数据）
-- 依据: 需求文档-AI模拟面试助手.md (PRD v0.1)
-- 方言: MySQL 8.0 / InnoDB / utf8mb4
-- 命名: 蛇形命名, 表名复数, 主键统一 id BIGINT
-- =====================================================================

-- 重复执行安全: 先删除旧库再重建, 保证脚本可整体重跑(演示数据, 无生产风险)
DROP DATABASE IF EXISTS interview_ai;
CREATE DATABASE IF NOT EXISTS interview_ai DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE interview_ai;
-- 固定连接字符集, 防止 Windows cmd 客户端默认 GBK 导致中文乱码/插入失败
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 1. 账户与会员域
-- ---------------------------------------------------------------------

-- 用户
CREATE TABLE users (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone         VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
  email         VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
  wechat_openid VARCHAR(64)  DEFAULT NULL COMMENT '微信 openid',
  password_hash VARCHAR(255) DEFAULT NULL COMMENT '第三方登录可空',
  nickname      VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '昵称',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '1正常 2封禁',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at    DATETIME     DEFAULT NULL COMMENT '软删, 触发敏感数据清理',
  UNIQUE KEY uk_phone (phone),
  UNIQUE KEY uk_email (email),
  UNIQUE KEY uk_wechat (wechat_openid)
) COMMENT='用户表';

-- 订阅计划(会员档位)
CREATE TABLE plans (
  id                     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code                   VARCHAR(32)  NOT NULL COMMENT 'free/monthly/quarterly/yearly',
  name                   VARCHAR(64)  NOT NULL COMMENT '展示名',
  price_cents            INT          NOT NULL DEFAULT 0 COMMENT '分',
  period_days            INT          NOT NULL DEFAULT 0 COMMENT '0=免费档',
  max_interviews_month   INT          DEFAULT NULL COMMENT '每月面试次数上限, NULL=无限',
  full_report_enabled    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否含完整诊断报告',
  pdf_export_enabled     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否可导出PDF',
  persona_premium        TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否解锁全部面试官风格',
  is_active              TINYINT(1)   NOT NULL DEFAULT 1,
  created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_code (code)
) COMMENT='订阅计划';

-- 会员记录(用户当前/历史订阅)
CREATE TABLE memberships (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id       BIGINT UNSIGNED NOT NULL,
  plan_id       BIGINT UNSIGNED NOT NULL,
  status        TINYINT NOT NULL DEFAULT 1 COMMENT '1生效 2已过期 3已退订',
  started_at    DATETIME NOT NULL,
  expired_at    DATETIME NOT NULL,
  auto_renew    TINYINT(1) NOT NULL DEFAULT 0 COMMENT '自动续费(合规需显著告知)',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user (user_id, status),
  CONSTRAINT fk_member_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_member_plan FOREIGN KEY (plan_id) REFERENCES plans(id)
) COMMENT='会员记录';

-- 订阅订单
CREATE TABLE orders (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_no    VARCHAR(40)  NOT NULL,
  user_id     BIGINT UNSIGNED NOT NULL,
  plan_id     BIGINT UNSIGNED NOT NULL,
  amount_cents INT         NOT NULL,
  status      TINYINT      NOT NULL DEFAULT 1 COMMENT '1待支付 2已支付 3已退款 4已关闭',
  channel     VARCHAR(20)  DEFAULT NULL COMMENT 'wechat/alipay',
  paid_at     DATETIME     DEFAULT NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_order_no (order_no),
  KEY idx_user (user_id),
  CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_order_plan FOREIGN KEY (plan_id) REFERENCES plans(id)
) COMMENT='订单';

-- 月度面试额度(免费+会员统一核算)
CREATE TABLE usage_quotas (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  period      CHAR(7)       NOT NULL COMMENT '结算月, 如 2026-09',
  quota_limit INT           NOT NULL COMMENT '当月上限, 由当月生效计划决定',
  quota_used  INT           NOT NULL DEFAULT 0,
  updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_period (user_id, period),
  CONSTRAINT fk_quota_user FOREIGN KEY (user_id) REFERENCES users(id)
) COMMENT='月度面试额度';

-- ---------------------------------------------------------------------
-- 2. 面试准备域
-- ---------------------------------------------------------------------

-- 简历(支持多版本)
CREATE TABLE resumes (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  title       VARCHAR(128) NOT NULL COMMENT '版本名, 如"后端方向-2026"',
  file_url    VARCHAR(512) DEFAULT NULL COMMENT '原始文件存储地址',
  raw_text    MEDIUMTEXT   COMMENT '解析出的纯文本',
  parsed_json JSON         DEFAULT NULL COMMENT '结构化解析结果(冗余快照, 明细在 experiences)',
  is_default  TINYINT(1)   NOT NULL DEFAULT 0,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user (user_id),
  CONSTRAINT fk_resume_user FOREIGN KEY (user_id) REFERENCES users(id)
) COMMENT='简历';

-- 简历结构化经历(供出题引擎深挖)
CREATE TABLE resume_experiences (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  resume_id    BIGINT UNSIGNED NOT NULL,
  exp_type     VARCHAR(16) NOT NULL COMMENT 'work/project/education',
  company      VARCHAR(128) DEFAULT NULL,
  title        VARCHAR(128) DEFAULT NULL COMMENT '职位/角色',
  start_date   DATE DEFAULT NULL,
  end_date     DATE DEFAULT NULL COMMENT 'NULL=至今',
  tech_stack   JSON DEFAULT NULL COMMENT '技术栈数组',
  description  TEXT COMMENT '经历描述',
  highlights   JSON DEFAULT NULL COMMENT '量化亮点数组, 如 QPS提升3倍',
  sort_order   INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_exp_resume FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
  KEY idx_resume (resume_id)
) COMMENT='简历结构化经历';

-- 目标岗位 JD
CREATE TABLE job_positions (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id        BIGINT UNSIGNED NOT NULL,
  company_name   VARCHAR(128) DEFAULT NULL,
  position_title VARCHAR(128) NOT NULL,
  jd_text        MEDIUMTEXT   NOT NULL COMMENT 'JD原文',
  parsed_requirements JSON DEFAULT NULL COMMENT '解析出的职责/要求/软素质条目',
  job_category   VARCHAR(32)  DEFAULT NULL COMMENT '岗位大类, 如 backend/product',
  source         VARCHAR(16)  NOT NULL DEFAULT 'paste' COMMENT 'paste/link',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user (user_id),
  CONSTRAINT fk_position_user FOREIGN KEY (user_id) REFERENCES users(id)
) COMMENT='目标岗位';

-- 面试官人设(多风格)
CREATE TABLE interviewer_personas (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code            VARCHAR(32)  NOT NULL COMMENT 'coach/pressure/bigtech/fast',
  name            VARCHAR(64)  NOT NULL,
  description     VARCHAR(255) NOT NULL,
  prompt_template TEXT         NOT NULL COMMENT 'System Prompt 模板',
  voice_config    JSON         DEFAULT NULL COMMENT 'TTS音色/语速配置',
  is_premium      TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '会员专属风格',
  is_active       TINYINT(1)   NOT NULL DEFAULT 1,
  UNIQUE KEY uk_code (code)
) COMMENT='面试官人设';

-- ---------------------------------------------------------------------
-- 3. 面试会话域(实时面试间)
-- ---------------------------------------------------------------------

-- 面试会话(一次完整模拟面试)
CREATE TABLE interview_sessions (
  id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_no       VARCHAR(40)  NOT NULL COMMENT '业务单号',
  user_id          BIGINT UNSIGNED NOT NULL,
  resume_id        BIGINT UNSIGNED DEFAULT NULL COMMENT '可空: 支持无简历快捷练习',
  job_position_id  BIGINT UNSIGNED DEFAULT NULL COMMENT '可空: 支持无JD通用练习',
  persona_id       BIGINT UNSIGNED NOT NULL,
  interview_type   VARCHAR(16)  NOT NULL COMMENT 'tech/behavioral/case/hr',
  difficulty       VARCHAR(16)  NOT NULL DEFAULT 'mid' COMMENT '对标职级',
  planned_minutes  INT          NOT NULL DEFAULT 30,
  status           TINYINT      NOT NULL DEFAULT 1 COMMENT '1已预约待开始 2进行中 3正常结束 4用户提前结束 5中断',
  started_at       DATETIME     DEFAULT NULL,
  ended_at         DATETIME     DEFAULT NULL,
  overall_score    DECIMAL(4,1) DEFAULT NULL COMMENT '综合评分1-5, 由报告回填',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_session_no (session_no),
  KEY idx_user_status (user_id, status),
  CONSTRAINT fk_session_user     FOREIGN KEY (user_id)         REFERENCES users(id),
  CONSTRAINT fk_session_resume   FOREIGN KEY (resume_id)       REFERENCES resumes(id),
  CONSTRAINT fk_session_position FOREIGN KEY (job_position_id) REFERENCES job_positions(id),
  CONSTRAINT fk_session_persona  FOREIGN KEY (persona_id)      REFERENCES interviewer_personas(id)
) COMMENT='面试会话';

-- 会话题目(含追问链: parent_question_id 指向被追问的题)
CREATE TABLE interview_questions (
  id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id         BIGINT UNSIGNED NOT NULL,
  parent_question_id BIGINT UNSIGNED DEFAULT NULL COMMENT '追问指向的上一题, 顶层题为NULL',
  seq_no             INT    NOT NULL COMMENT '题目在会话中的顺序',
  question_type      VARCHAR(16) NOT NULL COMMENT 'opening/main/followup/closing',
  question_text      TEXT   NOT NULL,
  source             VARCHAR(16) NOT NULL COMMENT 'resume/jd/bank/mixed',
  bank_question_id   BIGINT UNSIGNED DEFAULT NULL COMMENT '来自通用题库时回链',
  target_dimension   VARCHAR(32) DEFAULT NULL COMMENT '考察维度, 如 project_depth',
  asked_at           DATETIME DEFAULT NULL,
  CONSTRAINT fk_q_session FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_q_parent  FOREIGN KEY (parent_question_id) REFERENCES interview_questions(id),
  KEY idx_session_seq (session_id, seq_no)
) COMMENT='会话题目';

-- 对话消息(语音转写+录音, 实时字幕与回放数据源)
CREATE TABLE interview_messages (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id      BIGINT UNSIGNED NOT NULL,
  question_id     BIGINT UNSIGNED DEFAULT NULL COMMENT '归属题目; 寒暄/收尾等非题目消息为NULL',
  role            VARCHAR(16) NOT NULL COMMENT 'interviewer/candidate',
  content_text    MEDIUMTEXT COMMENT 'ASR转写或面试官台词',
  audio_url       VARCHAR(512) DEFAULT NULL COMMENT '录音/合成音频存储地址',
  asr_confidence  DECIMAL(4,3) DEFAULT NULL COMMENT '识别置信度, 低置信提示手动修正',
  duration_ms     INT DEFAULT NULL,
  is_interrupted  TINYINT(1) NOT NULL DEFAULT 0 COMMENT '该面试官消息是否被用户打断',
  manual_revised  TINYINT(1) NOT NULL DEFAULT 0 COMMENT '用户是否手动修正过转写',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_msg_session  FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_msg_question FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE SET NULL,
  KEY idx_session_time (session_id, created_at)
) COMMENT='对话消息';

-- ---------------------------------------------------------------------
-- 4. 诊断报告域
-- ---------------------------------------------------------------------

-- 逐题评估(四维评分+点评+话术改进)
CREATE TABLE question_evaluations (
  id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id          BIGINT UNSIGNED NOT NULL,
  question_id         BIGINT UNSIGNED NOT NULL,
  content_score       DECIMAL(3,1) DEFAULT NULL COMMENT '内容质量1-5',
  logic_score         DECIMAL(3,1) DEFAULT NULL COMMENT '表达逻辑1-5',
  match_score         DECIMAL(3,1) DEFAULT NULL COMMENT '岗位匹配度1-5',
  delivery_score      DECIMAL(3,1) DEFAULT NULL COMMENT '沟通气场1-5',
  comment             MEDIUMTEXT COMMENT 'AI点评',
  improved_answer     MEDIUMTEXT COMMENT '改进后话术示范(修改前/后)',
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_question (question_id),
  CONSTRAINT fk_eval_session  FOREIGN KEY (session_id)  REFERENCES interview_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_eval_question FOREIGN KEY (question_id) REFERENCES interview_questions(id) ON DELETE CASCADE
) COMMENT='逐题评估';

-- 面试诊断报告(与会话一对一)
CREATE TABLE interview_reports (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id     BIGINT UNSIGNED NOT NULL,
  user_id        BIGINT UNSIGNED NOT NULL,
  is_full        TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1完整版(会员) 0简版(免费)',
  overall_score  DECIMAL(4,1) NOT NULL COMMENT '综合评分',
  strengths      JSON DEFAULT NULL COMMENT '优势项数组',
  weaknesses     JSON DEFAULT NULL COMMENT '短板项数组',
  jd_match       JSON DEFAULT NULL COMMENT 'JD要求逐条对照结果',
  summary        MEDIUMTEXT COMMENT '总评',
  pdf_url        VARCHAR(512) DEFAULT NULL COMMENT '导出PDF地址',
  generated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_session (session_id),
  KEY idx_user (user_id, generated_at),
  CONSTRAINT fk_report_session FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_report_user   FOREIGN KEY (user_id)   REFERENCES users(id)
) COMMENT='面试诊断报告';

-- ---------------------------------------------------------------------
-- 5. 题库域
-- ---------------------------------------------------------------------

-- 通用题库(兜底题源, 去重统计)
CREATE TABLE question_bank (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  interview_type  VARCHAR(16) NOT NULL COMMENT 'tech/behavioral/case/hr',
  job_category    VARCHAR(32) NOT NULL COMMENT '岗位大类',
  difficulty      VARCHAR(16) NOT NULL DEFAULT 'mid',
  question_text   TEXT NOT NULL,
  tags            JSON DEFAULT NULL,
  usage_count     INT NOT NULL DEFAULT 0 COMMENT '被引用次数, 支撑去重与热度',
  is_active       TINYINT(1) NOT NULL DEFAULT 1,
  KEY idx_type_cat_diff (interview_type, job_category, difficulty)
) COMMENT='通用题库';

-- 用户出题去重记录(同一用户多次练习不重复出题)
CREATE TABLE user_question_history (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id         BIGINT UNSIGNED NOT NULL,
  bank_question_id BIGINT UNSIGNED NOT NULL,
  session_id      BIGINT UNSIGNED NOT NULL COMMENT '出现在的会话',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_bank (user_id, bank_question_id) COMMENT '同用户全局不重复出题',
  CONSTRAINT fk_uqh_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_uqh_bank FOREIGN KEY (bank_question_id) REFERENCES question_bank(id),
  CONSTRAINT fk_uqh_session FOREIGN KEY (session_id) REFERENCES interview_sessions(id) ON DELETE CASCADE
) COMMENT='用户出题历史';

-- ---------------------------------------------------------------------
-- 6. 初始化数据
-- ---------------------------------------------------------------------

INSERT INTO plans (id, code, name, price_cents, period_days, max_interviews_month, full_report_enabled, pdf_export_enabled, persona_premium) VALUES
(1, 'free',      '免费版',   0,      0,   2, 0, 0, 0),
(2, 'monthly',   '月度会员', 3900,   30,  NULL, 1, 1, 1),
(3, 'quarterly', '季度会员', 9900,   90,  NULL, 1, 1, 1),
(4, 'yearly',    '年度会员', 29900,  365, NULL, 1, 1, 1);

INSERT INTO interviewer_personas (id, code, name, description, prompt_template, is_premium) VALUES
(1, 'coach',    '温和教练型', '语气友好, 多给引导和鼓励, 适合建立自信',       '你是一位温和耐心的面试教练，多用引导式提问并给予鼓励。',       0),
(2, 'pressure', '压力挑战型', '高频追问, 质疑回答漏洞, 模拟高压面试',         '你是一位严格挑剔的面试官，会高频追问并质疑回答中的漏洞。',         0),
(3, 'bigtech',  '大厂风格',   '流程严谨, 深挖技术与项目细节, 对标大厂标准',   '你是一位大厂资深面试官，流程严谨，深挖技术细节与项目难点。',   1),
(4, 'fast',     '快节奏',     '语速快、单刀直入, 考验临场反应',               '你是一位雷厉风行的面试官，语速快、提问直接，考验临场反应。',               1);

-- ---------------------------------------------------------------------
-- 7. 业务种子数据（全链路演示, 显式指定 id 保证外键引用）
--    数据故事:
--      张伟(id=1, 免费用户): 2份简历 + 1个目标JD
--        会话1: 行为面·温和教练 09-01 正常结束 → 简版报告 4.3
--        会话2: 技术面·压力挑战 09-03 进行中(演示追问链与低置信修正)
--        9月额度 2/2 已用尽(演示额度拦截场景)
--      李娜(id=2, 年度会员): 无简历无JD快捷练习(演示可空外键场景)
--        会话3: HR面·大厂风格 09-02 正常结束 → 完整版报告 4.6 + PDF
-- ---------------------------------------------------------------------

-- 用户(password_hash 为 123456 的 bcrypt 哈希, 两个账号均可用该密码登录)
INSERT INTO users (id, phone, email, wechat_openid, password_hash, nickname, status, created_at) VALUES
(1, '13800000001', 'zhangwei@example.com', NULL, '$2b$10$/UqbK76kHOgV1TgYqN6RYeyASIPlDmfBsDlKylICypN86s6B5NOl.', '张伟', 1, '2026-08-01 09:30:00'),
(2, '13800000002', 'lina@example.com',     'wx_openid_lina_001', '$2b$10$/UqbK76kHOgV1TgYqN6RYeyASIPlDmfBsDlKylICypN86s6B5NOl.', '李娜', 1, '2026-07-15 20:12:00');

-- 会员记录(李娜年度会员生效中, auto_renew 已合规告知)
INSERT INTO memberships (id, user_id, plan_id, status, started_at, expired_at, auto_renew) VALUES
(1, 2, 4, 1, '2026-08-20 10:15:00', '2027-08-20 10:15:00', 1);

-- 订单(李娜开通年度会员的支付记录)
INSERT INTO orders (id, order_no, user_id, plan_id, amount_cents, status, channel, paid_at) VALUES
(1, 'ORD2026082010150001', 2, 4, 29900, 2, 'wechat', '2026-08-20 10:15:30');

-- 月度额度(会员999=无限; 张伟9月额度已用尽, 演示拦截升级引导)
INSERT INTO usage_quotas (id, user_id, period, quota_limit, quota_used) VALUES
(1, 1, '2026-09', 2,   2),
(2, 2, '2026-09', 999, 1);

-- 简历(张伟两份多版本)
INSERT INTO resumes (id, user_id, title, file_url, parsed_json, is_default) VALUES
(1, 1, '后端开发-最新版', '/storage/resumes/1/backend_v5.pdf', NULL, 1),
(2, 1, '全栈方向-v3',     '/storage/resumes/1/fullstack_v3.docx', NULL, 0);

-- 简历结构化经历(出题引擎深挖素材, 归属简历1)
INSERT INTO resume_experiences (id, resume_id, exp_type, company, title, start_date, end_date, tech_stack, description, highlights, sort_order) VALUES
(1, 1, 'work', 'XX金融科技有限公司', '高级后端开发工程师', '2023-03-01', NULL, '["Go","MySQL","Redis","Kafka"]', '负责支付网关核心链路的设计与稳定性保障, 主导渠道路由模块架构演进', '["故障切换时间 2min降至5s","支撑十万级QPS支付流量"]', 1),
(2, 1, 'project', '支付网关渠道路由重构', '项目负责人(团队4人)', '2024-05-01', '2024-11-30', '["Go","gRPC","Prometheus","etcd"]', '将单机主动探测的人工切换改造为异步健康检查+多活路由的自动切换, 并灰度验证上线', '["全年累计减少约40分钟线上故障时长","方案沉淀为团队标准SOP"]', 2),
(3, 1, 'work', 'YY互联网公司', '后端开发工程师', '2021-06-01', '2023-02-28', '["Java","Spring Cloud","MySQL"]', '参与订单中心与库存服务的开发与性能优化', '["订单接口P99延迟降低60%"]', 3);

-- 目标岗位JD
INSERT INTO job_positions (id, user_id, company_name, position_title, jd_text, parsed_requirements, job_category, source) VALUES
(1, 1, '某头部互联网公司', '高级后端开发工程师', '【高级后端开发工程师·支付方向】岗位职责：1.负责支付网关核心链路的设计、开发与稳定性保障 2.主导高并发(十万级QPS)系统的架构演进与性能优化 3.与产品、运营协作推动业务需求落地。任职要求：1.本科及以上学历, 5年以上后端开发经验 2.精通Go或Java, 深入理解微服务架构与分布式系统 3.熟悉MySQL、Redis、Kafka及其底层原理 4.有支付/交易系统经验者优先 5.良好的沟通协作与抗压能力', '{"responsibilities":["支付网关核心链路设计与稳定性保障","高并发架构演进与性能优化","业务需求协作落地"],"requirements":["5年以上后端经验","精通Go/Java与微服务架构","熟悉MySQL/Redis/Kafka","支付交易经验优先"],"soft":["沟通协作","抗压"]}', 'backend', 'paste'),
(2, 2, '某互联网大厂', '高级产品经理', '【高级产品经理】岗位职责：1.负责B端商业化产品规划与落地 2.基于数据分析驱动产品迭代 3.跨部门协作推动版本交付。任职要求：1.5年以上产品经验 2.有B端商业化经验 3.具备较强的数据分析能力 4.优秀的跨部门沟通能力', '{"responsibilities":["B端商业化产品规划","数据驱动迭代"],"requirements":["5年以上产品经验","B端商业化经验","数据分析能力"],"soft":["跨部门沟通"]}', 'product', 'paste');

-- 通用题库(usage_count与实际被引用次数一致; 必须先于会话题目插入, 满足外键即时检查)
INSERT INTO question_bank (id, interview_type, job_category, difficulty, question_text, tags, usage_count) VALUES
(1, 'tech',       'backend',  'high', 'Redis缓存与数据库一致性有哪些常见方案？各自的适用场景？', '["Redis","缓存一致性","补偿机制"]', 1),
(2, 'tech',       'backend',  'high', '设计一个支持十万级QPS的支付网关, 你会怎么做容量规划与降级预案？', '["系统设计","支付","高并发"]', 0),
(3, 'behavioral', 'general',  'mid',  '说说你离开上一家公司的原因。', '["离职原因","动机"]', 1),
(4, 'behavioral', 'general',  'mid',  '你有什么想问我们的吗？(收尾反问引导)', '["反问环节","收尾"]', 1),
(5, 'hr',         'general',  'mid',  '请用两分钟做一个自我介绍。', '["自我介绍","开场"]', 1),
(6, 'hr',         'general',  'mid',  '你的期望薪资是多少？谈判依据是什么？', '["薪资谈判","期望薪酬"]', 1);

-- 面试会话(3场: 结束/进行中/结束, 覆盖多种状态与快捷练习)
INSERT INTO interview_sessions (id, session_no, user_id, resume_id, job_position_id, persona_id, interview_type, difficulty, planned_minutes, status, started_at, ended_at, overall_score) VALUES
(1, 'SN20260901001', 1, 1, 1, 1, 'behavioral', 'P7', 30, 3, '2026-09-01 14:00:00', '2026-09-01 14:31:00', 4.3),
(2, 'SN20260903002', 1, 1, 1, 2, 'tech',       'P7', 30, 2, '2026-09-03 18:35:00', NULL, NULL),
(3, 'SN20260902003', 2, NULL, 2, 3, 'hr',      'mid', 15, 3, '2026-09-02 21:00:00', '2026-09-02 21:16:00', 4.6);

-- 会话题目(会话1含完整STAR追问链: q3/q4 追问 q2; 会话2含JD出题与题库兜底; 会话3为快捷练习)
INSERT INTO interview_questions (id, session_id, parent_question_id, seq_no, question_type, question_text, source, bank_question_id, target_dimension, asked_at) VALUES
(1, 1, NULL, 1, 'opening',  '你好, 我是今天的面试官林老师。请先做个自我介绍, 重点讲一下支付网关项目中你的角色和贡献。', 'resume', NULL, 'self_intro', '2026-09-01 14:00:30'),
(2, 1, NULL, 2, 'main',     '请完整讲讲支付网关渠道路由重构这个项目：当时的背景、你的任务、解决方案和最终结果。', 'resume', NULL, 'project_depth', '2026-09-01 14:02:10'),
(3, 1, 2,    3, 'followup', '你提到切换时间从2分钟降到5秒, 当时的技术难点是什么？你是怎么定位到瓶颈的？', 'resume', NULL, 'project_depth', '2026-09-01 14:06:20'),
(4, 1, 3,    4, 'followup', '这个方案的结果如何量化？有没有沉淀成团队标准？', 'resume', NULL, 'result_quantify', '2026-09-01 14:12:00'),
(5, 1, NULL, 5, 'main',     '说说你离开上一家公司的原因。', 'bank', 3, 'motivation', '2026-09-01 14:18:00'),
(6, 1, NULL, 6, 'closing',  '最后, 你有什么想问我的吗？', 'bank', 4, 'closing', '2026-09-01 14:26:30'),
(7, 2, NULL, 1, 'opening',  '先自我介绍, 重点讲你最近一年最有挑战的技术工作。', 'resume', NULL, 'self_intro', '2026-09-03 18:35:20'),
(8, 2, NULL, 2, 'main',     '支付网关在十万级QPS下如何保证渠道路由的一致性与可用性？请给出你的架构设计。', 'jd', NULL, 'system_design', '2026-09-03 18:37:10'),
(9, 2, 8,    3, 'followup', '如果Redis缓存与数据库出现不一致, 你的补偿机制怎么设计？', 'bank', 1, 'cache_consistency', '2026-09-03 18:40:05'),
(10, 3, NULL, 1, 'opening', '请用两分钟做一个自我介绍。', 'bank', 5, 'self_intro', '2026-09-02 21:00:30'),
(11, 3, NULL, 2, 'main',    '你的期望薪资是多少？谈判依据是什么？', 'bank', 6, 'salary_negotiation', '2026-09-02 21:04:00');

-- 对话消息(含: 低置信度0.587+手动修正、被打断的面试官消息、非题目收尾消息)
INSERT INTO interview_messages (id, session_id, question_id, role, content_text, audio_url, asr_confidence, duration_ms, is_interrupted, manual_revised, created_at) VALUES
(1, 1, 1, 'interviewer', '你好, 我是今天的面试官林老师。请先做个自我介绍, 重点讲一下支付网关项目中你的角色和贡献。', '/audio/s1/m1.mp3', NULL, 4800, 0, 0, '2026-09-01 14:00:30'),
(2, 1, 1, 'candidate', '我是张伟, 5年后端开发经验, 最近三年在XX金融负责支付网关项目, 担任核心开发, 主导渠道路由重构, 把故障切换时间从2分钟降到5秒以内。', '/audio/s1/m2.mp3', 0.962, 61000, 0, 0, '2026-09-01 14:01:05'),
(3, 1, 2, 'interviewer', '很好。请完整讲讲渠道路由重构这个项目：当时的背景、你的任务、解决方案和最终结果。', '/audio/s1/m3.mp3', NULL, 6300, 0, 0, '2026-09-01 14:02:10'),
(4, 1, 2, 'candidate', '背景是单渠道故障时切换依赖人工, 平均耗时2分钟。我负责整体方案设计, 最终通过异步健康检查加多活路由实现5秒内自动切换。', '/audio/s1/m4.mp3', 0.941, 95000, 0, 0, '2026-09-01 14:03:00'),
(5, 1, 3, 'interviewer', '你提到切换从2分钟降到5秒, 当时的技术难点是什么？你怎么定位到瓶颈的？', '/audio/s1/m5.mp3', NULL, 7100, 0, 0, '2026-09-01 14:06:20'),
(6, 1, 3, 'candidate', '当时切换很慢, 我先加了全链路监控, 发现80%延迟在探测超时, 然后改成异步健康检查和多活路由。', '/audio/s1/m6.mp3', 0.587, 88000, 0, 1, '2026-09-01 14:07:30'),
(7, 1, 4, 'interviewer', '结果如何量化？方案有没有沉淀成团队标准？', '/audio/s1/m7.mp3', NULL, 5900, 0, 0, '2026-09-01 14:12:00'),
(8, 1, 4, 'candidate', '故障恢复从2分钟降到5秒, 全年减少约40分钟线上故障时长, 方案沉淀成了路由切换SOP。', '/audio/s1/m8.mp3', 0.951, 76000, 0, 0, '2026-09-01 14:13:10'),
(9, 1, 5, 'interviewer', '说说你离开上一家公司的原因…', '/audio/s1/m9.mp3', NULL, 8200, 1, 0, '2026-09-01 14:18:00'),
(10, 1, 5, 'candidate', '我离开主要是因为希望深耕支付域的高并发场景, 贵司这个岗位和我的方向非常匹配。', '/audio/s1/m10.mp3', 0.933, 70000, 0, 0, '2026-09-01 14:19:40'),
(11, 1, 6, 'interviewer', '最后, 你有什么想问我的吗？', '/audio/s1/m11.mp3', NULL, 5200, 0, 0, '2026-09-01 14:26:30'),
(12, 1, 6, 'candidate', '想了解一下团队目前支付网关最大的技术挑战是什么？以及新人的成长路径。', '/audio/s1/m12.mp3', 0.958, 45000, 0, 0, '2026-09-01 14:27:40'),
(13, 1, NULL, 'interviewer', '好的, 今天先到这里, 感谢你的时间, 结果一周内会通知你。', '/audio/s1/m13.mp3', NULL, 6400, 0, 0, '2026-09-01 14:30:50'),
(14, 2, 7, 'interviewer', '先自我介绍, 重点讲你最近一年最有挑战的技术工作。', '/audio/s2/m1.mp3', NULL, 5200, 0, 0, '2026-09-03 18:35:20'),
(15, 2, 7, 'candidate', '最近一年最有挑战的是渠道路由的百万级灰度切换, 我设计了分阶段放量与快速回滚机制。', '/audio/s2/m2.mp3', 0.944, 82000, 0, 0, '2026-09-03 18:36:10'),
(16, 2, 8, 'interviewer', '十万级QPS下如何保证路由的一致性与可用性？给出你的架构设计。', '/audio/s2/m3.mp3', NULL, 6800, 0, 0, '2026-09-03 18:37:10'),
(17, 2, 8, 'candidate', '路由配置走etcd多副本加本地快照降级, 一致性通过版本号比对加主动推送保障…', '/audio/s2/m4.mp3', 0.921, 102000, 0, 0, '2026-09-03 18:38:20'),
(18, 2, 9, 'interviewer', '如果Redis缓存与数据库出现不一致, 你的补偿机制怎么设计？', NULL, NULL, 5900, 0, 0, '2026-09-03 18:40:05'),
(19, 3, 10, 'interviewer', '请用两分钟做一个自我介绍。', '/audio/s3/m1.mp3', NULL, 4600, 0, 0, '2026-09-02 21:00:30'),
(20, 3, 10, 'candidate', '我是李娜, 6年产品经验, 主要做B端商业化方向, 目前带3人产品小组。', '/audio/s3/m2.mp3', 0.95, 55000, 0, 0, '2026-09-02 21:01:10'),
(21, 3, 11, 'interviewer', '你的期望薪资是多少？谈判依据是什么？', '/audio/s3/m3.mp3', NULL, 5100, 0, 0, '2026-09-02 21:04:00'),
(22, 3, 11, 'candidate', '期望总包45万, 参考了我目前薪资水平和市场上同级别岗位的薪酬范围。', '/audio/s3/m4.mp3', 0.93, 62000, 0, 0, '2026-09-02 21:06:30'),
(23, 3, NULL, 'interviewer', '好的, 今天的沟通就到这里, 后续HR会和你联系。', '/audio/s3/m5.mp3', NULL, 5800, 0, 0, '2026-09-02 21:15:40');

-- 逐题评估(会话1全部6题, 四维评分与话术改进示范)
INSERT INTO question_evaluations (id, session_id, question_id, content_score, logic_score, match_score, delivery_score, comment, improved_answer) VALUES
(1, 1, 1, 4.0, 4.0, 4.5, 4.0, '整体流畅, 但结构偏流水账, 建议开头用一句话定位身份, 再按STAR展开。', '修改前: 我是张伟, 做过5年开发, 在公司做支付网关, 重构了渠道路由。 修改后: 我是专注支付域的Go后端工程师张伟, 5年经验, 主导支付网关渠道路由重构, 将故障切换从2分钟压缩至5秒。'),
(2, 1, 2, 4.5, 3.5, 4.8, 4.0, '行动描述清楚, 但背景铺垫不足, 面试官追问一次才听到原因, 建议先结论后过程。', '修改后按STAR: 背景-人工切换耗时2分钟, 任务-10秒内自动切换, 行动-监控定位探测超时占80%延迟并设计异步健康检查, 结果-稳定5秒切换。'),
(3, 1, 3, 4.5, 4.0, 4.5, 3.5, '个人贡献边界清晰, 但灰度与演练缺少具体数字(灰度比例、演练次数)。', '修改后: 我们按20%流量分三批灰度, 上线前完成12次故障演练, 每次回滚时间小于30秒。'),
(4, 1, 4, 4.8, 4.5, 4.5, 4.0, '有量化结果, 很好, 但减少40分钟缺少业务影响(对应多少交易损失)。', '修改后: 全年减少40分钟故障时长, 按高峰每分钟约3万交易额估算, 避免损失约1200万元。'),
(5, 1, 5, 4.2, 4.0, 4.0, 3.8, '离职动机表达积极, 但缺少与目标岗位的关联铺垫, 气场略显不足。', '修改后: 我希望在支付高并发场景持续深耕, 贵司的支付网关规模正是我最想挑战的方向。'),
(6, 1, 6, 3.5, 3.5, 3.5, 3.5, '反问准备不足, 问题过于通用, 建议准备2-3个与团队技术挑战相关的具体问题。', '修改后: 想了解当前网关在多活架构上踩过的最大的坑, 以及团队对新人前三个月的期望。');

-- 诊断报告(会话1=免费简版is_full=0, 会话3=会员完整版is_full=1, 总分与会话双写一致)
INSERT INTO interview_reports (id, session_id, user_id, is_full, overall_score, strengths, weaknesses, jd_match, summary, pdf_url, generated_at) VALUES
(1, 1, 1, 0, 4.3, '["技术深度扎实","岗位匹配度高","有真实落地经验"]', '["表达结构松散","缺少量化数据","反问准备不足"]', NULL, '整体表现良好, 技术内容扎实, 支付网关项目经验与目标岗位高度匹配。主要问题是表达缺少结构, 建议练习STAR结构: 先一句结论, 再按背景-任务-行动-结果展开, 行动点附带量化收益。(简版报告, 升级会员可查看逐题回放与JD匹配度)', NULL, '2026-09-01 14:35:00'),
(2, 3, 2, 1, 4.6, '["薪资谈判逻辑清晰","自我介绍定位准确","气场稳定"]', '["B端经验讲述偏少","数据驱动案例不足"]', '[{"requirement":"5年以上产品经验","coverage":"具备6年产品经验, 讲述清晰","status":"covered"},{"requirement":"B端商业化经验","coverage":"仅一笔带过, 未展开案例","status":"partial"},{"requirement":"数据分析能力","coverage":"回答中未体现数据案例","status":"missing"},{"requirement":"跨部门沟通","coverage":"带团队经历佐证充分","status":"covered"}]', '薪资谈判表现优秀, 给价有依据、有锚点。短板在于JD中"数据分析能力"完全未覆盖, 建议下次面试主动准备1-2个数据驱动决策的案例。(完整版报告)', '/storage/reports/2/report_s3.pdf', '2026-09-02 21:18:00');

-- 用户出题去重记录(uk(user_id, bank_question_id)保证同用户不重复出题)
INSERT INTO user_question_history (id, user_id, bank_question_id, session_id) VALUES
(1, 1, 3, 1),
(2, 1, 4, 1),
(3, 1, 1, 2),
(4, 2, 5, 3),
(5, 2, 6, 3);
