import json
import re
from datetime import date, timedelta
from pathlib import Path

SRC = Path(r"C:\Users\admin\Desktop\my_data9.json")
DEST = Path(r"C:\Users\admin\Desktop\my_data9_enhanced.json")

LEVEL_STD = {
    "L1": "五级/初级工",
    "L2": "四级/中级工",
    "L3": "三级/高级工",
    "L4": "二级/技师",
    "L5": "一级/高级技师",
}

ROLE_LIBRARY = {
    "变电运维值班员": {"skills": ["倒闸操作票复核", "设备巡视缺陷识别", "五防闭锁校验", "异常告警处置"], "dep": ["安规两票流程", "一次设备状态量识别", "监控告警分级"], "safety": ["仅在当值负责人许可和监护下执行倒闸相关演练", "操作票复核不得替代正式唱票复诵和调度许可", "异常告警处置必须先完成风险辨识并留痕"], "team_score": 82, "team_hours": 3.2},
    "继电保护工": {"skills": ["软压板逻辑", "定值单核对", "二次回路识图", "故障录波判读"], "dep": ["保护原理与定值单结构", "软硬压板对应关系", "二次回路安全隔离"], "safety": ["保护装置相关操作须在继保负责人授权和监护下进行", "不得在未签发工作票情况下触碰运行保护压板", "定值核对输出只能作为复核建议，不能替代正式审批"], "team_score": 84, "team_hours": 4.0},
    "高压试验员": {"skills": ["绝缘电阻试验", "介损测试", "SF6微水检测", "避雷器带电检测"], "dep": ["试验接线安全距离", "仪器校准与放电流程", "试验报告判据"], "safety": ["高压试验必须在试验负责人许可、围栏和专人监护下实施", "带电检测只能在具备相应授权并完成风险交底后执行", "试验结论需经持证人员复核后进入正式报告"], "team_score": 83, "team_hours": 4.2},
    "设备巡视员": {"skills": ["红外测温", "设备外观缺陷识别", "巡视路线优化", "异常状态上报"], "dep": ["巡视标准化路线", "缺陷分级规则", "红外图谱判读"], "safety": ["巡视发现异常只做记录和上报，不擅自扩大工作范围", "近电巡视必须保持安全距离并执行双人确认", "缺陷定级需由班组长或专业人员复核"], "team_score": 81, "team_hours": 2.8},
    "一次设备检修工": {"skills": ["断路器机构检查", "隔离开关调整", "接地刀闸联锁检查", "检修记录闭环"], "dep": ["一次设备结构原理", "检修工器具点检", "机械闭锁逻辑"], "safety": ["一次设备检修必须在停电、验电、挂接地线后按票执行", "机械调整需在检修负责人监护下进行", "未完成安措复核不得进行机构动作试验"], "team_score": 82, "team_hours": 5.0},
    "二次回路检修工": {"skills": ["端子排核对", "回路绝缘检查", "信号回路排查", "图纸变更闭环"], "dep": ["二次图纸识读", "端子编号规则", "回路隔离措施"], "safety": ["二次回路作业必须执行防误碰隔离和监护复核", "运行回路不得单人拆接线", "图纸变更须经技术负责人确认后归档"], "team_score": 83, "team_hours": 4.6},
    "变压器检修工": {"skills": ["油色谱异常判断", "套管检查", "冷却系统巡检", "有载调压机构检查"], "dep": ["变压器结构与油务知识", "冷却控制回路", "异常声音辨识"], "safety": ["变压器附件检修须在许可范围内并落实防高坠防触电措施", "油务取样和附件检查需按作业指导书留样留痕", "涉及有载调压机构动作须经负责人监护"], "team_score": 84, "team_hours": 5.4},
    "开关柜检修员": {"skills": ["局放检测", "机械特性测试", "柜内闭锁检查", "母线室隐患识别"], "dep": ["开关柜结构分区", "局放图谱基础", "机械特性判据"], "safety": ["开关柜作业须确认隔离、验电、接地和防误闭锁状态", "局放检测不得擅自开启带电间隔柜门", "机械特性测试需在检修负责人监护下接线"], "team_score": 82, "team_hours": 4.4},
    "通信自动化运维员": {"skills": ["远动通道排障", "保护信息子站维护", "遥信遥测核对", "时钟同步检查"], "dep": ["站控层网络拓扑", "规约点表基础", "网络安全边界"], "safety": ["自动化配置变更须经审批并做好备份回退", "远动通道排障不得越权修改调度侧参数", "网络接入需符合二次安防要求"], "team_score": 85, "team_hours": 3.7},
    "班组技术员": {"skills": ["缺陷闭环管理", "作业风险辨识", "技术交底", "复盘报告编写"], "dep": ["班组台账规范", "风险分级管控", "作业指导书编制"], "safety": ["技术建议需经班组长或专业负责人确认后执行", "风险交底不得替代现场许可和监护", "跨专业安排需明确责任边界和验收人"], "team_score": 86, "team_hours": 3.5},
    "蓄电池维护员": {"skills": ["蓄电池内阻测试", "容量核对性放电", "直流系统告警处置", "端电压趋势分析"], "dep": ["直流系统构成", "蓄电池试验规程", "告警信号含义"], "safety": ["蓄电池放电试验须在直流专业授权、旁路保障和专人监护下执行", "直流系统异常不得擅自退出保护电源", "测试记录需经直流负责人复核"], "team_score": 82, "team_hours": 3.8},
    "避雷器检修员": {"skills": ["避雷器泄漏电流检测", "红外异常判断", "在线监测数据核对", "计数器动作分析"], "dep": ["避雷器结构原理", "带电检测安全距离", "红外与泄漏电流判据"], "safety": ["避雷器带电检测需具备带电检测授权并保持规定安全距离", "异常判定不得替代停电检修审批", "检测结论需经高压专业复核"], "team_score": 83, "team_hours": 3.6},
    "接地网检测员": {"skills": ["接地电阻测试", "跨步电压风险辨识", "接地引下线检查", "测试点布置"], "dep": ["接地系统图纸识读", "测试仪器接线", "安全围栏设置"], "safety": ["接地网测试必须办理现场许可并避开雷雨天气", "测试线布置需设置警示并安排看护", "涉及开挖或拆接必须另行审批"], "team_score": 81, "team_hours": 4.1},
    "隔离开关检修员": {"skills": ["触头接触状态检查", "机构连杆调整", "分合闸同期检查", "闭锁逻辑核对"], "dep": ["隔离开关机械结构", "传动机构润滑点", "五防闭锁逻辑"], "safety": ["隔离开关调整必须在停电接地和检修负责人监护下进行", "机构试动前需确认人员撤离和闭锁状态", "不得越权解除五防闭锁"], "team_score": 82, "team_hours": 5.2},
    "变压器冷却系统维护员": {"skills": ["冷却器控制回路检查", "风机油泵切换试验", "温控器校验", "冷却系统缺陷闭环"], "dep": ["冷却系统控制逻辑", "温度保护联动关系", "低压控制回路安全"], "safety": ["冷却系统切换试验须经运行值班许可并设专人监视油温", "控制回路作业需断开相应电源并验电", "不得擅自退出主变冷却保护联锁"], "team_score": 84, "team_hours": 4.8},
    "母线保护检修员": {"skills": ["母差保护逻辑校验", "CT回路极性核对", "出口回路隔离", "保护定检记录"], "dep": ["母差保护原理", "CT二次回路规则", "出口压板管理"], "safety": ["母线保护检修须由继保负责人授权并执行双人复核", "出口回路相关操作必须按票隔离并全过程监护", "试验结论需经专业负责人签字"], "team_score": 85, "team_hours": 5.0},
    "机器人巡检运维员": {"skills": ["巡检点位配置", "机器人告警复核", "红外图谱标注", "巡检路线维护"], "dep": ["机器人巡检系统操作", "设备点位命名规范", "红外缺陷判据"], "safety": ["机器人巡检路线调整需经运维负责人确认，不得覆盖禁行区域", "机器人告警仅作为辅助发现，缺陷定级需人工复核", "现场干预机器人需先确认设备安全距离"], "team_score": 83, "team_hours": 3.1},
    "电能质量监测员": {"skills": ["谐波数据分析", "电压暂降事件判读", "监测装置校验", "治理建议编写"], "dep": ["电能质量指标体系", "监测装置接线规则", "用户侧负荷特性"], "safety": ["监测装置接入须执行二次安全措施并经计量/自动化专业确认", "治理建议不得替代客户侧改造审批", "异常事件结论需经专业负责人复核"], "team_score": 84, "team_hours": 3.9},
}

SOFT_STRATEGIES = [
    ("主动提问", "每日一问机制：每天班前提交1个具体卡点，班后用三句话复述师傅答复并归档", "主动提问闭环任务（连续10个工作日提交卡点、答复和复盘）", "建立每日一问台账，把不会的点从口头问题转成可追踪记录", "连续10个工作日完成每日一问，师傅抽查通过率≥90%"),
    ("沟通", "三段式汇报：现象、风险、请求支持，连续完成5次现场卡点主动汇报", "现场卡点三段式汇报训练", "把沉默卡点改为现场主动汇报，避免问题拖到任务末尾", "5次汇报记录完整，班组长评价达到清晰可执行"),
    ("表达", "完成3次向非专业人员解释一个专业概念，并提交1份缺陷分析报告给师傅批注", "技术表达转译与缺陷报告编写任务", "训练把专业判断写成清楚结论、依据和检修建议", "完成3次非专业解释，缺陷报告一次返工项≤2处"),
    ("协作", "跨班组跟班2次→主动发送交接清单→复盘1次接口卡点和责任边界", "跨班组跟班与主动汇报组合任务", "把协作障碍拆成接口清单、主动汇报和责任确认三件事", "完成2次跨班组跟班，交接清单无遗漏项"),
    ("复核", "执行双人复核清单：关键读数、风险点、结论三项逐项签认，连续完成4次", "检修后复核沟通清单训练", "把复核从口头确认改为清单化签认，降低遗漏风险", "4次复核清单齐全，关键项遗漏为0"),
    ("描述", "按设备位置-异常现象-趋势-初判风险模板完成6条异常描述并由师傅评分", "故障现象结构化描述训练", "先把异常说准确，再进入原因判断和处置建议", "6条异常描述平均评分≥85分，退回重写≤1条"),
    ("汇报", "异常数据10分钟内上报，附原始读数、对比基准和建议复测点位", "异常数据主动上报演练", "围绕异常数据建立及时上报和证据链意识", "完成5次模拟上报，字段完整率100%"),
    ("结论", "每周完成2份结论-依据-边界短报告，明确不能越权判断的部分", "技术结论边界表达训练", "把结论写清楚，同时保留授权边界和待复核事项", "4份短报告通过师傅复核，越界表述为0"),
]

def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\\n", " ").replace("\\t", " ")).strip()

def parse_first(text, pattern, fallback=""):
    match = re.search(pattern, clean_text(text))
    return clean_text(match.group(1)) if match else fallback

def parse_all(input_text):
    s = clean_text(input_text)
    name_role = parse_first(s, r"姓名 / 岗位：(.+?) 部门 / 班组：", "未知员工 · 变电运维值班员")
    if " · " in name_role:
        parts = [clean_text(x) for x in name_role.split(" · ", 1)]
    elif " / " in name_role:
        parts = [clean_text(x) for x in name_role.split(" / ", 1)]
    else:
        parts = [clean_text(name_role), "变电运维值班员"]
    lvl = re.search(r"当前\s*(L\d)，岗位要求\s*(L\d)", s)
    exam = re.search(r"考试与错题：(.+?)考试\s*(\d+(?:\.\d+)?)\s*分，合格线\s*(\d+(?:\.\d+)?)\s*分", s)
    work = re.search(r"实操任务：(.+?)计划\s*(\d+(?:\.\d+)?)\s*小时，实际\s*(\d+(?:\.\d+)?)\s*小时", s)
    cert_raw = parse_first(s, r"证书：(.+?) 职业目标 ", "变电运维岗位资格证有效期至2027-12-31")
    cert_date = re.search(r"20\d{2}-\d{2}-\d{2}", cert_raw)
    return {
        "name": parts[0] if parts else "未知员工",
        "role": parts[1] if len(parts) > 1 and parts[1] else "变电运维值班员",
        "team": parse_first(s, r"部门 / 班组：(.+?) 工龄 / 入职时间：", "变电运维中心 / 一班"),
        "tenure": parse_first(s, r"工龄 / 入职时间：(.+?) 当前", "3年 / 2023-01-01"),
        "current": lvl.group(1) if lvl else "L1",
        "job_req": lvl.group(2) if lvl else "L3",
        "future_req": parse_first(s, r"未来需求\s*(L\d)", lvl.group(2) if lvl else "L3"),
        "main_skill": parse_first(s, r"主技能：(.+?) 技能树盲区：", "继电保护"),
        "blind": parse_first(s, r"技能树盲区：(.+?) 软技能短板：", "二次回路识图"),
        "soft": parse_first(s, r"软技能短板：(.+?) 考试与错题：", "主动提问困难"),
        "exam_topic": clean_text(exam.group(1)) if exam else "继电保护基础",
        "score": float(exam.group(2)) if exam else 65.0,
        "pass_score": float(exam.group(3)) if exam else 80.0,
        "task": clean_text(work.group(1)) if work else "倒闸操作票复核",
        "planned": float(work.group(2)) if work else 4.0,
        "actual": float(work.group(3)) if work else 5.5,
        "mentor_review": parse_first(s, r"带教师傅：(.+?) 评价：", "师傅复核2次"),
        "mentor_level": parse_first(s, r"评价：(.+?)证书：", parse_first(s, r"评价：(.+?)当前\s*L\d", "需要规范化复盘")),
        "cert_raw": cert_raw,
        "cert_date": cert_date.group(0) if cert_date else "2027-12-31",
        "target": parse_first(s, r"职业目标 / 轮岗意向：(.+?) 用户查询", "成长为L3复合型人才"),
        "query": parse_first(s, r"用户查询（([^）]+)）", "个性化诊断"),
        "input": input_text,
    }

def pick(items, index):
    return items[index % len(items)]

def role_profile(role):
    return ROLE_LIBRARY.get(role, ROLE_LIBRARY[pick(list(ROLE_LIBRARY), len(role))])

def soft_strategy(soft, index):
    for item in SOFT_STRATEGIES:
        if item[0] in soft:
            return item
    return pick(SOFT_STRATEGIES, index)

def next_level(current, req):
    cur = int((current or "L1").replace("L", ""))
    target = int((req or "L3").replace("L", ""))
    return f"L{min(cur + 1, target)}"

def add_days(days):
    return (date(2026, 9, 30) + timedelta(days=days)).isoformat()

def build_input(f):
    return f"姓名 / 岗位：{f['name']} / {f['role']} 部门 / 班组：{f['team']} 工龄 / 入职时间：{f['tenure']} 当前{f['current']}，岗位要求{f['job_req']}，未来需求{f['future_req']}，主技能：{f['main_skill']} 技能树盲区：{f['blind']} 软技能短板：{f['soft']} 考试与错题：{f['exam_topic']}考试 {f['score']:g} 分，合格线 {f['pass_score']:g} 分 实操任务：{f['task']}计划 {f['planned']:g} 小时，实际 {f['actual']:g} 小时 带教师傅：{f['mentor_review']} 评价：{f['mentor_level']}证书：{f['cert_raw']} 职业目标 / 轮岗意向：{f['target']} 用户查询（{f['query']}）：请生成个性化诊断和学习提升方案。"

def build_output(f, index):
    rp = role_profile(f["role"])
    score_gap = round(f["pass_score"] - f["score"], 1)
    overtime = round(f["actual"] - f["planned"], 1)
    overtime_rate = round(overtime / f["planned"] * 100, 1) if f["planned"] else 0
    target_hours = round(max(f["planned"], min(f["actual"] - 0.5, rp["team_hours"] + 0.4)), 1)
    key, soft_action, soft_path, soft_road, soft_metric = soft_strategy(f["soft"], index)
    role_skill = pick(rp["skills"], index)
    role_skill2 = pick(rp["skills"], index + 1)
    pre = pick(rp["dep"], index)
    safety = pick(rp["safety"], index)
    exam_focus = f"错题逐题归因，重点复盘{f['exam_topic']}中失分最高的知识点" if score_gap >= 15 else (f"{f['exam_topic']}错题分类复盘，补齐易混规则" if score_gap >= 8 else f"{f['exam_topic']}边界题复核，防止低级失误")
    time_focus = f"{f['task']}分段计时复盘，拆分准备、执行、记录三段耗时" if overtime >= 2 else (f"{f['task']}关键步骤限时演练，压缩等待和返工时间" if overtime >= 1 else f"{f['task']}稳定性复盘，保持合格线内完成")
    action1 = f"{exam_focus}；{time_focus}；{soft_action}；涉及现场操作时{safety}"
    action2 = f"{pre}清单核对→{role_skill}带教2次→提交1份{f['task']}复盘记录→在具备相应授权且有监护前提下完成模拟或跟班验证"
    return {
        "conclusion": f"{f['name']}当前{f['role']}主差距是{f['main_skill']}{f['current']}到岗位要求{f['job_req']}的等级差，考试{f['score']:g}分较合格线{f['pass_score']:g}分差{score_gap:g}分，{f['task']}计划{f['planned']:g}小时实际{f['actual']:g}小时超时{overtime:g}小时；软技能短板为{f['soft']}。建议在证书到期日{f['cert_date']}前完成第1至第3步，其中现场类动作仅能在授权、许可和监护条件满足时作为训练或跟班任务执行，不能越权替代正式作业。",
        "gaps": [
            {"priority": "P1", "skill": f["main_skill"], "current": f["current"], "job_req": f["job_req"], "future_req": f["future_req"], "impact": f"{f['main_skill']}等级差导致{f['task']}需要师傅复核，无法稳定承担{f['role']}关键任务。", "action": action1},
            {"priority": "P2", "skill": f["blind"], "current": f["current"], "job_req": next_level(f["current"], f["job_req"]), "future_req": f["future_req"], "impact": f"{f['blind']}盲区叠加{f['soft']}，使异常判断、记录交接和复盘闭环容易断点。", "action": action2},
        ],
        "learning_path": [
            {"step": 1, "type": "任务复盘", "name": f"{f['exam_topic']}错题逐题归因与{f['blind']}知识点索引", "deadline": add_days(14 + index % 5), "target": f"{f['main_skill']}→{next_level(f['current'], f['job_req'])}", "reason": f"考试差{score_gap:g}分，先把错题对应规则和{f['blind']}概念补齐，避免直接进入现场训练造成反复返工。"},
            {"step": 2, "type": "带教", "name": f"{f['task']}分段计时跟班（计划{f['planned']:g}小时，目标≤{target_hours:g}小时）", "deadline": add_days(35 + index % 7), "target": f"{role_skill}效率达标", "reason": f"实际耗时{f['actual']:g}小时，较计划多{overtime:g}小时，需要拆分准备、执行、记录三段，定位真正慢点。"},
            {"step": 3, "type": "模拟考", "name": f"{f['main_skill']}授权边界内模拟考与{role_skill2}情景问答", "deadline": add_days(58 + index % 9), "target": f"考试≥80分，{f['main_skill']}达到{f['job_req']}", "reason": "将理论错题、岗位技能和安全边界放进同一次验收，防止只会答题不会按规程执行。"},
            {"step": 4, "type": "任务复盘", "name": soft_path, "deadline": add_days(75 + index % 20), "target": f"{f['soft']}改善并支撑{f['target']}", "reason": f"师傅评价为{f['mentor_level']}，软技能短板会影响带教吸收、缺陷闭环和跨班组协同。"},
        ],
        "roadmap": [
            {"phase": "第1阶段 · 0-2个月", "learn": f"围绕{f['exam_topic']}做错题逐题归因，并把{f['blind']}整理成岗位化核对清单。", "metrics": "模拟考≥80分，错题归因表覆盖率100%，师傅复核1次通过。"},
            {"phase": "第2阶段 · 2-4个月", "learn": f"开展{f['task']}分段计时复盘，重点压缩超时{overtime:g}小时中的准备和记录返工。", "metrics": f"单次耗时≤{target_hours:g}小时，三段耗时记录不少于3次。"},
            {"phase": "第3阶段 · 4-6个月", "learn": f"在{safety}的边界下完成{role_skill}跟班验证和{role_skill2}情景问答。", "metrics": "跟班2次，关键步骤口述正确率≥90%，无越权操作表述。"},
            {"phase": "第4阶段 · 6-9个月", "learn": f"结合{f['soft']}执行{soft_road}，形成可复用的岗位复盘样例。", "metrics": soft_metric},
        ],
        "level_mapping": {"current_level": f["current"], "job_required_level": f["job_req"], "future_required_level": f["future_req"], "national_standard": LEVEL_STD, "current_standard": LEVEL_STD.get(f["current"], "未定级"), "job_required_standard": LEVEL_STD.get(f["job_req"], "未定级"), "future_required_standard": LEVEL_STD.get(f["future_req"], "未定级")},
        "skill_dependencies": [{"name": pre, "type": "前置"}, {"name": role_skill, "type": "核心"}, {"name": f"{f['task']}验收记录与师傅复核", "type": "验收"}],
        "safety_boundary": safety,
        "quantitative_baseline": {"exam_score": f["score"], "pass_score": f["pass_score"], "score_gap": score_gap, "planned_hours": f["planned"], "actual_hours": f["actual"], "overtime_hours": overtime, "overtime_rate": f"{overtime_rate}%", "target_hours": target_hours, "team_avg_hours": rp["team_hours"], "team_avg_score": rp["team_score"], "mentor_review_count": int(re.search(r"\d+", f["mentor_review"]).group(0)) if re.search(r"\d+", f["mentor_review"]) else 2},
        "personalization_basis": [f"岗位={f['role']}", f"考试={f['score']:g}/{f['pass_score']:g}", f"耗时={f['actual']:g}/{f['planned']:g}小时", f"软技能={f['soft']}", f"盲区={f['blind']}", f"证书到期={f['cert_date']}"],
    }

def row_from_facts(f, index, instruction):
    return {"instruction": instruction, "input": clean_text(f.get("input") or build_input(f)), "output": json.dumps(build_output(f, index), ensure_ascii=False, separators=(",", ":"))}

def role_of(row):
    return parse_all(row["input"])["role"]

def safety_of(row):
    return json.loads(row["output"])["safety_boundary"]

def reorder(rows):
    pending = rows[:]
    ordered = []
    while pending:
        chosen = 0
        for i, row in enumerate(pending):
            role = role_of(row)
            safety = safety_of(row)
            if len(ordered) >= 2 and all(role_of(x) == role for x in ordered[-2:]):
                continue
            if len(ordered) >= 3 and all(safety_of(x) == safety for x in ordered[-3:]):
                continue
            chosen = i
            break
        ordered.append(pending.pop(chosen))
    return ordered

def main():
    source = json.loads(SRC.read_text(encoding="utf-8-sig"))
    if not isinstance(source, list):
        raise ValueError("source is not a JSON array")
    instruction = source[0].get("instruction") or "你是专业诊断专家，请根据用户提供的全部个人档案信息，完成个性化诊断，并生成对应的学习提升方案。输出格式严格遵循本项目前端诊断报告的排版规范。"
    rows = [row_from_facts(parse_all(row.get("input", "")), i, row.get("instruction") or instruction) for i, row in enumerate(source)]

    extra_roles = ["蓄电池维护员", "避雷器检修员", "接地网检测员", "隔离开关检修员", "变压器冷却系统维护员", "母线保护检修员", "机器人巡检运维员", "电能质量监测员", "开关柜检修员", "通信自动化运维员"]
    names = ["顾晨", "沈悦", "陆明", "唐晓", "侯宁", "蒋岚", "韩旭", "曹颖", "许峰", "邵琳"]
    softs = ["异常数据主动汇报不足", "检修建议技术表达不足", "跨班组现场协作不足", "检修后复核沟通不足", "故障现象描述不完整", "跨专业试验协调不足", "误报告警解释不足", "异常路线主动上报不足", "曲线结论表达不足", "客户侧治理建议表达不足"]
    queries = ["证书授权", "复合型路线", "实操效率", "技术等级差距", "软技能缺失", "安全优先级", "目标岗位", "30天计划", "岗位匹配", "考试错题"]
    for j, role in enumerate(extra_roles):
        rp = role_profile(role)
        f = {"name": names[j], "role": role, "team": f"变电运维中心 / 专项{j % 5 + 1}班", "tenure": f"{j + 2}年 / {2024 - j}-0{j % 8 + 1}-15", "current": "L1" if j % 3 == 0 else "L2", "job_req": "L3" if j % 3 == 0 else "L4", "future_req": "L4" if j % 2 == 0 else "L3", "main_skill": pick(rp["skills"], j), "blind": pick(rp["skills"], j + 1), "soft": softs[j], "exam_topic": pick(rp["skills"], j + 2), "score": float(55 + (j * 7) % 24), "pass_score": 80.0, "task": pick(rp["skills"], j + 3), "planned": round(3 + (j % 4) * 0.5, 1), "actual": round(4.8 + (j % 5) * 0.7, 1), "mentor_review": f"师傅复核{2 + j % 4}次，发现关键步骤需要提示", "mentor_level": pick(["需要强化主动汇报", "理论能答但现场组织偏慢", "结论表达边界不清", "跨专业配合等待较多"], j), "cert_raw": f"{role}岗位资格证有效期至2027-{j + 3:02d}-20", "cert_date": f"2027-{j + 3:02d}-20", "target": "成长为L3复合型人才并承担专项巡检" if j % 2 == 0 else "向L4骨干培养，具备带教和复盘能力", "query": queries[j]}
        rows.append(row_from_facts(f, len(source) + j, instruction))

    rows = reorder(rows)
    DEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    validate(rows)

def validate(rows):
    vague = re.compile(r"加强学习|多看图纸|多读书|增加实操|参加在线课程|第\d+类场景|第X类场景")
    cn_key = re.compile(r"[\u4e00-\u9fff]")
    errors = []
    signatures = set()
    duplicate_count = 0
    max_role_run = max_safety_run = role_run = safety_run = 0
    prev_role = prev_safety = None
    for i, row in enumerate(rows):
        out = json.loads(row["output"])
        if not all(k in row for k in ["instruction", "input", "output"]): errors.append(f"row {i} top keys")
        if not isinstance(out.get("gaps"), list) or not isinstance(out.get("learning_path"), list) or not isinstance(out.get("roadmap"), list): errors.append(f"row {i} arrays")
        if "national_standard" not in out.get("level_mapping", {}): errors.append(f"row {i} national_standard")
        qb = out.get("quantitative_baseline", {})
        if not isinstance(qb.get("team_avg_hours"), (int, float)) or not isinstance(qb.get("team_avg_score"), (int, float)): errors.append(f"row {i} team avg")
        if any(d.get("type") not in ["前置", "核心", "验收"] for d in out.get("skill_dependencies", [])): errors.append(f"row {i} dep type")
        if vague.search(row["output"]): errors.append(f"row {i} vague")
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if cn_key.search(k): errors.append(f"row {i} chinese key {k}")
                    walk(v)
            elif isinstance(obj, list):
                for item in obj: walk(item)
        walk(out)
        facts = parse_all(row["input"])
        expected = round(facts["actual"] - facts["planned"], 1)
        if qb.get("overtime_hours") != expected: errors.append(f"row {i} overtime")
        role = facts["role"]
        role_run = role_run + 1 if role == prev_role else 1
        max_role_run = max(max_role_run, role_run)
        prev_role = role
        safety = out["safety_boundary"]
        safety_run = safety_run + 1 if safety == prev_safety else 1
        max_safety_run = max(max_safety_run, safety_run)
        prev_safety = safety
        sig = "|".join([role, facts["query"], facts["soft"], ";".join(g["action"] for g in out["gaps"]), ";".join(p["name"] for p in out["learning_path"]), ";".join(r["learn"] for r in out["roadmap"])])
        if sig in signatures: duplicate_count += 1
        signatures.add(sig)
    summary = {"dest": str(DEST), "count": len(rows), "roles": len({role_of(r) for r in rows}), "soft_types": len({parse_all(r["input"])["soft"] for r in rows}), "duplicate_signatures": duplicate_count, "max_consecutive_role": max_role_run, "max_consecutive_safety_boundary": max_safety_run, "validation_error_count": len(errors), "validation_errors": errors[:20]}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
