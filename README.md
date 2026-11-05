# 面霸 AI · AI 模拟面试助手

基于 **简历 × 岗位 JD** 的 AI 模拟面试系统：上传简历、粘贴目标岗位 JD，即可生成个性化面试方案，进行语音/文字多轮模拟面试，并输出包含四维评分、逐题点评与话术示范的诊断报告。

> 个人独立开发项目（2026.09）。从 PRD、数据库建模、前后端开发到联调交付由一人完成；AI 编程助手仅用于样板代码补全与调试辅助。

## 项目亮点

- **大模型对话策略引擎**：LLM 在 `followup` / `next_question` / `closing` 三类意图动作间自主决策，按「背景 → 任务 → 行动 → 结果」逐层追问；15 / 30 / 45 分钟自适应 2 / 3 / 4 道主干题，追问上限 +2，单场稳定输出 8—10 题，内置题目去重。
- **可解释的结构化评分**：四维 rubric（内容质量 / 表达逻辑 / 岗位匹配度 / 沟通气场）+ 强制 JSON schema 校验 + 格式容错，脏数据不入库；报告结论可回溯到具体回答与逐题评分依据。
- **稳定性与降级**：出题 / 追问 / 评分三类大模型能力封装为可替换客户端，未配置 API Key 时自动降级为规则引擎（关键词命中 + 篇幅 + 结构化表达评分），服务不中断；评分并发上限 3、单题失败重试 1 次、无效回答连续 2 次触发升级追问。
- **工程规模**：9 个路由模块 / 39 个 RESTful 接口 / 16 张业务表 / 9 个业务页面；后端 39 个 Python 模块 4,110 行，前端 11 个 Vue 文件 4,283 行。

## 实测效果

自建 40 条人工标注集（20 无效 / 20 有效）与 15 次真实大模型调用评测：

| 指标 | 结果 |
| --- | --- |
| LLM 结构化输出有效率 | 100%（15 / 15） |
| 同一回答重复 5 次评分极差 | ≤ 0.25 分（5 分制） |
| 优质 / 无效回答平均分差 | 3.05 分（4.05 vs 1.0） |
| 无效回答识别准确率 / F1 | 90% / 0.895 |
| 评分端垃圾文本识别准确率 / F1 | 95% / 0.95 |
| 并发 3 批量评分 | 22.38s，较串行 61.96s 加速 2.77× |

评测同时暴露启发式规则的边界缺陷（漏判「在吗」「跑题闲聊」、误杀「Python」等短专业词），已整理为 bad case 回归清单，后续计划以轻量 LLM 分类器替换规则。

> **配置提示**：复制 `backend/.env.example` 为 `backend/.env` 并填写 DeepSeek API Key 即可启用真实大模型；不配置也能完整运行（自动走规则降级路径）。密钥文件不会提交到仓库。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端（PC 端） | Vue 3 + Vite + Ant Design Vue + Pinia + Vue Router + Axios |
| 后端 | Python 3.10+ + FastAPI + SQLAlchemy 2.0 + PyMySQL |
| 数据库 | MySQL 8.0 |
| 认证 | JWT（python-jose）+ bcrypt 密码哈希 |

## 目录结构

```
实训/
├── 需求文档-AI模拟面试助手.md   # 需求说明
├── schema.sql                    # 数据库建表脚本（16 张表）
├── index.html                    # 原型 HTML（供还原 UI 参考）
├── backend/                      # FastAPI 后端
│   ├── requirements.txt
│   ├── run.py                    # 启动入口
│   ├── .env.example              # 环境变量示例
│   └── app/
│       ├── main.py               # 应用入口 & 路由注册
│       ├── config.py             # 配置（数据库/JWT/CORS）
│       ├── database.py           # 引擎与会话
│       ├── deps.py               # 依赖注入（当前用户）
│       ├── seed.py               # 种子数据脚本
│       ├── models/               # SQLAlchemy 模型（映射全部表）
│       ├── schemas/              # Pydantic 请求/响应模型
│       ├── routers/              # auth/users/resumes/positions/interviews/reports
│       └── services/             # 额度、面试引擎、报告引擎、安全
└── frontend/                     # Vue3 前端
    └── src/
        ├── api/                  # Axios 接口封装
        ├── store/                # Pinia 用户状态
        ├── router/               # 路由
        ├── layouts/              # 主布局
        ├── views/                # 页面
        └── utils/                # 工具函数
```

## 环境要求

- **Python** 3.10 及以上
- **Node.js** 18 及以上
- **MySQL** 8.0（本地已启动，默认端口 3306）

## 一、初始化数据库

1. 创建数据库（如已存在可跳过）：

```sql
CREATE DATABASE IF NOT EXISTS interview_ai DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 执行建表脚本：

```bash
mysql -u root -p interview_ai < schema.sql
```

> 也可跳过手动建表：后端启动时会调用 `Base.metadata.create_all` 自动创建缺失的表；种子数据（订阅计划、面试官人设、通用题库）通过下面的 seed 脚本导入。

## 二、启动后端

```bash
cd backend

# 1. 创建虚拟环境并安装依赖（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# 2. 配置数据库连接（可选，默认 root@127.0.0.1:3306 / interview_ai）
cp .env.example .env
# 按需修改 .env 中的 DB_USER / DB_PASSWORD / DB_NAME 等

# 3. 初始化种子数据（订阅计划 / 面试官人设 / 通用题库）
python -m app.seed

# 4. 启动服务
python run.py
```

后端默认运行在 `http://127.0.0.1:8000`，接口文档见 `http://127.0.0.1:8000/docs`。

## 三、启动前端

```bash
cd frontend

npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，开发环境已配置代理将 `/api` 转发到后端 `http://127.0.0.1:8000`。

## 主要功能

1. **注册 / 登录**：手机号或邮箱 + 密码，支持「跳过登录」体验模式。
2. **工作台**：累计面试次数、平均得分、练习时长、额度使用情况与最近记录。
3. **新建面试**：选择面试类型（技术/行为/案例/HR）、面试官风格（温和教练/压力挑战/大厂/快节奏）、目标岗位 JD、简历、难度与时长，并预览面试方案。
4. **模拟面试间**：多轮对话（文字模拟语音转写），面试官基于简历与 JD 定制提问与追问，支持提前结束。
5. **诊断报告**：综合评分、四维评分、优势/短板、JD 匹配度、逐题点评与话术改进示范。
6. **简历管理**：多版本简历、工作/项目/教育经历、设为默认、编辑删除。
7. **会员中心**：免费版与多档会员计划展示。

## 说明

- **AI 引擎为可替换的 Mock 实现**：`app/services/interview_engine.py`（出题/追问）与 `app/services/report_engine.py`（评分/报告）基于规则生成，接口签名稳定，可平滑替换为真实 LLM / ASR / TTS 调用。
- **支付未接入**：会员中心仅展示计划，升级按钮为演示提示。
- **演示账号**：可直接在登录页「跳过登录，直接体验」自动创建临时账号，或自行注册。
