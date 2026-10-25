import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

SRC = Path(r"C:\Users\admin\Desktop\my_data12.json")
DEST = Path(r"C:\Users\admin\Desktop\my_data12_standard.json")
ISSUES_DEST = Path(r"C:\Users\admin\Desktop\my_data12_issues.json")

INSTRUCTION = "你是专业诊断专家，请根据用户提供的全部个人档案信息，完成个性化诊断，并生成对应的学习提升方案。输出格式严格遵循本项目前端诊断报告的排版规范。"

LEVEL_STD = {
    "L1": "五级/初级工",
    "L2": "四级/中级工",
    "L3": "三级/高级工",
    "L4": "二级/技师",
    "L5": "一级/高级技师",
}

SOFT_POOL = [
    ("主动沟通", "完成2次事实-风险-请求汇报，师傅现场复核并签字"),
    ("技术结论表达", "完成3次结论-依据-边界口述，班组长按清晰度评分"),
    ("带教反馈闭环", "带教后24小时内提交问题清单、修正动作和复盘结论"),
    ("异常升级汇报", "发现异常10分钟内提交读数、趋势、风险和请求支持"),
    ("跨班组协作", "跨班组跟班2次并形成交接清单，双方负责人签认"),
    ("客户沟通技术解释", "向非专业客户解释1个设备风险和1条治理建议并录入纪要"),
    ("现场指挥口令", "按复诵-确认-执行格式完成3次模拟口令演练"),
    ("授权边界沟通", "开工前口述本人授权范围、禁止动作和升级条件"),
    ("需求访谈", "完成1次岗位需求访谈并整理成目标-差距-证据表"),
    ("冲突沟通", "用事实-影响-方案框架处理1次排班或接口冲突演练"),
    ("经验显性化", "把1次隐性经验整理成步骤、风险点和验收口径"),
    ("报告叙述完整性", "提交1份含现象、数据、判断、建议、边界的完整报告"),
    ("跨专业协调", "组织1次继保/高试/运维联合复盘并明确责任界面"),
    ("文档编写规范性", "按模板提交2份缺陷闭环记录，字段完整率100%"),
    ("时间管理", "完成3次三段式计时，准备、执行、记录均有压缩动作"),
    ("任务优先级判断", "对5项任务按安全风险、停电影响、时限排序并说明理由"),
    ("风险预判", "开工前列出3个风险触发条件和对应停止作业条件"),
    ("应急处置决策", "完成1次事故场景桌面推演并说明升级、隔离、恢复步骤"),
]

QUERY_TYPES = ["技术等级差距", "实操效率", "软技能缺失", "证书授权", "安全优先级", "岗位匹配", "目标岗位", "考试错题", "复合型路线", "30天计划"]

ROLE_PROFILES = [
    ("变电运维值班员", ["倒闸操作票复核", "设备巡视缺陷识别", "五防闭锁校验", "异常告警处置"], ["安规两票流程", "一次设备状态量识别", "监控告警分级", "操作票闭环验收"], ["迎峰度夏特巡", "倒闸操作复核", "异常告警闭环"], "仅在当值负责人许可和监护下执行倒闸相关演练，正式操作必须按调度令和两票流程执行。"),
    ("继电保护工", ["软压板逻辑", "定值单核对", "二次回路识图", "故障录波判读"], ["二次图纸识读", "定值单核对", "软压板投退逻辑", "保护出口压板复核"], ["保护定检", "故障录波复盘", "新设备投运"], "不得在未签发工作票情况下触碰运行保护压板，保护试验须由继保负责人授权并双人复核。"),
    ("高压试验员", ["绝缘电阻试验", "介损测试", "SF6微水检测", "避雷器带电检测"], ["仪器校准与放电流程", "绝缘电阻试验", "介损数据判读", "主变油色谱趋势分析验收"], ["预试定检", "事故抢修试验", "设备投运交接"], "高压试验必须在试验负责人许可、围栏和专人监护下实施，接线和放电流程不得省略。"),
    ("设备巡视员", ["红外测温", "设备外观缺陷识别", "巡视路线优化", "异常状态上报"], ["巡视标准化路线", "缺陷分级规则", "红外图谱判读", "巡视记录闭环验收"], ["夜间特巡", "缺陷闭环", "雨雪天气巡视"], "巡视发现异常只做记录、隔离建议和上报，不得擅自扩大工作范围或触碰运行设备。"),
    ("一次设备检修工", ["断路器机构检查", "隔离开关调整", "接地刀闸联锁检查", "检修记录闭环"], ["一次设备结构原理", "检修工器具点检", "机械闭锁逻辑", "机构动作试验验收"], ["断路器检修", "缺陷消除", "停电年检"], "一次设备检修必须在停电、验电、挂接地线和许可手续齐备后按票执行。"),
    ("二次回路检修工", ["端子排核对", "回路绝缘检查", "信号回路排查", "图纸变更闭环"], ["二次图纸识读", "端子编号规则", "回路隔离措施", "信号传动验收"], ["回路消缺", "技改接线", "信号核对"], "二次回路作业必须执行防误碰隔离和监护复核，运行回路不得单人拆接线。"),
    ("变压器检修工", ["油色谱异常判断", "套管检查", "冷却系统巡检", "有载调压机构检查"], ["变压器结构与油务知识", "油色谱趋势分析", "附件状态检查", "检修记录验收"], ["主变检修", "油色谱异常复盘", "迎峰度夏冷却检查"], "变压器附件检修须落实防高坠、防触电和许可边界，涉及有载调压机构动作须负责人监护。"),
    ("开关柜检修员", ["局放检测", "机械特性测试", "柜内闭锁检查", "母线室隐患识别"], ["开关柜结构分区", "局放图谱基础", "机械特性判据", "闭锁状态验收"], ["局放异常", "开关柜年检", "新柜投运"], "开关柜作业须确认隔离、验电、接地和防误闭锁状态，带电间隔不得擅自开柜。"),
    ("通信自动化运维员", ["远动通道排障", "保护信息子站维护", "遥信遥测核对", "时钟同步检查"], ["站控层网络拓扑", "规约点表基础", "网络安全边界", "遥信遥测验收"], ["通道中断", "远动点表核对", "自动化改造"], "自动化配置变更须经审批并做好备份回退，不得越权修改调度侧参数。"),
    ("班组技术员", ["缺陷闭环管理", "作业风险辨识", "技术交底", "复盘报告编写"], ["班组台账规范", "风险分级管控", "作业指导书编制", "复盘报告验收"], ["带教复盘", "缺陷闭环", "月度技术分析"], "技术建议需经班组长或专业负责人确认后执行，风险交底不得替代现场许可和监护。"),
    ("直流系统维护员", ["直流屏告警处置", "蓄电池组核容", "馈线绝缘监测", "充电模块切换"], ["直流系统图识读", "蓄电池试验规程", "馈线绝缘判据", "直流告警闭环验收"], ["直流接地排查", "蓄电池核容", "充电模块故障"], "直流系统异常不得擅自退出保护电源，切换和试验须经直流专业负责人许可。"),
    ("继保调试员", ["保护装置定检", "整组传动试验", "GOOSE链路核对", "保护逻辑调试"], ["保护原理图识读", "试验仪配置", "出口回路隔离", "整组传动验收"], ["新设备投运", "保护升级", "整组传动"], "继保调试涉及出口回路时必须先完成隔离措施和双人核对，调试记录需专业负责人签字。"),
    ("电能质量监测员", ["谐波数据分析", "电压暂降事件判读", "监测装置校验", "治理建议编写"], ["电能质量指标体系", "监测装置接线规则", "用户侧负荷特性", "事件报告验收"], ["客户侧治理", "电压暂降分析", "谐波专项排查"], "监测装置接入须执行二次安全措施并经计量或自动化专业确认，治理建议不得替代客户侧审批。"),
    ("变电土建监督员", ["电缆沟防水检查", "基础沉降观测", "消防通道核查", "土建缺陷闭环"], ["土建设施验收规范", "沉降观测记录", "防水缺陷分级", "整改验收签认"], ["汛期特巡", "土建改造", "缺陷整改"], "土建监督不得代替施工许可和监理签证，进入受限区域须完成安全交底和现场监护。"),
    ("智能巡检数据分析员", ["机器人巡检数据标注", "红外图谱复核", "告警误报过滤", "巡检策略优化"], ["设备点位命名规范", "红外判据", "告警样本标注", "复核结论验收"], ["智能巡检复核", "误报治理", "模型样本整理"], "智能巡检结论只能作为辅助判断，缺陷定级和处置建议必须经人工专业复核。"),
    ("变电消防管理员", ["消防报警处置", "气体灭火系统检查", "消防联动测试", "动火风险核查"], ["消防系统图识读", "气体灭火闭锁条件", "动火票流程", "消防联动验收"], ["消防联动测试", "动火作业监护", "消防缺陷闭环"], "消防联动测试须经运行许可并落实隔离措施，动火相关判断不得替代动火票审批。"),
    ("蓄电池维护员", ["蓄电池内阻测试", "容量核对性放电", "直流系统告警处置", "端电压趋势分析"], ["蓄电池试验规程", "内阻测试接线", "核对性放电流程", "端电压趋势分析验收"], ["核容试验", "端电压异常", "直流屏巡检"], "蓄电池放电试验须在直流专业授权、旁路保障和专人监护下执行，不得擅自退出保护电源。"),
    ("避雷器检修员", ["避雷器泄漏电流检测", "红外异常判断", "在线监测数据核对", "计数器动作分析"], ["避雷器结构原理", "带电检测安全距离", "泄漏电流判据", "在线监测验收"], ["雷雨季特巡", "带电检测", "异常计数分析"], "避雷器带电检测需具备授权并保持规定安全距离，异常判定不得替代停电检修审批。"),
    ("接地网检测员", ["接地电阻测试", "跨步电压风险辨识", "接地引下线检查", "测试点布置"], ["接地系统图纸识读", "测试仪器接线", "安全围栏设置", "接地电阻验收"], ["接地网普测", "雷雨季整改", "扩建接入"], "接地网测试必须办理现场许可并避开雷雨天气，涉及开挖或拆接必须另行审批。"),
    ("隔离开关检修员", ["触头接触状态检查", "机构连杆调整", "分合闸同期检查", "闭锁逻辑核对"], ["隔离开关机械结构", "传动机构润滑点", "五防闭锁逻辑", "分合闸同期验收"], ["隔离开关消缺", "机构调整", "停电年检"], "隔离开关调整必须在停电接地和检修负责人监护下进行，不得越权解除五防闭锁。"),
    ("变压器冷却系统维护员", ["冷却器控制回路检查", "风机油泵切换试验", "温控器校验", "冷却系统缺陷闭环"], ["冷却系统控制逻辑", "温度保护联动关系", "低压控制回路安全", "切换试验验收"], ["迎峰度夏冷却检查", "风机故障", "油泵切换试验"], "冷却系统切换试验须经运行值班许可并设专人监视油温，不得擅自退出主变冷却保护联锁。"),
    ("母线保护检修员", ["母差保护逻辑校验", "CT回路极性核对", "出口回路隔离", "保护定检记录"], ["母差保护原理", "CT二次回路规则", "出口压板管理", "母差保护试验验收"], ["母差定检", "CT回路核对", "保护异常复盘"], "母线保护检修须由继保负责人授权并执行双人复核，出口回路相关操作必须按票隔离。"),
    ("机器人巡检运维员", ["巡检点位配置", "机器人告警复核", "红外图谱标注", "巡检路线维护"], ["机器人巡检系统操作", "设备点位命名规范", "红外缺陷判据", "巡检路线验收"], ["机器人路线优化", "告警复核", "特巡任务配置"], "机器人巡检路线调整需经运维负责人确认，不得覆盖禁行区域，告警结论需人工复核。"),
    ("视频巡检运维员", ["视频点位校核", "图像遮挡识别", "远程巡视记录", "视频告警复核"], ["视频点位台账", "远程巡视标准", "图像质量判据", "告警复核验收"], ["远程巡视", "视频盲区治理", "告警联动"], "视频巡检不得替代现场必要检查，涉及设备状态结论必须由运维人员复核确认。"),
    ("油务化验员", ["油色谱取样", "微水检测", "击穿电压试验", "色谱趋势判断"], ["油样取样规范", "仪器校准流程", "色谱特征气体判据", "化验报告验收"], ["油色谱异常", "主变取样", "投运前化验"], "油样取样和化验必须按作业指导书留样留痕，异常结论需经油务负责人复核。"),
    ("SF6气体检测员", ["SF6微水检测", "气体泄漏检测", "分解物分析", "气瓶安全管理"], ["SF6安全防护", "微水仪校准", "泄漏点定位", "检测报告验收"], ["气体补充", "泄漏排查", "组合电器检测"], "SF6检测必须落实通风、防护和气体回收要求，不得在未确认环境安全时进入低洼区域。"),
    ("有限空间监护员", ["有限空间气体检测", "通风措施确认", "人员进出登记", "应急撤离组织"], ["有限空间作业票", "气体检测仪使用", "通风和监护要求", "撤离条件验收"], ["电缆沟作业", "通风检测", "应急演练"], "有限空间和气体检测必须先完成通风、检测、监护和撤离条件确认。"),
    ("电缆检修员", ["电缆终端检查", "护层接地电流检测", "电缆沟巡视", "局放定位"], ["电缆结构识别", "护层接地原理", "局放定位方法", "检修验收记录"], ["电缆终端消缺", "护层异常", "电缆沟特巡"], "电缆检修必须确认停电、验电和接地，电缆沟内作业按有限空间要求执行。"),
    ("电抗器检修员", ["电抗器声音辨识", "红外测温", "支柱绝缘检查", "振动异常分析"], ["电抗器结构原理", "红外温差判据", "异常声音记录", "缺陷验收闭环"], ["迎峰度夏测温", "异响复盘", "支柱检查"], "电抗器异常检查须保持安全距离，噪声和振动判断需结合红外和历史数据复核。"),
    ("互感器检修员", ["CT绝缘检查", "PT二次回路核对", "互感器油位检查", "极性核对"], ["互感器原理", "二次回路安全", "极性测试方法", "试验报告验收"], ["互感器预试", "二次异常", "投运交接"], "互感器二次回路不得开路或短路误操作，试验接线必须经双人核对。"),
    ("GIS检修员", ["GIS气室压力核对", "局放检测", "隔离接地联锁检查", "密度继电器校验"], ["GIS气室图识读", "局放检测方法", "联锁逻辑", "气室记录验收"], ["GIS年检", "气压异常", "局放排查"], "GIS检修需确认气室边界和联锁状态，气体处理须按环保与安全规程执行。"),
    ("无功补偿装置维护员", ["电容器组巡视", "电抗器检查", "投切逻辑核对", "熔断器状态判断"], ["无功补偿原理", "投切策略", "电容器缺陷判据", "投切试验验收"], ["电容器异常", "投切试验", "迎峰度夏"], "无功补偿装置投切试验须经运行许可并监视电压无功变化，不得擅自改变控制策略。"),
    ("站用电维护员", ["站用变巡视", "低压开关检查", "备自投逻辑核对", "站用电切换演练"], ["站用电系统图", "备自投逻辑", "低压配电安全", "切换演练验收"], ["站用电切换", "低压缺陷", "备自投测试"], "站用电切换演练必须经值班负责人许可，涉及低压回路作业需验电并落实防反送电措施。"),
    ("防误闭锁管理员", ["五防规则维护", "电脑钥匙管理", "闭锁逻辑核对", "解锁流程审查"], ["五防闭锁原理", "设备编码规则", "解锁审批流程", "闭锁逻辑验收"], ["五防规则校核", "钥匙异常", "新间隔投运"], "防误闭锁规则变更必须经审批和模拟验证，严禁以训练名义绕过闭锁。"),
    ("检修计划协调员", ["停电计划编排", "资源冲突识别", "跨班组协调", "检修窗口复盘"], ["设备停电约束", "人员资质矩阵", "风险优先级排序", "计划复盘验收"], ["月度检修计划", "资源冲突", "跨专业窗口协调"], "检修计划只能提出排程建议，涉及停电范围和作业许可须由相应负责人审批。"),
    ("应急抢修协调员", ["故障信息汇总", "抢修资源调度", "现场风险研判", "恢复送电复盘"], ["应急预案流程", "故障分级标准", "资源调度清单", "复盘报告验收"], ["事故抢修", "应急演练", "恢复送电复盘"], "应急协调不得替代现场指挥授权，抢修动作必须服从调度和现场负责人命令。"),
    ("培训管理员", ["培训需求分析", "考试题库维护", "带教计划跟踪", "培训效果评估"], ["岗位能力矩阵", "题库标签规则", "带教记录规范", "效果评估验收"], ["月度培训", "补考组织", "带教复盘"], "培训建议不得替代岗位授权，涉及人员上岗资格需按制度审批和留痕。"),
    ("安全稽查员", ["两票稽查", "违章风险识别", "现场安全观察", "整改闭环跟踪"], ["安规条款", "两票判据", "违章分类", "整改闭环验收"], ["现场稽查", "违章复盘", "整改验收"], "安全稽查只形成问题和整改建议，处罚和停工决定须按管理权限执行。"),
    ("材料备品管理员", ["备品台账核对", "安全库存测算", "领用记录追踪", "备品质量验收"], ["设备型号识别", "库存阈值规则", "领用审批流程", "质量验收记录"], ["抢修备品准备", "库存盘点", "到货验收"], "备品替代建议须经专业负责人确认，不得擅自以非同型号备品投入现场。"),
    ("工器具管理员", ["绝缘工器具试验周期核对", "领用归还登记", "缺陷工器具隔离", "试验标签检查"], ["工器具试验规程", "标签有效期识别", "台账管理", "隔离验收"], ["工器具盘点", "试验到期预警", "缺陷隔离"], "试验超期或缺陷工器具必须隔离停用，不得因抢修压力临时放行。"),
    ("在线监测运维员", ["在线监测告警复核", "传感器状态检查", "数据漂移判断", "趋势报告编写"], ["在线监测系统架构", "传感器校验规则", "趋势分析方法", "告警闭环验收"], ["告警复核", "传感器漂移", "趋势月报"], "在线监测告警不得直接作为停运依据，处置建议需结合现场复核和专业判断。"),
    ("继保定值管理员", ["定值单版本管理", "定值核对", "定值变更留痕", "定值差异复核"], ["定值单结构", "版本控制规则", "保护定值原理", "变更记录验收"], ["定值变更", "版本核对", "投运前复核"], "定值变更必须按审批流程执行，训练中的核对结果不得替代正式定值通知单。"),
    ("运行方式分析员", ["运行方式校核", "负荷潮流分析", "风险预案编制", "方式变更复盘"], ["电网运行方式基础", "负荷数据分析", "风险校核规则", "方式报告验收"], ["方式变更", "迎峰度夏", "负荷异常"], "运行方式建议须经调度和专业负责人审核，不得直接改变现场运行状态。"),
    ("低压配电维护员", ["低压柜巡视", "开关温升检查", "配电回路核对", "漏保测试"], ["低压配电图", "漏保试验方法", "温升判据", "回路验收记录"], ["低压消缺", "漏保测试", "配电柜特巡"], "低压配电作业须验电并防止反送电，涉及带电部位必须按安全距离和监护要求执行。"),
    ("无人机巡检员", ["航线规划", "设备影像识别", "红外航拍复核", "飞行安全检查"], ["无人机飞行规范", "航线风险识别", "影像缺陷判据", "巡检成果验收"], ["无人机特巡", "影像缺陷识别", "灾后巡检"], "无人机巡检必须遵守空域、天气和站内安全要求，影像结论需由专业人员复核。"),
    ("数字化台账管理员", ["设备台账核对", "缺陷数据清洗", "检修记录关联", "标签体系维护"], ["设备编码规则", "缺陷字段规范", "检修记录映射", "台账一致性验收"], ["台账治理", "数据质量核查", "缺陷关联分析"], "台账修正须保留变更记录和审批来源，不得用推测数据覆盖现场原始记录。"),
    ("环境监测管理员", ["噪声监测", "油污风险识别", "排水系统检查", "环保记录闭环"], ["环保监测规范", "站内排水路径", "油污应急处置", "环保记录验收"], ["环保特巡", "油污处置", "噪声投诉复核"], "环保异常处置须按站内应急预案和属地要求上报，现场清理不得越过安全隔离范围。"),
    ("新员工带教员", ["带教计划拆解", "实操观察记录", "错题复盘", "阶段评价"], ["岗位能力矩阵", "带教记录模板", "阶段评价规则", "带教成效验收"], ["新员工带教", "补考复盘", "实操观察"], "带教安排不得突破学员授权等级，现场演练必须有具备资质人员监护。"),
    ("技术档案管理员", ["图纸版本核对", "试验报告归档", "检修记录追溯", "档案借阅管理"], ["档案编码规则", "图纸版本管理", "报告归档要求", "可追溯性验收"], ["档案治理", "图纸变更", "报告追溯"], "档案修订必须依据已审批文件和现场验收记录，不得用口头信息替代正式版本。"),
]

def clean_text(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\\n", " ").replace("\\t", " ")).strip()

def parse_output(row):
    out = row.get("output", "")
    if isinstance(out, str):
        return json.loads(out)
    return out

def parse_input(text):
    s = clean_text(text)
    def one(pattern, default=""):
        m = re.search(pattern, s)
        return clean_text(m.group(1)) if m else default
    name_role = one(r"姓名 / 岗位：(.+?) 部门 / 班组：", "未知员工 · 变电运维值班员")
    if " · " in name_role:
        name, role = [clean_text(x) for x in name_role.split(" · ", 1)]
    elif " / " in name_role:
        name, role = [clean_text(x) for x in name_role.split(" / ", 1)]
    else:
        name, role = name_role, "变电运维值班员"
    work = re.search(r"实操任务：(.+?)计划\s*(\d+(?:\.\d+)?)\s*小时，实际\s*(\d+(?:\.\d+)?)\s*小时", s)
    exam = re.search(r"考试与错题：(.+?)考试\s*(\d+(?:\.\d+)?)\s*分，合格线\s*(\d+(?:\.\d+)?)\s*分", s)
    soft = one(r"软技能短板：(.+?) 考试与错题：", "")
    return {"name": name, "role": role, "soft": soft, "planned": float(work.group(2)) if work else None, "actual": float(work.group(3)) if work else None, "score": float(exam.group(2)) if exam else None}

def scan_source(rows):
    names, roles, softs, safeties = [], [], [], []
    overtime_bad = []
    level_missing_l5 = []
    avg_score_high = []
    for i, row in enumerate(rows):
        info = parse_input(row.get("input", ""))
        names.append(info["name"])
        roles.append(info["role"])
        softs.append(info["soft"])
        try:
            out = parse_output(row)
        except Exception as exc:
            continue
        safeties.append(clean_text(out.get("safety_boundary", "")))
        if info["planned"] and info["actual"]:
            rate = (info["actual"] - info["planned"]) / info["planned"]
            if rate > 1:
                overtime_bad.append({"index": i, "name": info["name"], "role": info["role"], "overtime_rate": round(rate * 100, 1)})
        lm = out.get("level_mapping", {}) if isinstance(out, dict) else {}
        ns = lm.get("national_standard", {}) if isinstance(lm, dict) else {}
        if "L5" not in ns:
            level_missing_l5.append(i)
        qb = out.get("quantitative_baseline", {}) if isinstance(out, dict) else {}
        if info["score"] is not None and isinstance(qb.get("team_avg_score"), (int, float)) and qb["team_avg_score"] - info["score"] > 15:
            avg_score_high.append({"index": i, "name": info["name"], "score": info["score"], "team_avg_score": qb["team_avg_score"]})
    duplicate_names = {k: v for k, v in Counter(names).items() if v > 1}
    role_counts = Counter(roles)
    high_roles = dict(role_counts.most_common(20))
    consecutive_role_runs = []
    last, run = None, 0
    for idx, role in enumerate(roles):
        run = run + 1 if role == last else 1
        if run > 1:
            consecutive_role_runs.append({"index": idx, "role": role, "run": run})
        last = role
    recent_soft_repeats = []
    for i in range(len(softs)):
        window = [x for x in softs[max(0, i-9):i+1] if x]
        repeated = [k for k, v in Counter(window).items() if v > 1]
        if repeated:
            recent_soft_repeats.append({"index": i, "repeated_soft_skills": repeated})
    safety_repeats = {k: v for k, v in Counter(safeties).items() if k and v > 3}
    return {
        "source_count": len(rows),
        "duplicate_names": duplicate_names,
        "role_high_frequency_top20": high_roles,
        "consecutive_role_runs": consecutive_role_runs[:50],
        "recent_10_soft_skill_repeats": recent_soft_repeats[:50],
        "overtime_rate_over_100_percent": overtime_bad,
        "level_mapping_missing_L5_count": len(level_missing_l5),
        "level_mapping_missing_L5_sample_indices": level_missing_l5[:30],
        "team_avg_score_more_than_personal_plus_15": avg_score_high[:50],
        "safety_boundary_repeated_over_3": safety_repeats,
    }

def dadd(days):
    return (date(2026, 9, 30) + timedelta(days=days)).isoformat()

def pick(items, i):
    return items[i % len(items)]

def name_for(i):
    surnames = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
    given = ["晨", "悦", "明", "岚", "宁", "旭", "颖", "峰", "琳", "航", "睿", "彤", "磊", "洁", "涛", "琪", "楠", "博", "静", "凯", "璐", "鑫", "洋", "敏", "昊", "婷", "森", "丹", "威", "然"]
    return surnames[i % len(surnames)] + given[(i * 7) % len(given)] + ("" if i < len(surnames) else str(i // len(surnames)))

def make_case(i, role_profile, role_case_no):
    role, skills, deps, scenarios, safety = role_profile
    scenario = pick(scenarios, i + role_case_no)
    soft, behavior = SOFT_POOL[i % len(SOFT_POOL)]
    current = ["L1", "L2", "L2", "L3", "L3", "L4"][i % 6]
    job_req = ["L3", "L3", "L4", "L4", "L5", "L5"][i % 6]
    future_req = ["L3", "L4", "L4", "L5", "L5", "L5"][i % 6]
    if i in (7, 41, 88, 119):
        job_req = future_req = "L5"
        current = "L4"
    score = 55 + ((i * 7 + role_case_no * 3) % 24)
    pass_score = 80 if i % 8 else 85
    team_avg_score = min(88, score + 5 + (i % 10))
    team_avg_hours = round(2.8 + (i % 8) * 0.35 + role_case_no * 0.1, 1)
    planned = round(max(team_avg_hours - 0.2, 2.5), 1)
    overtime_rate = [0.12, 0.18, 0.25, 0.32, 0.45, 0.58, 0.72][i % 7]
    actual = round(planned * (1 + overtime_rate), 1)
    overtime = round(actual - planned, 1)
    real_rate = round(overtime / planned * 100, 1)
    skill = pick(skills, i)
    blind = pick(skills, i + 1)
    task = pick(skills, i + 2)
    exam_topic = pick(skills, i + 3)
    cert_level = ["L1", "L2", "L3", "L4", "L5"][i % 5]
    cert_date = dadd(90 + (i * 11) % 420)
    tenure = 1 + (i * 5) % 15
    edu = "本科" if i % 3 else "大专"
    team = f"变电运维中心 / {role[:4]}{role_case_no + 1}班"
    query = QUERY_TYPES[i % len(QUERY_TYPES)]
    target = f"{skill}：目标 {future_req} · {1 + i % 3} 年内；{scenario}中承担关键任务"
    name = name_for(i)
    mentor_count = 2 + i % 4
    match_now = 60 + (i * 3) % 29
    match_target = 38 + (i * 5) % 45
    input_text = (
        f"基本信息 姓名 / 岗位：{name} · {role} 部门 / 班组：{team} 工龄 / 入职时间：{tenure} 年 · {2026 - tenure}-07-01 "
        f"学历：{edu} · 电气工程及其自动化 证书：{role} {cert_level} 资格（{cert_date}）；安全规程年度合格（{dadd(30 + i % 120)}） "
        f"职业目标 {target} 师傅评价 带教师傅：{pick(['王建国','李海峰','陈志强','刘晓梅','赵立新'], i)} · {pick(['高级技师','班组长','技术专责','安全专责'], i)} "
        f"评价：{skill}当前 {current}，岗位要求 {job_req}；建议先补{blind}，再在{scenario}中跟班验证 协作评价 "
        f"班组协作：{76 + i % 18} 分 安全意识：{82 + i % 14} 分 责任心：{80 + i % 16} 分 班组评价：{scenario}可参与，但{soft}影响任务闭环和复盘效率 "
        f"岗位匹配度 {role}：{match_now}% 当前岗位说明：基础职责可完成，但{skill}影响复杂任务独立闭环 {skill}复合型方向：{match_target}% 目标岗位说明：需补齐{skill} {job_req} 与{blind} "
        f"诊断补充事实 技能树盲区：{blind} 软技能短板：{soft} 可观察行为：{behavior} 考试与错题：{exam_topic}考试 {score} 分，合格线 {pass_score} 分 "
        f"实操任务：{task}计划 {planned} 小时，实际 {actual} 小时 安全记录：无安全一票否决记录 用户查询（{query}）：请结合岗位、证书、分数、耗时和软技能短板生成个性化诊断与学习方案。"
    )
    gap_level = int(job_req[1]) - int(current[1])
    score_gap = round(pass_score - score, 1)
    target_hours = round(max(planned, min(actual - 0.2, team_avg_hours + 0.4)), 1)
    action1 = f"{exam_topic}错题逐题归因→完成2份{skill}核对记录→{task}三段式计时复盘→{behavior}；涉及现场动作时遵守：{safety}"
    action2 = f"{deps[0]}清单复核→{deps[1]}带教2次→{deps[2]}情景演练→{deps[-1]}，所有现场环节需在授权和监护下完成"
    output = {
        "conclusion": f"{name}当前岗位为{role}，{skill}为{current}而岗位要求{job_req}、未来需求{future_req}，等级差为{gap_level}级；{exam_topic}考试{score}分，距合格线{pass_score}分差{score_gap}分；{task}计划{planned}小时、实际{actual}小时，超时{overtime}小时，超时率{real_rate}%；软技能短板为{soft}，技能树盲区为{blind}。建议在证书到期日{cert_date}前完成前3步训练，现场类动作只能在授权、许可和监护条件满足时执行。",
        "gaps": [
            {"priority": "P1", "skill": skill, "current": current, "job_req": job_req, "future_req": future_req, "impact": f"{skill}等级不足会影响{scenario}中的{task}质量、时限和复核通过率。", "action": action1},
            {"priority": "P2", "skill": blind, "current": current, "job_req": job_req if gap_level <= 1 else f"L{int(current[1]) + 1}", "future_req": future_req, "impact": f"{blind}盲区叠加{soft}，容易造成跨专业交接、记录闭环或异常升级不及时。", "action": action2},
        ],
        "learning_path": [
            {"step": 1, "type": "任务复盘", "name": f"{exam_topic}错题逐题归因与{blind}知识点索引", "deadline": dadd(14 + i % 5), "target": f"{skill}→{current if gap_level == 0 else 'L' + str(int(current[1]) + 1)}", "reason": f"考试差{score_gap}分，先定位错题对应的{blind}和{exam_topic}薄弱点。"},
            {"step": 2, "type": "带教", "name": f"{scenario}下{task}分段计时跟班（计划{planned}小时，目标≤{target_hours}小时）", "deadline": dadd(35 + i % 8), "target": f"{task}效率达标", "reason": f"实际耗时{actual}小时，超时率{real_rate}%，需要拆分准备、执行、记录三段。"},
            {"step": 3, "type": "模拟考", "name": f"{skill}授权边界内模拟考与{deps[2]}情景问答", "deadline": dadd(58 + i % 10), "target": f"考试≥80分，{skill}达到{job_req}", "reason": "把理论、岗位技能和安全边界放在同一次验收中，避免只会答题不会按规程执行。"},
            {"step": 4, "type": "任务复盘", "name": f"{soft}可观察行为训练：{behavior}", "deadline": dadd(82 + i % 18), "target": f"{soft}改善并支撑{target}", "reason": f"班组评价指出{soft}影响{scenario}闭环，需要用可观察行为验收。"},
        ],
        "roadmap": [
            {"phase": "第1阶段 · 0-2个月", "learn": f"围绕{exam_topic}做错题逐题归因，并把{blind}整理成岗位化核对清单。", "metrics": "模拟考≥80分，错题归因表覆盖率100%，师傅复核1次通过。"},
            {"phase": "第2阶段 · 2-4个月", "learn": f"在{scenario}中开展{task}分段计时复盘，重点压缩超时{overtime}小时中的等待和返工。", "metrics": f"单次耗时≤{target_hours}小时，三段耗时记录不少于3次。"},
            {"phase": "第3阶段 · 4-6个月", "learn": f"在{safety}的边界下完成{deps[1]}带教和{deps[2]}情景演练。", "metrics": "跟班2次，关键步骤口述正确率≥90%，无越权操作表述。"},
            {"phase": "第4阶段 · 6-9个月", "learn": f"结合{soft}完成{behavior}，形成1份{scenario}复盘样例。", "metrics": "复盘样例通过班组长审核，行动项按期关闭率100%。"},
        ],
        "level_mapping": {"current_level": current, "job_required_level": job_req, "future_required_level": future_req, "national_standard": LEVEL_STD, "current_standard": LEVEL_STD[current], "job_required_standard": LEVEL_STD[job_req], "future_required_standard": LEVEL_STD[future_req]},
        "skill_dependencies": [
            {"name": deps[0], "type": "前置"},
            {"name": deps[1], "type": "核心"},
            {"name": deps[2], "type": "核心"},
            {"name": deps[3], "type": "验收"},
        ],
        "safety_boundary": safety,
        "quantitative_baseline": {"exam_score": score, "pass_score": pass_score, "score_gap": score_gap, "planned_hours": planned, "actual_hours": actual, "overtime_hours": overtime, "overtime_rate": f"{real_rate}%", "target_hours": target_hours, "team_avg_hours": team_avg_hours, "team_avg_score": team_avg_score, "mentor_review_count": mentor_count},
        "personalization_basis": [f"岗位={role}", f"场景={scenario}", f"考试={score}/{pass_score}", f"耗时={actual}/{planned}小时", f"软技能={soft}", f"盲区={blind}", f"证书到期={cert_date}"],
    }
    return {"instruction": INSTRUCTION, "input": input_text, "output": json.dumps(output, ensure_ascii=False, separators=(",", ":"))}

def generate_dataset(count=130):
    rows = []
    role_counts = Counter()
    role_case = defaultdict(int)
    role_index = 0
    while len(rows) < count:
        profile = ROLE_PROFILES[role_index % len(ROLE_PROFILES)]
        role = profile[0]
        role_index += 1
        if role_counts[role] >= 3:
            continue
        row = make_case(len(rows), profile, role_case[role])
        role_counts[role] += 1
        role_case[role] += 1
        rows.append(row)
    return rows

def validate(rows):
    errors = []
    names = []
    roles = []
    softs = []
    safety_counts = Counter()
    for i, row in enumerate(rows):
        if set(row) != {"instruction", "input", "output"}:
            errors.append(f"row {i} top keys invalid")
        if not all(isinstance(row[k], str) for k in ["instruction", "input", "output"]):
            errors.append(f"row {i} fields not string")
        info = parse_input(row["input"])
        names.append(info["name"])
        roles.append(info["role"])
        softs.append(info["soft"])
        out = json.loads(row["output"])
        required = ["conclusion", "gaps", "learning_path", "roadmap", "level_mapping", "skill_dependencies", "safety_boundary", "quantitative_baseline", "personalization_basis"]
        missing = [k for k in required if k not in out]
        if missing:
            errors.append(f"row {i} missing {missing}")
        if set(out["level_mapping"].get("national_standard", {})) != set(LEVEL_STD):
            errors.append(f"row {i} level mapping incomplete")
        qb = out["quantitative_baseline"]
        expected_overtime = round(qb["actual_hours"] - qb["planned_hours"], 1)
        if qb["overtime_hours"] != expected_overtime:
            errors.append(f"row {i} overtime mismatch")
        if float(str(qb["overtime_rate"]).rstrip("%")) > 100:
            errors.append(f"row {i} overtime rate over 100")
        if qb["team_avg_score"] - qb["exam_score"] > 15:
            errors.append(f"row {i} team score too high")
        if any(d.get("type") not in ["前置", "核心", "验收"] for d in out["skill_dependencies"]):
            errors.append(f"row {i} dependency type invalid")
        safety_counts[out["safety_boundary"]] += 1
        if i >= 2 and roles[i] == roles[i-1] == roles[i-2]:
            errors.append(f"row {i} role consecutive over 2")
        if softs[i] in softs[max(0, i-9):i]:
            errors.append(f"row {i} soft repeated in recent 10")
    dup_names = [k for k, v in Counter(names).items() if v > 1]
    if dup_names:
        errors.append(f"duplicate names {dup_names[:5]}")
    role_over = {k: v for k, v in Counter(roles).items() if v > 3}
    if role_over:
        errors.append(f"role over 3 {role_over}")
    safety_over = {k: v for k, v in safety_counts.items() if v > 3}
    if safety_over:
        errors.append(f"safety repeated over 3 {list(safety_over.items())[:5]}")
    return {"count": len(rows), "names": len(set(names)), "roles": len(set(roles)), "soft_types": len(set(softs)), "role_max_count": max(Counter(roles).values()), "safety_max_count": max(safety_counts.values()), "errors": errors[:30], "error_count": len(errors)}

def main():
    source = json.loads(SRC.read_text(encoding="utf-8-sig"))
    issues = scan_source(source)
    ISSUES_DEST.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = generate_dataset(130)
    report = validate(rows)
    if report["errors"]:
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    DEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"issues_file": str(ISSUES_DEST), "output_file": str(DEST), "source_issues": issues, "validation": report}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
