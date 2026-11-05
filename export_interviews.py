# -*- coding: utf-8 -*-
"""导出面试记录并生成可视化 HTML 报告"""
import json
import pymysql

DB = dict(host="127.0.0.1", port=3306, user="root", password="123456",
          database="interview_ai", charset="utf8mb4")

STATUS = {1: "待开始", 2: "进行中", 3: "正常结束", 4: "提前结束", 5: "中断"}
TYPE = {"tech": "技术面", "behavioral": "行为面", "case": "案例面", "hr": "HR面"}
ROLE = {"interviewer": "面试官", "candidate": "候选人"}

conn = pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# 1. 会话列表（含用户昵称）
cur.execute("""
SELECT s.id, s.session_no, s.user_id, u.nickname, s.interview_type, s.difficulty,
       s.status, s.overall_score, s.started_at, s.ended_at, s.created_at, s.deleted_at
FROM interview_sessions s LEFT JOIN users u ON u.id = s.user_id
ORDER BY s.id
""")
sessions = cur.fetchall()

# 2. 全部题目
cur.execute("SELECT * FROM interview_questions ORDER BY session_id, seq_no")
questions = cur.fetchall()

# 3. 全部消息
cur.execute("SELECT * FROM interview_messages ORDER BY session_id, id")
messages = cur.fetchall()

# 4. 全部报告
cur.execute("SELECT * FROM interview_reports ORDER BY session_id")
reports = cur.fetchall()

conn.close()

# 组织成按会话聚合的结构
sessions_map = {s["id"]: s for s in sessions}
q_by_session = {}
for q in questions:
    q_by_session.setdefault(q["session_id"], []).append(q)
m_by_session = {}
for m in messages:
    m_by_session.setdefault(m["session_id"], []).append(m)
r_by_session = {r["session_id"]: r for r in reports}

# 数据导出为 JSON 存档
dump = {
    "sessions": sessions,
    "questions": questions,
    "messages": messages,
    "reports": reports,
}
with open(r"C:\Users\31609\Desktop\实训\面试记录导出.json", "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=2, default=str)


def esc(s):
    if s is None:
        return "—"
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_dt(d):
    return esc(d.strftime("%m-%d %H:%M")) if d else "—"


def score_color(score):
    if score is None:
        return "#94a3b8"
    if score >= 4:
        return "#e11d48"
    if score >= 3:
        return "#f59e0b"
    return "#16a34a"


def status_color(st):
    return {1: "#64748b", 2: "#2563eb", 3: "#16a34a", 4: "#f59e0b", 5: "#dc2626"}.get(st, "#64748b")


# 构建会话卡片
cards = []
for s in sessions:
    sid = s["id"]
    qs = q_by_session.get(sid, [])
    ms = m_by_session.get(sid, [])
    rp = r_by_session.get(sid)

    st = s["status"]
    st_badge = f'<span class="badge" style="background:{status_color(st)}">{esc(STATUS.get(st, st))}</span>'

    score = s["overall_score"]
    score_html = f'<span class="score" style="color:{score_color(score)}">{esc(score) if score is not None else "未评分"}</span>'

    # 题目列表
    q_rows = ""
    for q in qs:
        qtype = q["question_type"]
        qtype_badge = {"opening": "开场", "main": "主问", "followup": "追问",
                       "closing": "收尾"}.get(qtype, qtype)
        parent = f' <span class="tag">追问自#{q["parent_question_id"]}</span>' if q["parent_question_id"] else ""
        q_rows += f'''<li><span class="qtype">{esc(qtype_badge)}</span><span class="qtext">{esc(q["question_text"])}{parent}</span></li>'''

    # 消息列表（对话流）
    m_rows = ""
    for m in ms:
        role = ROLE.get(m["role"], m["role"])
        cls = "msg-iv" if m["role"] == "interviewer" else "msg-cd"
        flags = []
        if m.get("is_interrupted"):
            flags.append("被打断")
        if m.get("manual_revised"):
            flags.append("手动修正")
        if m.get("asr_confidence") is not None and m["asr_confidence"] < 0.9:
            flags.append(f"置信{m['asr_confidence']}")
        flag_html = f'<span class="flag">{" / ".join(flags)}</span>' if flags else ""
        content = esc(m["content_text"]) if m["content_text"] else "（无文本/语音）"
        m_rows += f'''<div class="msg {cls}"><div class="mh"><span class="role">{esc(role)}</span>{flag_html}</div><div class="mb">{content}</div></div>'''

    # 报告摘要
    report_html = ""
    if rp:
        strengths = json.loads(rp["strengths"]) if rp["strengths"] else []
        weaknesses = json.loads(rp["weaknesses"]) if rp["weaknesses"] else []
        summary = esc(rp["summary"]) if rp["summary"] else ""
        is_full = "完整版(会员)" if rp["is_full"] else "简版(免费)"
        str_html = "".join(f'<span class="chip chip-g">✓ {esc(x)}</span>' for x in strengths)
        weak_html = "".join(f'<span class="chip chip-r">△ {esc(x)}</span>' for x in weaknesses)
        report_html = f'''
        <div class="report">
          <div class="rep-head">诊断报告 <span class="tag">{esc(is_full)}</span> <span class="score" style="color:{score_color(rp["overall_score"])}">{esc(rp["overall_score"])}</span></div>
          {('<div class="rep-row">优势：' + str_html + '</div>') if str_html else ""}
          {('<div class="rep-row">短板：' + weak_html + '</div>') if weak_html else ""}
          {('<div class="rep-summary">' + summary + '</div>') if summary else ""}
        </div>'''

    cards.append(f'''
    <div class="card">
      <div class="card-head">
        <div class="ch-left">
          <div class="no">#{sid} · {esc(s["session_no"])}</div>
          <div class="meta">{esc(s["nickname"])} · {esc(TYPE.get(s["interview_type"], s["interview_type"]))} · 难度 {esc(s["difficulty"])}</div>
        </div>
        <div class="ch-right">{st_badge} {score_html}</div>
      </div>
      <div class="times">开始 {fmt_dt(s["started_at"])} · 结束 {fmt_dt(s["ended_at"])} · 创建 {fmt_dt(s["created_at"])}</div>
      <div class="sec"><div class="sec-title">题目（{len(qs)}）</div><ol class="qlist">{q_rows}</ol></div>
      <div class="sec"><div class="sec-title">对话记录（{len(ms)} 条）</div><div class="msgs">{m_rows}</div></div>
      {report_html}
    </div>''')

# 统计
total = len(sessions)
finished = sum(1 for s in sessions if s["status"] == 3)
ongoing = sum(1 for s in sessions if s["status"] == 2)
scored = [s["overall_score"] for s in sessions if s["overall_score"] is not None]
avg = round(sum(scored) / len(scored), 2) if scored else 0

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>面试记录导出</title>
<style>
  :root {{ --bg:#f8fafc; --card:#ffffff; --border:#e2e8f0; --text:#0f172a; --muted:#64748b; --accent:#2563eb; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }}
  .wrap {{ max-width:960px; margin:0 auto; padding:24px 16px 60px; }}
  header {{ background:linear-gradient(135deg,#1e3a8a,#2563eb); color:#fff; border-radius:16px; padding:28px 28px; margin-bottom:20px; }}
  header h1 {{ margin:0 0 8px; font-size:22px; }}
  header p {{ margin:0; opacity:.85; font-size:13px; }}
  .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin:18px 0 8px; }}
  .stat {{ background:rgba(255,255,255,.15); border-radius:10px; padding:10px 16px; }}
  .stat .num {{ font-size:20px; font-weight:700; }}
  .stat .lbl {{ font-size:12px; opacity:.8; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:18px 20px; margin-bottom:16px; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
  .no {{ font-weight:700; font-size:15px; }}
  .meta {{ color:var(--muted); font-size:13px; margin-top:3px; }}
  .badge {{ color:#fff; font-size:12px; padding:3px 10px; border-radius:999px; white-space:nowrap; }}
  .score {{ font-weight:800; font-size:20px; }}
  .times {{ color:var(--muted); font-size:12px; margin:10px 0 4px; }}
  .sec {{ margin-top:14px; }}
  .sec-title {{ font-size:13px; font-weight:700; color:#334155; border-left:3px solid var(--accent); padding-left:8px; margin-bottom:8px; }}
  .qlist {{ margin:0; padding-left:20px; }}
  .qlist li {{ margin:6px 0; font-size:14px; line-height:1.5; }}
  .qtype {{ display:inline-block; font-size:11px; color:#2563eb; background:#eff6ff; padding:1px 7px; border-radius:6px; margin-right:7px; }}
  .qtext {{ color:#1e293b; }}
  .tag {{ font-size:11px; color:#7c3aed; background:#f5f3ff; padding:1px 6px; border-radius:6px; margin-left:6px; }}
  .msgs {{ display:flex; flex-direction:column; gap:8px; }}
  .msg {{ border-radius:10px; padding:9px 12px; font-size:14px; }}
  .msg-iv {{ background:#f1f5f9; border:1px solid #e2e8f0; }}
  .msg-cd {{ background:#eff6ff; border:1px solid #dbeafe; margin-left:18px; }}
  .mh {{ display:flex; align-items:center; gap:8px; margin-bottom:4px; }}
  .role {{ font-size:12px; font-weight:700; color:#334155; }}
  .flag {{ font-size:11px; color:#b45309; background:#fef3c7; padding:1px 6px; border-radius:6px; }}
  .mb {{ color:#0f172a; line-height:1.55; }}
  .report {{ margin-top:14px; background:#fffbeb; border:1px solid #fde68a; border-radius:12px; padding:12px 14px; }}
  .rep-head {{ font-weight:700; font-size:14px; margin-bottom:6px; }}
  .rep-row {{ font-size:13px; margin:6px 0; }}
  .chip {{ display:inline-block; font-size:12px; padding:2px 8px; border-radius:999px; margin:2px 3px 2px 0; }}
  .chip-g {{ background:#dcfce7; color:#166534; }}
  .chip-r {{ background:#fee2e2; color:#991b1b; }}
  .rep-summary {{ font-size:13px; color:#78350f; margin-top:6px; line-height:1.6; }}
  footer {{ text-align:center; color:var(--muted); font-size:12px; margin-top:24px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>AI 模拟面试助手 · 面试记录导出</h1>
    <p>数据库 interview_ai · 表 interview_sessions（含题目、对话、报告）· 导出时间 {esc(__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"))}</p>
    <div class="stats">
      <div class="stat"><div class="num">{total}</div><div class="lbl">总会话数</div></div>
      <div class="stat"><div class="num">{finished}</div><div class="lbl">正常结束</div></div>
      <div class="stat"><div class="num">{ongoing}</div><div class="lbl">进行中</div></div>
      <div class="stat"><div class="num">{len(scored)}</div><div class="lbl">已评分</div></div>
      <div class="stat"><div class="num">{avg}</div><div class="lbl">平均分</div></div>
    </div>
  </header>
  {''.join(cards)}
  <footer>共 {total} 场面试 · 题目 {len(questions)} 条 · 对话 {len(messages)} 条 · 报告 {len(reports)} 份</footer>
</div>
</body>
</html>'''

out = r"C:\Users\31609\Desktop\实训\面试记录导出.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(html)

print(f"OK sessions={total} questions={len(questions)} messages={len(messages)} reports={len(reports)}")
print(f"HTML -> {out}")
