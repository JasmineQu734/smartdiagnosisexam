import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from build_my_data12_standard import ROLE_PROFILES, SOFT_POOL  # noqa: E402


DESKTOP = Path(r"C:\Users\admin\Desktop")
ALL_PATH = DESKTOP / "my_data14.json"
TRAIN_PATH = DESKTOP / "my_data14_train.json"
VAL_PATH = DESKTOP / "my_data14_val.json"

INSTRUCTION = (
    "你是专业诊断专家，请根据用户提供的全部个人档案信息，完成个性化诊断，并生成对应的学习提升方案。"
    "输出格式严格遵循本项目前端诊断报告的排版规范。"
)

QUERY_TYPES = [
    "技术等级差距",
    "实操效率",
    "软技能缺失",
    "证书授权",
    "安全优先级",
    "目标岗位",
    "考试错题",
    "30天计划",
    "岗位匹配",
    "复合型路线",
]

NAMES = [
    "赵晨", "钱悦", "孙明", "李岚", "周宁", "吴旭", "郑颖", "王峰", "冯琳", "陈航",
    "褚睿", "卫彤", "蒋磊", "沈洁", "韩涛", "杨琪", "朱楠", "秦博", "尤静", "许凯",
    "何璐", "吕鑫", "施洋", "张敏", "孔昊", "曹婷", "严森", "华丹", "金威", "魏然",
    "陶晨", "姜悦", "谢明", "邹岚", "喻宁", "柏旭", "水颖", "窦峰", "章琳", "云航",
    "苏睿", "潘彤", "葛磊", "奚洁", "范涛", "彭琪", "郎楠", "鲁博", "韦静", "昌凯",
    "马璐", "苗鑫", "凤洋", "花敏", "方昊", "俞婷", "任森", "袁丹", "柳威", "鲍然",
    "史晨", "唐悦", "费明", "廉岚", "岑宁", "薛旭", "雷颖", "贺峰", "倪琳", "汤航",
    "滕睿", "殷彤", "罗磊", "毕洁", "郝涛", "邬琪", "安楠", "常博", "乐静", "于凯",
    "时璐", "傅鑫", "皮洋", "卞敏", "齐昊", "康婷", "伍森", "余丹", "元威", "卜然",
    "顾晨一", "孟悦一", "平明一", "黄岚一", "和宁一", "穆旭一", "萧颖一", "尹峰一",
    "姚琳一", "邵航一", "湛睿一", "汪彤一", "祁磊一", "毛洁一", "禹涛一", "狄琪一",
    "米楠一", "贝博一", "明静一", "臧凯一", "计璐一", "伏鑫一", "成洋一", "戴敏一",
    "谈昊一", "宋婷一", "庞森一", "熊丹一", "纪威一", "舒然一", "屈晨一", "项悦一",
    "祝明一", "董岚一", "梁宁一", "杜旭一", "阮颖一", "蓝峰一", "闵琳一", "席航一",
    "季睿一", "麻彤一", "强磊一", "贾洁一", "路涛一", "娄琪一", "危楠一", "江博一",
    "童静一", "颜凯一", "郭璐一", "梅鑫一", "盛洋一", "林敏一", "刁昊一", "钟婷一",
    "徐森一", "邱丹一", "骆威一", "高然一", "夏晨一", "蔡悦一", "田明一", "樊岚一",
    "胡宁一", "凌旭一", "霍颖一", "虞峰一", "万琳一", "支航一", "柯睿一", "昝彤一",
    "管磊一", "卢洁一", "莫涛一", "经琪一", "房楠一", "裘博一", "缪静一", "干凯一",
]

SCENARIO_PREFIX = {
    "事故抢修": "事故抢修",
    "新设备投运": "新设备投运",
    "迎峰度夏特巡": "迎峰度夏特巡",
    "缺陷闭环": "缺陷闭环",
    "带教复盘": "带教复盘",
}

SAFETY_RECORDS = [
    ("无扣分记录", "近12个月无安全扣分和未遂事件，现场安措执行记录完整。", "继续保持双人复诵、验电接地和过程留痕。"),
    ("安全扣分", "近12个月因漏填一项风险预控措施扣2分，未造成设备或人身后果。", "把开工前风险清单改为逐项口述加签字，未完成不得进入下一步骤。"),
    ("未遂事件", "曾在夜间巡视中靠近异常发热点，因同伴提醒及时退回，形成1起未遂事件。", "异常巡视先停留在安全距离外，完成上报和复核后再决定是否扩大检查范围。"),
    ("越权操作", "曾在师傅未到场时尝试修改监控告警屏蔽条件，后被及时制止，未改变运行状态。", "任何运行参数和屏蔽条件变更都必须审批、授权、监护并留存回退方案。"),
    ("无票作业", "曾参与一次无票拆接二次端子排的违章作业，未造成保护误动，已完成班组通报。", "没有工作票、许可和隔离措施时只允许停留在资料复核，不得触碰现场回路。"),
    ("未监护", "曾在带教任务中未等监护人到位就开始仪器接线，被班组长叫停。", "现场接线、试验和机构试动必须确认监护人到位后才能开始。"),
]

WRONG_QUESTIONS = {
    "保护": [
        ("在运行保护装置上核对软压板时，以下做法正确的是？", "选B：直接退出压板后观察信号变化", "选A：只核对标识和定值单，不触碰运行压板", "软压板投退边界", "把验证想当然地等同于现场试动"),
        ("定值单版本核对首先要确认什么？", "选C：先修改装置内定值再比对", "选A：核对定值单编号、版本、审批状态和装置当前版本", "定值版本管理", "忽略版本和审批链，只关注数值"),
        ("保护出口回路试验前最先完成的措施是？", "选B：先加大试验电流观察出口", "选A：按工作票隔离出口回路并完成双人核对", "出口回路安全隔离", "把试验顺序和运行状态边界混淆"),
    ],
    "试验": [
        ("绝缘电阻试验结束后，正确的收尾动作是什么？", "选D：立即拆线收工", "选A：先放电并确认无残余电荷，再拆线和记录", "试验放电与收尾", "只记得接线，遗漏放电和残压确认"),
        ("SF6检测进入低洼区域前应先做什么？", "选B：佩戴手套后直接进入", "选A：通风、检测环境气体并安排专人监护", "SF6环境安全", "把个人防护用品当成环境检测的替代"),
        ("介损数据异常时，不能直接得出的结论是？", "选C：立即判定设备击穿", "选A：结合温度、接线、历史趋势和复测结果综合判断", "介损数据判读", "将单次数据直接等同于设备最终结论"),
    ],
    "运行": [
        ("执行倒闸操作前的正确顺序是？", "选A：先操作设备，再补填操作票", "选B：核对调度令、操作票、模拟预演和现场设备名称", "两票和调度指令", "把效率放在票据和指令核对之前"),
        ("发现开关柜温升异常时，第一步应是什么？", "选C：立即打开柜门查看", "选A：保持安全距离，记录数据并按告警等级上报", "异常巡视和安全距离", "在未辨识风险前扩大现场接近范围"),
        ("五防闭锁异常时，哪种处理不合规？", "选D：履行审批后按解锁流程处理", "选A：为了赶进度私自使用万能钥匙解除闭锁", "防误闭锁管理", "把工期压力当成越权解锁理由"),
    ],
    "通用": [
        ("作业负责人发现现场条件与作业票不一致时应如何处理？", "选B：先做一小步验证再说", "选A：停止作业，重新核实风险和许可条件", "作业条件确认", "没有执行停止作业和条件复核"),
        ("缺陷闭环记录至少应包含哪些内容？", "选C：只写处理结果", "选A：现象、证据、原因、措施、复测结果和责任人", "缺陷闭环记录", "记录只写结果，缺少证据和验证"),
        ("跨班组交接时最容易漏掉的关键项是什么？", "选D：午餐安排", "选A：未完成安措、设备状态、遗留风险和下一步责任人", "跨班组交接", "只交接任务名称，没有交接边界和责任"),
    ],
}

def pick(items, index):
    return items[index % len(items)]

def add_days(days):
    return (date(2026, 10, 9) + timedelta(days=days)).isoformat()

def level_for_tenure(tenure):
    if tenure <= 2:
        return "L1"
    if tenure <= 5:
        return "L2"
    if tenure <= 9:
        return "L3"
    if tenure <= 13:
        return "L4"
    return "L5"

def next_level(level):
    return f"L{min(5, int(level[1:]) + 1)}"

def standard(level):
    return {
        "L1": "五级/初级工",
        "L2": "四级/中级工",
        "L3": "三级/高级工",
        "L4": "二级/技师",
        "L5": "一级/高级技师",
    }[level]

def extract_wrong(role, index):
    if any(x in role for x in ["继电保护", "母线保护", "继保", "定值"]):
        group = WRONG_QUESTIONS["保护"]
    elif any(x in role for x in ["试验", "油务", "SF6", "避雷器", "接地网", "互感器"]):
        group = WRONG_QUESTIONS["试验"]
    elif any(x in role for x in ["值班", "巡视", "防误", "运行", "站用电", "低压", "消防"]):
        group = WRONG_QUESTIONS["运行"]
    else:
        group = WRONG_QUESTIONS["通用"]
    return [pick(group, index), pick(group, index + 1)]

def build_case(i):
    profile = ROLE_PROFILES[i % len(ROLE_PROFILES)]
    role, skills, deps, scenarios, safety = profile
    scenario = pick(scenarios, i // len(ROLE_PROFILES))
    query = QUERY_TYPES[i % len(QUERY_TYPES)]
    tenure = 1 + (i * 7) % 15
    current = level_for_tenure(tenure)
    required_gap = 1 if i % 4 else 2
    job_required = f"L{min(5, int(current[1:]) + required_gap)}"
    future_required = f"L{min(5, int(job_required[1:]) + (1 if i % 3 == 0 else 0))}"
    score = 58 + ((i * 11) % 25)
    pass_score = 80 if i % 5 else 85
    team_score = min(92, score + 6 + (i % 8))
    team_hours = round(2.7 + ((i * 3) % 13) / 10, 1)
    planned = round(max(team_hours - 0.1 + (i % 3) * 0.2, 2.5), 1)
    overtime_rate = [0.11, 0.16, 0.24, 0.31, 0.43, 0.57, 0.68][i % 7]
    actual = round(planned * (1 + overtime_rate), 1)
    overtime = round(actual - planned, 1)
    overtime_percent = round(overtime / planned * 100, 1)
    target_hours = round(min(actual, max(team_hours, planned - 0.1)), 1)
    soft_name, soft_behavior = pick(SOFT_POOL, (i * 5) % len(SOFT_POOL))
    safety_type, safety_fact, safety_action = pick(SAFETY_RECORDS, i)
    skill = pick(skills, i)
    blind = pick(skills, i + 1)
    task = pick(skills, i + 2)
    exam_topic = pick(skills, i + 3)
    wrong = extract_wrong(role, i)
    cert_level = current if tenure < 10 else (future_required if i % 4 == 0 else current)
    cert_date = add_days(45 + (i * 13) % 420)
    safety_date = add_days(10 + (i * 7) % 90)
    education = "大专" if i % 4 == 0 else "本科"
    name = NAMES[i]
    mentor = pick(["王建国", "李海峰", "陈志强", "刘晓梅", "赵立新", "周文博"], i)
    mentor_title = pick(["高级技师", "班组长", "技术专责", "安全专责"], i)
    team = f"变电运维中心 / {role[:4]}专项{(i % 4) + 1}班"
    target = f"{skill}达到{future_required}，在{scenario}中承担可授权的关键任务"
    match_current = 61 + (i * 7) % 30
    match_future = 35 + (i * 9) % 50
    score_gap = round(pass_score - score, 1)
    job_gap = int(job_required[1:]) - int(current[1:])
    future_gap = int(future_required[1:]) - int(current[1:])
    mentor_reviews = 2 + i % 5
    wrong_text = "；".join(
        f"错题{n+1}题干：{q}；错误选项：{wrong_opt}；正确答案：{right};知识点：{topic}；错因：{cause}"
        for n, (q, wrong_opt, right, topic, cause) in enumerate(wrong)
    )
    input_text = (
        f"基本信息｜姓名：{name}｜岗位：{role}｜部门/班组：{team}｜工龄：{tenure}年｜入职时间：{2026-tenure}-07-01"
        f"｜学历：{education}｜证书：{role}{cert_level}资格，预计到期日{cert_date}｜安全规程年度合格日期：{safety_date}；"
        f"职业目标｜目标等级：{future_required}｜计划年限：{1 + i % 4}年｜关键任务：{target}；"
        f"师傅评价｜带教师傅：{mentor}（{mentor_title}）｜评价：{skill}基础已具备，但{blind}和{soft_name}会影响{scenario}闭环｜建议：先完成错题归因和授权边界口述，再安排带教验证；"
        f"协作评价｜班组协作分：{75 + i % 20}｜安全意识分：{80 + i % 17}｜责任心分：{78 + i % 19}"
        f"｜班组评语：可以承担常规任务，但复杂场景需要提前报告、双人复核和过程留痕；"
        f"岗位匹配度｜当前岗位匹配度：{match_current}%｜复合型方向匹配度：{match_future}%"
        f"｜说明：当前岗位基础任务完成度尚可，{skill}与{blind}决定向下一等级拓展的速度；"
        f"诊断补充事实｜场景：{scenario}｜技能树盲区：{blind}｜软技能短板：{soft_name}"
        f"｜可观察行为基线：{soft_behavior}｜考试与错题：{exam_topic}考试{score}分，合格线{pass_score}分；{wrong_text}"
        f"｜实操任务：{task}计划{planned}小时，实际{actual}小时｜安全记录：{safety_type}；{safety_fact}"
        f"｜用户查询：{query}。请基于全部档案生成个性化诊断和学习提升方案。"
    )
    core_action = (
        f"围绕{exam_topic}错题逐题归因，连续3天每天完成2道同类题；"
        f"在{scenario}中完成2次{task}分段计时；"
        f"每次作业前口述授权范围、停止条件和升级对象；"
        f"现场动作必须满足{safety_action}，验收为模拟考≥80分、师傅复核记录不少于2次。"
    )
    secondary_action = (
        f"先核对{deps[0]}，再由师傅带教{deps[1]}和{deps[2]}各1次，"
        f"提交1份{scenario}复盘单，至少包含3项证据、1项风险和1项待复核结论；"
        f"未经授权不得独立进行现场操作。"
    )
    if query in {"安全优先级", "证书授权"} or safety_type not in {"无扣分记录", "安全扣分"}:
        conclusion = (
            f"这份档案的优先级不由分数单独决定：{safety_type}已经把{role}的训练边界前置。"
            f"在{score}分、{task}实际{actual}小时以及{blind}盲区的共同证据下，当前应先恢复合规作业能力，"
            f"再推进{skill}的等级提升；证书到期日{cert_date}前只安排授权范围内的模拟、资料核对和受监护跟班。"
        )
    elif query in {"实操效率", "30天计划"}:
        conclusion = (
            f"{name}的主要瓶颈更像流程节拍而非单纯熟练度：{task}从计划{planned}小时延长到{actual}小时，"
            f"超时率为{overtime_percent}%，同时{exam_topic}只有{score}分。先把准备、执行、记录三段拆开计时，"
            f"再用错题对应的规则校正判断，目标是在不减少安措的前提下回到{target_hours}小时附近。"
        )
    elif query in {"软技能缺失", "岗位匹配"}:
        conclusion = (
            f"班组协作分{75 + i % 20}分并不能掩盖{soft_name}的具体行为缺口：{soft_behavior}尚未稳定发生。"
            f"这会放大{blind}对{scenario}的影响。技术补课只占一半，另一半要用可记录的汇报、复核和闭环动作验收。"
        )
    elif query in {"目标岗位", "复合型路线"}:
        conclusion = (
            f"从{role}到目标{future_required}，真正的跨越不是再堆一门课程，而是把{deps[1]}、{deps[2]}和{scenario}经验串成证据链。"
            f"当前{skill}距离岗位要求差{job_gap}级、距离未来需求差{future_gap}级，宜采用先核心技能、后跨专业协同的路线。"
        )
    else:
        conclusion = (
            f"考试{score}分与合格线{pass_score}分之间的{score_gap}分缺口，集中暴露在{exam_topic}和{blind}；"
            f"结合师傅已完成{mentor_reviews}次复核仍需提示，说明问题是知识规则没有稳定迁移到{scenario}。"
            f"先完成错题归因和受监护任务，再判断是否具备向{job_required}推进的证据。"
        )
    output = {
        "conclusion": conclusion,
        "evidence": [
            f"{exam_topic}考试{score}分，合格线{pass_score}分，分数差{score_gap}分",
            f"{task}计划{planned}小时、实际{actual}小时，超时{overtime}小时，超时率{overtime_percent}%",
            f"技能树盲区为{blind}，软技能短板为{soft_name}，行为基线为{soft_behavior}",
            f"安全记录：{safety_type}；{safety_fact}",
            f"师傅已复核{mentor_reviews}次，当前岗位匹配度{match_current}%",
        ],
        "root_cause": (
            f"核心根因是{blind}的规则知识没有形成稳定的作业检查点，"
            f"叠加{soft_name}导致关键条件未能及时汇报或复核；"
            f"安全记录中的{ safety_type }说明其风险控制习惯仍需通过明确授权、监护和停止条件固化。"
        ),
        "gaps": [
            {
                "priority": "P1",
                "skill": skill,
                "current": current,
                "job_req": job_required,
                "future_req": future_required,
                "job_gap": job_gap,
                "future_gap": future_gap,
                "impact": f"{skill}差距会直接影响{scenario}中的{task}质量、复核通过率和可授权范围。",
                "action": core_action,
            },
            {
                "priority": "P2",
                "skill": blind,
                "current": current,
                "job_req": job_required,
                "future_req": future_required,
                "job_gap": job_gap,
                "future_gap": future_gap,
                "impact": f"{blind}与{soft_name}叠加后，容易出现异常升级滞后、交接证据不足或复盘无法闭环。",
                "action": secondary_action,
            },
        ],
        "learning_path": [
            {
                "step": 1,
                "type": "任务复盘",
                "name": f"{exam_topic}错题逐题归因和{blind}检查点重建",
                "deadline": add_days(12 + i % 8),
                "target": f"错题再测≥80分，{blind}清单覆盖3个关键步骤",
                "reason": f"{score}分与合格线相差{score_gap}分，且错误集中在{exam_topic}规则迁移。",
                "verification": "提交2份错题归因表，师傅抽查每份至少3个因果链，漏项不超过1项。",
            },
            {
                "step": 2,
                "type": "带教",
                "name": f"{scenario}中{task}分段计时与双人复核",
                "deadline": add_days(28 + i % 9),
                "target": f"实际耗时从{actual}小时降至≤{target_hours}小时",
                "reason": f"当前超时率为{overtime_percent}%，需要识别等待、返工和记录耗时，而不是压缩安全步骤。",
                "verification": "连续完成2次分段计时，三段记录齐全，安全措施零删减，师傅签字确认。",
            },
            {
                "step": 3,
                "type": "模拟考",
                "name": f"{skill}授权边界模拟考与{deps[2]}情景问答",
                "deadline": add_days(46 + i % 11),
                "target": f"{skill}达到{job_required}所需的阶段能力",
                "reason": f"当前岗位差距job_gap={job_gap}，未来差距future_gap={future_gap}，需要把等级目标转成可观察步骤。",
                "verification": "模拟考≥80分，口述授权范围、停止条件和升级对象全部正确，不出现越权动作。",
            },
            {
                "step": 4,
                "type": "任务复盘",
                "name": f"{soft_name}行为闭环：{soft_behavior}",
                "deadline": add_days(70 + i % 20),
                "target": f"{soft_name}行为连续达标4次",
                "reason": f"班组反馈和安全记录显示，{soft_name}会放大{blind}带来的现场风险。",
                "verification": "提交4次行为记录，每次含时间、对象、事实、风险和后续动作，班组长抽查通过率≥90%。",
            },
        ],
        "roadmap": [
            {
                "phase": "第1阶段 · 0-2个月",
                "learn": f"先完成{exam_topic}错题归因和{blind}检查点重建，补齐{deps[0]}。",
                "metrics": f"再测成绩≥80分，错题归因覆盖率100%，安全记录中的{ safety_type }不再重复。",
            },
            {
                "phase": "第2阶段 · 2-4个月",
                "learn": f"围绕{scenario}开展{task}分段计时，固定{deps[1]}的准备、执行和记录节拍。",
                "metrics": f"单次耗时≤{target_hours}小时，超时率降至≤15%，安措和复核记录完整率100%。",
            },
            {
                "phase": "第3阶段 · 4-6个月",
                "learn": f"在“有票、许可、验电接地或等效隔离、专人监护”条件下，完成{skill}和{deps[2]}受监护验证。",
                "metrics": "完成2次带教任务，关键步骤口述正确率≥90%，越权和无监护动作记录为0。",
            },
            {
                "phase": "第4阶段 · 6-9个月",
                "learn": f"把{soft_name}行为嵌入{scenario}复盘，形成一份可供下一名员工使用的岗位案例。",
                "metrics": "提交1份完整案例，包含证据、根因、边界、行动和验收结果，班组评审通过。",
            },
        ],
        "level_mapping": {
            "current_level": current,
            "job_required_level": job_required,
            "future_required_level": future_required,
            "national_standard": {
                "L1": "五级/初级工",
                "L2": "四级/中级工",
                "L3": "三级/高级工",
                "L4": "二级/技师",
                "L5": "一级/高级技师",
            },
            "current_standard": standard(current),
            "job_required_standard": standard(job_required),
            "future_required_standard": standard(future_required),
        },
        "skill_dependencies": [
            {"name": deps[0], "type": "前置"},
            {"name": deps[1], "type": "核心"},
            {"name": deps[2], "type": "核心"},
            {"name": deps[3], "type": "验收"},
        ],
        "safety_boundary": f"{safety}当前负例为“{safety_type}”：{safety_fact}；后续任何现场动作必须在工作票或等效许可、风险交底、必要的验电接地或隔离措施、具备资质的监护人到位后实施，未经授权不得独立操作。",
        "quantitative_baseline": {
            "exam_score": score,
            "pass_score": pass_score,
            "score_gap": score_gap,
            "planned_hours": planned,
            "actual_hours": actual,
            "overtime_hours": overtime,
            "overtime_rate": f"{overtime_percent}%",
            "target_hours": target_hours,
            "team_avg_hours": team_hours,
            "team_avg_score": team_score,
            "mentor_review_count": mentor_reviews,
        },
        "personalization_basis": [
            f"岗位={role}",
            f"场景={scenario}",
            f"查询类型={query}",
            f"工龄={tenure}年，当前等级={current}",
            f"job_gap={job_gap}，future_gap={future_gap}",
            f"考试={score}/{pass_score}，错题主题={exam_topic}",
            f"耗时={actual}/{planned}小时，超时率={overtime_percent}%",
            f"安全记录={safety_type}",
            f"软技能={soft_name}，盲区={blind}",
            f"证书到期={cert_date}",
        ],
    }
    return {"instruction": INSTRUCTION, "input": input_text, "output": output}

def validate(rows):
    errors = []
    query_counts = Counter()
    role_counts = Counter()
    names = []
    for i, row in enumerate(rows):
        if set(row) != {"instruction", "input", "output"}:
            errors.append(f"row {i}: top keys")
        if row["instruction"] != INSTRUCTION:
            errors.append(f"row {i}: instruction")
        if not isinstance(row["output"], dict):
            errors.append(f"row {i}: output is not object")
            continue
        required = {"conclusion", "evidence", "root_cause", "gaps", "learning_path", "roadmap", "level_mapping", "skill_dependencies", "safety_boundary", "quantitative_baseline", "personalization_basis"}
        if set(row["output"]) != required:
            errors.append(f"row {i}: output schema")
        info = re.search(r"姓名：(.+?)｜岗位：(.+?)｜", row["input"])
        if not info:
            errors.append(f"row {i}: input identity")
            continue
        name, role = info.group(1), info.group(2)
        names.append(name)
        role_counts[role] += 1
        query_match = re.search(r"｜用户查询：(.+?)。请", row["input"])
        if query_match:
            query_counts[query_match.group(1)] += 1
        out = row["output"]
        baseline = out["quantitative_baseline"]
        expected = round(baseline["actual_hours"] - baseline["planned_hours"], 1)
        if baseline["overtime_hours"] != expected:
            errors.append(f"row {i}: overtime arithmetic")
        if float(str(baseline["overtime_rate"]).rstrip("%")) > 100:
            errors.append(f"row {i}: overtime >100")
        if baseline["team_avg_score"] - baseline["exam_score"] > 15:
            errors.append(f"row {i}: team score gap")
        lm = out["level_mapping"]
        if set(lm["national_standard"]) != {"L1", "L2", "L3", "L4", "L5"}:
            errors.append(f"row {i}: national mapping")
        if len(out["gaps"]) < 2 or {g["priority"] for g in out["gaps"]} != {"P1", "P2"}:
            errors.append(f"row {i}: gaps")
        if len(out["learning_path"]) < 4 or len(out["roadmap"]) < 4:
            errors.append(f"row {i}: path")
        dep_types = {x["type"] for x in out["skill_dependencies"]}
        if not {"前置", "核心", "验收"}.issubset(dep_types):
            errors.append(f"row {i}: dependencies")
    if len(names) != len(set(names)):
        errors.append("duplicate names")
    if max(role_counts.values()) > 4:
        errors.append("role frequency over 4")
    return {
        "count": len(rows),
        "unique_names": len(set(names)),
        "roles": len(role_counts),
        "max_role_count": max(role_counts.values()),
        "query_counts": dict(query_counts),
        "safety_negative_records": sum(1 for row in rows if "安全记录=无扣分记录" not in row["output"]["personalization_basis"]),
        "errors": errors,
    }

def main():
    rows = [build_case(i) for i in range(150)]
    report = validate(rows)
    if report["errors"]:
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    ALL_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    TRAIN_PATH.write_text(json.dumps(rows[:135], ensure_ascii=False, indent=2), encoding="utf-8")
    VAL_PATH.write_text(json.dumps(rows[135:], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"all": str(ALL_PATH), "train": str(TRAIN_PATH), "validation": str(VAL_PATH), "report": report}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
