"""内置预设岗位 JD：让所有新用户在"目标岗位"下拉框中有可选选项。

用户注册时自动播种；启动时为"没有任何岗位"的存量用户补种（幂等）。
用户可自由删除，删除后不会重新播种（只在岗位数为 0 时补种）。
"""
from sqlalchemy.orm import Session

from app.models import JobPosition

# 常见岗位的通用 JD（覆盖技术/产品/数据/运营等方向）
PRESET_POSITIONS = [
    {
        "position_title": "前端开发工程师",
        "job_category": "技术",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责公司 Web 端产品的前端架构设计与开发，保障页面性能与用户体验；\n"
            "2. 基于Vue/React 技术栈完成复杂交互组件的封装与维护；\n"
            "3. 与后端协作制定接口规范，参与前后端联调与上线部署；\n"
            "4. 持续优化首屏加载速度、打包体积与渲染性能。\n"
            "【任职要求】\n"
            "1. 熟悉 HTML/CSS/JavaScript 基础，理解闭包、事件循环、原型链等核心机制；\n"
            "2. 熟练使用 Vue 或 React 及其生态（Vuex/Pinia、React Router 等）；\n"
            "3. 熟悉 HTTP 协议、浏览器渲染原理，有性能优化实践经验；\n"
            "4. 了解工程化工具（Vite/Webpack）与 Git 协作流程。"
        ),
    },
    {
        "position_title": "后端开发工程师（Java）",
        "job_category": "技术",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责核心业务系统的服务端设计与开发，保障高并发场景下的系统稳定性；\n"
            "2. 参与微服务架构演进，完成模块拆分、接口设计与数据库建模；\n"
            "3. 编写高质量、可测试的服务端代码，参与 Code Review；\n"
            "4. 排查线上问题，持续优化接口性能与系统容量。\n"
            "【任职要求】\n"
            "1. 扎实的 Java 基础，深入理解集合、并发编程与 JVM 内存模型；\n"
            "2. 熟悉 Spring/Spring Boot/Spring Cloud 生态与 MyBatis；\n"
            "3. 熟悉 MySQL 索引与事务、Redis 缓存、消息队列（Kafka/RocketMQ）；\n"
            "4. 有分布式系统实践经验，理解幂等、限流、熔断等高可用设计。"
        ),
    },
    {
        "position_title": "后端开发工程师（Python）",
        "job_category": "技术",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责后端服务与 API 的设计开发，支撑业务快速迭代；\n"
            "2. 参与数据抓取、清洗与处理管道建设；\n"
            "3. 编写单元测试与接口文档，保障代码质量；\n"
            "4. 参与系统性能分析与优化。\n"
            "【任职要求】\n"
            "1. 熟练掌握 Python，理解装饰器、生成器、上下文管理器等语言特性；\n"
            "2. 熟悉 FastAPI/Flask/Django 至少一种 Web 框架；\n"
            "3. 熟悉 MySQL、Redis，了解异步编程（asyncio）与多进程/多线程适用场景；\n"
            "4. 有良好的编码习惯，熟悉 Git 协作与 Linux 常用操作。"
        ),
    },
    {
        "position_title": "算法工程师",
        "job_category": "技术",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责推荐/搜索/NLP 方向的算法设计与优化，提升核心业务指标；\n"
            "2. 完成数据预处理、特征工程、模型训练与离线评估全流程；\n"
            "3. 将模型部署至线上环境，持续监控效果并迭代优化；\n"
            "4. 跟踪前沿论文与开源进展，推动技术在业务中落地。\n"
            "【任职要求】\n"
            "1. 扎实的机器学习/深度学习基础，理解常见模型原理与适用场景；\n"
            "2. 熟练使用 PyTorch 或 TensorFlow，具备 Python 工程能力；\n"
            "3. 熟悉常用评估指标（AUC、F1、NDCG 等）与实验设计方法；\n"
            "4. 有推荐系统、NLP 或大模型应用经验者优先。"
        ),
    },
    {
        "position_title": "产品经理",
        "job_category": "产品",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责产品线的需求调研、分析与优先级管理，输出高质量 PRD；\n"
            "2. 设计产品功能流程与原型，协同设计与研发推进落地；\n"
            "3. 跟踪核心数据指标，基于数据反馈持续迭代产品方案；\n"
            "4. 收集用户反馈与竞品动态，挖掘新的产品机会。\n"
            "【任职要求】\n"
            "1. 具备较强的逻辑思维与结构化表达能力，能写清楚需求背景与目标；\n"
            "2. 熟悉产品全生命周期管理，掌握 Axure/Figma 等原型工具；\n"
            "3. 有数据敏感度，能通过漏斗与留存分析定位问题；\n"
            "4. 沟通协调能力强，能推动跨团队协作按期交付。"
        ),
    },
    {
        "position_title": "数据分析师",
        "job_category": "数据",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责业务数据的日常分析、报表搭建与专题分析，输出可落地的结论；\n"
            "2. 参与指标体系与数据看板的设计与维护；\n"
            "3. 通过 A/B 实验与用户行为分析，支撑产品与运营决策；\n"
            "4. 与研发协作完善数据埋点与数据质量治理。\n"
            "【任职要求】\n"
            "1. 精通 SQL，熟悉 Hive/Spark 等大数据处理工具者优先；\n"
            "2. 熟练使用 Python（pandas）或 R 进行数据处理与分析；\n"
            "3. 掌握假设检验、回归、聚类等常用统计方法，理解 A/B 测试原理；\n"
            "4. 具备良好的业务理解力与数据可视化能力（Tableau/Power BI 等）。"
        ),
    },
    {
        "position_title": "测试开发工程师",
        "job_category": "技术",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责产品功能测试与自动化测试体系建设，保障版本交付质量；\n"
            "2. 设计测试用例与测试方案，执行功能、接口与性能测试；\n"
            "3. 开发维护自动化测试脚本与持续集成流水线；\n"
            "4. 跟进线上问题复现与回归验证，沉淀质量度量数据。\n"
            "【任职要求】\n"
            "1. 熟悉软件测试理论与流程，具备扎实的用例设计能力；\n"
            "2. 掌握 Python/Java 至少一门语言，能编写自动化测试脚本；\n"
            "3. 熟悉接口测试工具（Postman/JMeter）与 Selenium/Pytest 等框架；\n"
            "4. 了解 CI/CD 流程，有 Jenkins/GitLab CI 使用经验者优先。"
        ),
    },
    {
        "position_title": "运营专员",
        "job_category": "运营",
        "jd_text": (
            "【岗位职责】\n"
            "1. 负责用户增长与活动运营，策划并执行线上活动，达成增长目标；\n"
            "2. 搭建用户分层运营体系，提升留存与活跃度；\n"
            "3. 撰写运营文案与推送内容，管理内容发布节奏；\n"
            "4. 复盘各项运营动作的数据表现，持续优化策略。\n"
            "【任职要求】\n"
            "1. 文案功底扎实，有网感，能独立完成活动方案与传播内容；\n"
            "2. 数据敏感度高，能通过数据评估活动效果并快速迭代；\n"
            "3. 熟悉主流新媒体平台（公众号/抖音/小红书）的运营玩法；\n"
            "4. 执行力强，具备跨部门沟通与项目推进能力。"
        ),
    },
]


def ensure_preset_positions(db: Session, user_id: int) -> int:
    """补齐该用户缺少的预设岗位（按岗位名去重，幂等）。返回新增数量。

    用户自建的岗位不受影响；若用户删除了某个预设岗位，下次启动会重新补上。
    """
    existing_titles = {
        (t or "").strip()
        for (t,) in db.query(JobPosition.position_title)
        .filter(JobPosition.user_id == user_id)
        .all()
    }
    count = 0
    for preset in PRESET_POSITIONS:
        if preset["position_title"] in existing_titles:
            continue
        db.add(
            JobPosition(
                user_id=user_id,
                company_name=None,
                position_title=preset["position_title"],
                jd_text=preset["jd_text"],
                job_category=preset.get("job_category"),
                parsed_requirements=None,
                source="preset",
            )
        )
        count += 1
    if count:
        db.commit()
    return count


def backfill_all_users(db: Session) -> int:
    """为所有用户补齐缺失的预设岗位（启动时执行，幂等）。"""
    from app.models import User

    users = db.query(User).all()
    total = 0
    for u in users:
        total += ensure_preset_positions(db, u.id)
    return total
