SET NAMES utf8mb4;
-- 后台展示数据集：老总 / 管理员 / 班组页面的维护清单与口径数据
-- 原 MVP 这些数据写在后端 Java 常量里（内存态），现全部落到 MySQL，后端只从库里读。
USE train_system;


-- ===== 角色与用户 =====
INSERT INTO role (code, name, scope, modules, members, note, sort_no) VALUES
  ('EMPLOYEE', '员工', 'PERSONAL', 8, 76, '只能看本人完整能力画像、记忆展示、学习建议与本人实操任务', 1),
  ('TEAM_LEAD', '组长（员工）', 'PERSONAL + TEAM', 9, 9, '员工全部板块 + 班组报告填报（每次实操活动必须上传报告）', 2),
  ('EXECUTIVE', '公司上级（老总）', 'COMPANY', 4, 1, '全公司人才驾驶舱、技能矩阵、培训看板与运行诊断 Agent；授权高管可加账号', 3),
  ('ADMIN', '系统管理员', 'PLATFORM', 4, 1, '只管理平台数据与配置，看不到员工个人页面与老总页面', 4)
  ON DUPLICATE KEY UPDATE name=VALUES(name), scope=VALUES(scope), modules=VALUES(modules), members=VALUES(members), note=VALUES(note), sort_no=VALUES(sort_no);
INSERT INTO app_user (id, username, display_name, password_hash, role_code, role_name, position, team, org, page_scope, status, last_login) VALUES
  (1, 'zhangwei', '张伟', '', 'EMPLOYEE', '员工', '变电运维值班员', '变电运维一班', '变电运维中心', 'PERSONAL', 'ACTIVE', '2026-09-19 16:30'),
  (2, 'limin', '李民', '', 'TEAM_LEAD', '组长（员工）', '变电运维一班班组长', '变电运维一班', '变电运维中心', 'PERSONAL + TEAM', 'ACTIVE', '2026-09-19 20:05'),
  (3, 'wangzong', '王总', '', 'EXECUTIVE', '公司上级（老总）', '分管老总', '中心管理层', '变电运维中心', 'COMPANY', 'ACTIVE', '2026-09-19 19:40'),
  (4, 'admin', '系统管理员', '', 'ADMIN', '系统管理员', '平台管理员', '信息中心', '变电运维中心', 'PLATFORM', 'ACTIVE', '2026-09-20 09:32'),
  (5, 'wangjianguo', '王建国', '', 'EMPLOYEE', '员工', '继电保护主值班员', '继电保护班', '变电运维中心', 'PERSONAL', 'ACTIVE', '2026-09-18 17:20'),
  (6, 'sunqian', '孙倩', '', 'EMPLOYEE', '员工', '值班员', '自动化班', '变电运维中心', 'PERSONAL', 'PENDING', '—')
  ON DUPLICATE KEY UPDATE username=VALUES(username), display_name=VALUES(display_name), password_hash=VALUES(password_hash), role_code=VALUES(role_code), role_name=VALUES(role_name), position=VALUES(position), team=VALUES(team), org=VALUES(org), page_scope=VALUES(page_scope), status=VALUES(status), last_login=VALUES(last_login);

-- ===== 组织与岗位 =====
INSERT INTO org (id, name, org_type, parent, headcount, leader, sort_no) VALUES
  (1, '城东供电公司', '公司', '—', 86, '—', 1),
  (2, '变电运维中心', '中心', '城东供电公司', 86, '王总', 2),
  (3, '变电运维一班', '班组', '变电运维中心', 9, '李民', 3),
  (4, '变电运维二班', '班组', '变电运维中心', 11, '赵敏', 4),
  (5, '变电运维三班', '班组', '变电运维中心', 12, '刘洋', 5),
  (6, '继电保护班', '班组', '变电运维中心', 8, '王建国', 6),
  (7, '电气试验班', '班组', '变电运维中心', 7, '周强', 7),
  (8, '自动化班', '班组', '变电运维中心', 10, '孙倩', 8),
  (9, '综合检修班', '班组', '变电运维中心', 9, '陈磊', 9),
  (10, '带电作业班', '班组', '变电运维中心', 10, '黄涛', 10)
  ON DUPLICATE KEY UPDATE name=VALUES(name), org_type=VALUES(org_type), parent=VALUES(parent), headcount=VALUES(headcount), leader=VALUES(leader), sort_no=VALUES(sort_no);
INSERT INTO position (id, name, org, required_level, key_post, headcount, backup_count, risk, note, sort_no) VALUES
  (1, '继电保护主值班员', '继电保护班', '继电保护 L3', 1, 12, 0, 'HIGH', '关键定值工作依赖 2 名老员工，2 年内退休 2 人', 1),
  (2, '高压试验负责人', '电气试验班', '高压试验 L3', 1, 6, 1, 'HIGH', '全公司仅 1 人 L3，且两年内退休', 2),
  (3, '定值整定校核', '继电保护班', '继电保护 L3 + 故障录波 L2', 1, 8, 1, 'MEDIUM', '校核需双人复核，暂停 1 人即压排队', 3),
  (4, '故障录波分析', '自动化班', '故障录波 L2', 1, 8, 2, 'LOW', '录波分析有 2 名备份', 4),
  (5, '安全监护', '安全监察班', '安全规程 L3', 1, 10, 8, 'LOW', '安全监护备份充足', 5),
  (6, '变电运维值班员', '变电运维一 / 二 / 三班', '倒闸操作 L2 + 继电保护 L1', 0, 32, 8, 'MEDIUM', '倒闸操作已全员达标，继保待补', 6)
  ON DUPLICATE KEY UPDATE name=VALUES(name), org=VALUES(org), required_level=VALUES(required_level), key_post=VALUES(key_post), headcount=VALUES(headcount), backup_count=VALUES(backup_count), risk=VALUES(risk), note=VALUES(note), sort_no=VALUES(sort_no);
INSERT INTO permission_matrix (id, module, employee, team_lead, executive, admin, note, sort_no) VALUES
  (1, '个人能力画像', '本人', '本人', '—', '—', '员工与组长只能看本人，老总与管理员不可见', 1),
  (2, '班组报告', '查看', '填报 + 查看', '—', '—', '只有组长有填报权（POST /tasks/**）', 2),
  (3, '公司总览 / 技能矩阵 / 培训看板 / 运行诊断', '—', '—', '查看', '—', '/exec/** 仅公司上级', 3),
  (4, '平台数据 / 员工档案 / 考试与试卷', '—', '—', '—', '维护', '/admin/** 仅系统管理员', 4),
  (5, '技能 / 课程 / 题库 / 资料审核', '—', '—', '—', '维护 + 审核', '上传资料经 Agent 识别后由管理员审核入库', 5),
  (6, '审计与留痕', '—', '—', '—', '查看 + 清除', '登录 / 修改 / 审批 / 决策 / 执行 / 回滚，可按时间与类别搜索', 6)
  ON DUPLICATE KEY UPDATE module=VALUES(module), employee=VALUES(employee), team_lead=VALUES(team_lead), executive=VALUES(executive), admin=VALUES(admin), note=VALUES(note), sort_no=VALUES(sort_no);

-- ===== 技能 / 标准依据 =====
INSERT INTO skill (code, name, levels, course_count, requirement_count, note, sort_no) VALUES
  ('SK-REL', '继电保护', 'L0 未入门 / L1 初级 / L2 中级 / L3 高级', 3, 4, '关键技能，L3 决定定值类工作能否独立开展', 1),
  ('SK-SWITCH', '倒闸操作', 'L0 / L1 / L2 / L3', 1, 3, '全员达标项，L3 可带教与监护', 2),
  ('SK-HV', '高压试验', 'L0 / L1 / L2 / L3', 2, 3, '外委依赖高，是复合型人才第二技能首选', 3),
  ('SK-WAVE', '故障录波', 'L0 / L1 / L2 / L3', 1, 2, '事故复盘能力，L2 可独立分析原因', 4),
  ('SK-SAFE', '安全规程', '不合格 / 合格（一票否决）', 2, 3, '不合格一票否决，需当月闭环', 5)
  ON DUPLICATE KEY UPDATE name=VALUES(name), levels=VALUES(levels), course_count=VALUES(course_count), requirement_count=VALUES(requirement_count), note=VALUES(note), sort_no=VALUES(sort_no);
INSERT INTO standard_source (id, source, source_url, fetched_at, note) VALUES
  (1, '国家标准全文公开系统（国家市场监督管理总局）', 'https://openstd.samr.gov.cn/bzgk/gb/std_list', '2026-09-19', '标准号、名称、状态与发布/实施日期均取自国家市场监督管理总局「国家标准全文公开系统」查询结果，链接为该系统的标准详情页，可点开核对。')
  ON DUPLICATE KEY UPDATE source=VALUES(source), source_url=VALUES(source_url), fetched_at=VALUES(fetched_at), note=VALUES(note);
INSERT INTO standard_ref (std_no, name, status, published, implemented, detail_url, sort_no) VALUES
  ('GB 26860-2011', '电力安全工作规程 发电厂和变电站电气部分', '现行', '2020-12-14', '2012-06-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=A42F6AA478EEC5C7F8C9E1745C9204E6', 1),
  ('GB/T 14285-2023', '继电保护和安全自动装置技术规程', '现行', '2023-11-27', '2024-03-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0F1C15A59731267D3A756D6AFBB32841', 2),
  ('GB/T 40599-2021', '继电保护及安全自动装置在线监视与分析技术规范', '现行', '2021-10-11', '2022-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8FC4D0493F797D161B500AD4DE613DA4', 3),
  ('GB/T 40584-2021', '继电保护整定计算软件及数据技术规范', '现行', '2021-10-11', '2022-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=78304C8B291E0152CA22842D09346F84', 4),
  ('GB/T 45568-2025', '继电保护信息规范', '现行', '2025-04-25', '2025-08-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=BAF2FBE24A61528D4EAC494DBFB27088', 5),
  ('GB/T 7261-2026', '继电保护和安全自动装置基本试验方法', '即将实施', '2026-07-02', '2027-02-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0A5C12F07DE543989ACEA40A87B09FE9', 6),
  ('GB/T 45906.1-2025', '变电站二次系统 第1部分：通用要求', '现行', '2025-08-01', '2026-02-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=30ED28E6A704B887BF73A32C60156C09', 7),
  ('GB/T 45906.5-2025', '变电站二次系统 第5部分：保护控制及相关设备', '现行', '2025-08-01', '2026-02-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8E846A173E7C2AAD567131F9593CE2CF', 8),
  ('GB/T 45906.8-2025', '变电站二次系统 第8部分：电气操作防误', '现行', '2025-08-01', '2026-02-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=EE41626FE56DF4D1F7E6A6A3E1024E93', 9),
  ('GB/T 45906.10-2025', '变电站二次系统 第10部分：试验与检测', '现行', '2025-08-01', '2026-02-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=D588D59E03B68F5F0AED89398FED4E48', 10),
  ('GB/T 16927.1-2011', '高电压试验技术 第1部分：一般定义及试验要求', '现行', '2011-12-30', '2012-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=E39F8AB18D7473E3EF0242BF357E158F', 11),
  ('GB/T 16927.2-2013', '高电压试验技术 第2部分：测量系统', '现行', '2012-12-11', '2013-07-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=27CE4F25FDAA76A32624751261F300A3', 12),
  ('GB/T 16927.3-2010', '高电压试验技术 第3部分: 现场试验的定义及要求', '现行', '2010-11-10', '2011-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=4DC323C0A451B5BCD3C4A253F98CD200', 13),
  ('GB/T 7354-2018', '高电压试验技术 局部放电测量', '现行', '2018-09-17', '2019-04-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=E9ADDD16BFDDB5B5CF5328B15E6EBE4F', 14),
  ('GB/T 2900.19-2022', '电工术语 高电压试验技术和绝缘配合', '现行', '2022-10-14', '2023-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=163A324C2A1AA08033AEC5C103BD22DE', 15),
  ('GB/T 22390.6-2026', '高压直流输电系统控制与保护设备 第6部分：换流站暂态故障录波装置', '现行', '2026-01-28', '2026-08-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=68FDCEA373435B45706128B653DECEAC', 16),
  ('GB 46768-2025', '有限空间作业安全技术规范', '现行', '2025-10-31', '2026-05-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=C26BA1B610497F860D280ACF929D3F7D', 17),
  ('GB/T 40096.6-2024', '就地化继电保护装置技术规范 第6部分：母线保护', '现行', '2024-04-25', '2024-11-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=D1EB2F7470668EF4A5BDC115D3745559', 18),
  ('GB/T 40096.7-2024', '就地化继电保护装置技术规范 第7部分：变压器保护', '现行', '2024-04-25', '2024-11-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=C1558AE3A892BC5E64C884D214A1F086', 19),
  ('GB/T 42150.1-2022', '就地化继电保护装置检测规范 第1部分：通用部分', '现行', '2022-12-30', '2023-07-01', 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=58C83BFF5DD3B47001FF04D0CC229D28', 20)
  ON DUPLICATE KEY UPDATE name=VALUES(name), status=VALUES(status), published=VALUES(published), implemented=VALUES(implemented), detail_url=VALUES(detail_url), sort_no=VALUES(sort_no);
INSERT INTO position_skill_requirement (id, position, skill, required_level, future_level, basis_role, standard_no, sort_no) VALUES
  (1, '继电保护主值班员', '继电保护', 'L3', 'L3', '主依据', 'GB/T 14285-2023', 1),
  (2, '继电保护主值班员', '故障录波', 'L2', 'L2', '主依据', 'GB/T 22390.6-2026', 2),
  (3, '高压试验负责人', '高压试验', 'L3', 'L3', '主依据', 'GB/T 16927.1-2011', 3),
  (4, '定值整定校核', '继电保护', 'L3', 'L3', '主依据', 'GB/T 40584-2021', 4),
  (5, '变电运维值班员', '倒闸操作', 'L2', 'L3', '未来需求依据', 'GB/T 45906.8-2025', 5),
  (6, '变电运维值班员', '继电保护', 'L1', 'L2', '未来需求依据', 'GB/T 45906.5-2025', 6),
  (7, '变电运维值班员', '安全规程', '合格', '合格', '主依据', 'GB 26860-2011', 7),
  (8, '变电运维值班员', '安全规程', '合格', '合格', '作业依据', 'GB 46768-2025', 8)
  ON DUPLICATE KEY UPDATE position=VALUES(position), skill=VALUES(skill), required_level=VALUES(required_level), future_level=VALUES(future_level), basis_role=VALUES(basis_role), standard_no=VALUES(standard_no), sort_no=VALUES(sort_no);

-- ===== 员工技能（技能雷达 + 个人能力硬技能） =====
INSERT INTO employee_skill (username, skill, level, required_level, future_level, level_label, required_label, future_label, state, priority, radar_note, trend, evidence, sort_no) VALUES
  ('zhangwei', '继电保护', 1, 3, 3, 'L1', 'L3', 'L3', '差 2 级', 'HIGH', '继保理论考试 62 分未通过，定值核对需师傅复核，是当前最大缺口', 'UP', '理论考试 62 分未通过，定值核对需师傅复核', 1),
  ('zhangwei', '倒闸操作', 3, 3, 3, 'L3', 'L3', 'L3', '已达标', 'LOW', '实操考核 92 分并取得 L3 资格，保持即可', 'FLAT', '实操考核 92 分，已取得 L3 资格', 2),
  ('zhangwei', '高压试验', 1, 2, 3, 'L1', 'L2', 'L3', '差 1 级', 'MEDIUM', '公司未来需求 L3，先补到 L2，与继保组合成复合型人才', 'UP', '参与 2 次，尚未独立开展', 3),
  ('zhangwei', '故障录波', 1, 2, 2, 'L1', 'L2', 'L2', '差 1 级', '', NULL, 'FLAT', '能读波形，不能独立分析原因', 4)
  ON DUPLICATE KEY UPDATE skill=VALUES(skill), level=VALUES(level), required_level=VALUES(required_level), future_level=VALUES(future_level), level_label=VALUES(level_label), required_label=VALUES(required_label), future_label=VALUES(future_label), state=VALUES(state), priority=VALUES(priority), radar_note=VALUES(radar_note), trend=VALUES(trend), evidence=VALUES(evidence), sort_no=VALUES(sort_no);

-- ===== 课程 / 技能关联 / 题库台账 / 资料台账 =====
INSERT INTO course (code, name, course_type, hours, skill, target_level, status, materials, source_file, reviewed_by, reviewed_at, sort_no) VALUES
  ('C-REL-01', '《软压板逻辑》微课', '线上', 2, '继电保护', 'L2', '已上线', 3, 'SK-REL_软压板逻辑_L2_v1.pdf', NULL, NULL, 1),
  ('C-REL-02', '定值核对 SOP 与实操', '实操', 4, '继电保护', 'L2', '已上线', 2, 'SK-REL_定值核对SOP_L2_v2.pdf', NULL, NULL, 2),
  ('C-SW-01', '倒闸操作标准化作业', '实操', 6, '倒闸操作', 'L3', '已上线', 4, 'SK-SWITCH_倒闸操作标准化作业_L3_v3.pdf', NULL, NULL, 3),
  ('C-HV-01', '高压试验安全规程', '线上', 3, '高压试验', 'L2', '已上线', 2, 'SK-HV_高压试验安全规程_L2_v1.pdf', NULL, NULL, 4),
  ('C-HV-02', 'SF6 微水与气体检测', '实操', 4, '高压试验', 'L2', '待审核', 1, 'SK-HV_SF6微水与气体检测_L2_v1.pdf', NULL, NULL, 5),
  ('C-WAVE-01', '故障录波读图与案例分析', '线上', 3, '故障录波', 'L2', '已上线', 3, 'SK-WAVE_故障录波读图_L2_v2.pdf', NULL, NULL, 6)
  ON DUPLICATE KEY UPDATE name=VALUES(name), course_type=VALUES(course_type), hours=VALUES(hours), skill=VALUES(skill), target_level=VALUES(target_level), status=VALUES(status), materials=VALUES(materials), source_file=VALUES(source_file), reviewed_by=VALUES(reviewed_by), reviewed_at=VALUES(reviewed_at), sort_no=VALUES(sort_no);
INSERT INTO course_skill_link (id, course, skill, target_level, link_type, weight, sort_no) VALUES
  (1, '《软压板逻辑》微课', '继电保护', 'L2', '主技能', '高', 1),
  (2, '定值核对 SOP 与实操', '继电保护', 'L2', '主技能', '高', 2),
  (3, '定值核对 SOP 与实操', '故障录波', 'L1', '辅助技能', '低', 3),
  (4, '倒闸操作标准化作业', '倒闸操作', 'L3', '主技能', '高', 4),
  (5, '高压试验安全规程', '高压试验', 'L1', '准入', '中', 5),
  (6, '高压试验安全规程', '安全规程', '合格', '准入', '高', 6),
  (7, 'SF6 微水与气体检测', '高压试验', 'L2', '主技能', '高', 7),
  (8, '故障录波读图与案例分析', '故障录波', 'L2', '主技能', '高', 8),
  (9, '故障录波读图与案例分析', '继电保护', 'L2', '辅助技能', '中', 9)
  ON DUPLICATE KEY UPDATE course=VALUES(course), skill=VALUES(skill), target_level=VALUES(target_level), link_type=VALUES(link_type), weight=VALUES(weight), sort_no=VALUES(sort_no);
INSERT INTO course_material (code, title, skill, skill_code, target, material_type, file_name, file_type, target_level, version, hours, recognized_items, agent_confidence, agent_note, status, submitted_by, submitted_at, file_url, source, note, stored_result, reviewed_by, reviewed_at, sort_no) VALUES
  ('MAT-001', '软压板逻辑', '继电保护', 'SK-REL', '课程库', '课程资料', 'SK-REL_软压板逻辑_L2_v1.pdf', 'pdf', 'L2', 'v1', 2, 18, 0.9, 'Agent 识别：继电保护 · 软压板逻辑 · L2 · v1，预计 18 个知识章节', '已审核', '系统管理员', '2026-09-16 09:20', 'mysql://train_system/file_object/SK-REL_软压板逻辑_L2_v1.pdf', '系统管理员上传', NULL, '课程库新增课程 C-SK-REL-v1', NULL, NULL, 1),
  ('MAT-002', '定值核对 SOP 图册', '继电保护', 'SK-REL', '课程库', '课程资料', 'SK-REL_定值核对SOP_L2_v2.pdf', 'pdf', 'L2', 'v2', 4, 12, 0.87, 'Agent 识别：继电保护 · 定值核对 SOP 图册 · L2 · v2，预计 12 个知识章节', '待审核', '系统管理员', '2026-09-19 15:12', 'mysql://train_system/file_object/SK-REL_定值核对SOP_L2_v2.pdf', '系统管理员上传', '含 12 步核对流程与常见错误', NULL, NULL, NULL, 2)
  ON DUPLICATE KEY UPDATE title=VALUES(title), skill=VALUES(skill), skill_code=VALUES(skill_code), target=VALUES(target), material_type=VALUES(material_type), file_name=VALUES(file_name), file_type=VALUES(file_type), target_level=VALUES(target_level), version=VALUES(version), hours=VALUES(hours), recognized_items=VALUES(recognized_items), agent_confidence=VALUES(agent_confidence), agent_note=VALUES(agent_note), status=VALUES(status), submitted_by=VALUES(submitted_by), submitted_at=VALUES(submitted_at), file_url=VALUES(file_url), source=VALUES(source), note=VALUES(note), stored_result=VALUES(stored_result), reviewed_by=VALUES(reviewed_by), reviewed_at=VALUES(reviewed_at), sort_no=VALUES(sort_no);
INSERT INTO file_object (id, owner, object_key, file_name, content_type, size_kb) VALUES
  (1, '系统管理员', 'mysql://train_system/file_object/SK-REL_软压板逻辑_L2_v1.pdf', 'SK-REL_软压板逻辑_L2_v1.pdf', 'pdf', 778),
  (2, '系统管理员', 'mysql://train_system/file_object/SK-REL_定值核对SOP_L2_v2.pdf', 'SK-REL_定值核对SOP_L2_v2.pdf', 'pdf', 911)
  ON DUPLICATE KEY UPDATE owner=VALUES(owner), object_key=VALUES(object_key), file_name=VALUES(file_name), content_type=VALUES(content_type), size_kb=VALUES(size_kb);
INSERT INTO question_bank (code, name, skill, questions, types, difficulty, updated_at, used_by, sort_no) VALUES
  ('QB-REL-A', '继保题库 A', '继电保护', 320, '单选 60% / 多选 25% / 判断 15%', '中', '2026-09-18', 3, 1),
  ('QB-SW-V3', '倒闸实操评分表 v3', '倒闸操作', 12, '评分项（含扣分项）', '中', '2026-08-28', 2, 2),
  ('QB-SAFE', '安全规程题库', '安全规程', 210, '单选 70% / 判断 30%', '高', '2026-09-01', 2, 3),
  ('QB-SPACE', '有限空间题库', '安全规程', 86, '单选 50% / 判断 50%', '中', '2026-09-16', 1, 4)
  ON DUPLICATE KEY UPDATE name=VALUES(name), skill=VALUES(skill), questions=VALUES(questions), types=VALUES(types), difficulty=VALUES(difficulty), updated_at=VALUES(updated_at), used_by=VALUES(used_by), sort_no=VALUES(sort_no);
INSERT INTO paper_batch (batch_no, exam_id, exam_name, issued_to, paper_count, issued_at, deadline, collected, status, sort_no) VALUES
  ('PAPER-20260918-02', '4', '有限空间作业专项考试', '变电运维一班', 9, '2026-09-18 14:00', '2026-09-25', 4, '回收中', 1),
  ('PAPER-20260920-03', '3', '高压试验安全规程考试', '电气试验班', 7, '2026-09-20 09:30', '2026-09-30', 0, '已发放', 2)
  ON DUPLICATE KEY UPDATE exam_id=VALUES(exam_id), exam_name=VALUES(exam_name), issued_to=VALUES(issued_to), paper_count=VALUES(paper_count), issued_at=VALUES(issued_at), deadline=VALUES(deadline), collected=VALUES(collected), status=VALUES(status), sort_no=VALUES(sort_no);

-- ===== 审计留痕 =====
INSERT INTO audit_log (id, occurred_at, actor, actor_role, category, action, target, result, ip) VALUES
  (128, '2026-09-20 09:32', '系统管理员', '系统管理员', '修改', '启用考试', '考试 3 · 高压试验安全规程考试', '成功', '10.12.3.8'),
  (127, '2026-09-20 09:10', '李民', '组长（员工）', '修改', '提交实操报告', 'RPT-20260919-0003 · 电缆沟气体检测', '成功', '10.12.7.21'),
  (126, '2026-09-20 08:55', '王总', '公司上级', '访问', '查看运行诊断', '公司运行诊断 Agent', '成功', '10.12.1.5'),
  (125, '2026-09-19 22:14', '张伟', '员工', '访问', '越权访问', '/api/v1/team/reports', '已拒绝（40301）', '10.12.7.33'),
  (124, '2026-09-19 21:40', '系统管理员', '系统管理员', '修改', '修改题库', '继保题库 A（新增 12 题）', '成功', '10.12.3.8'),
  (123, '2026-09-19 20:05', '李民', '组长（员工）', '登录', '登录系统', 'X-Role=TEAM_LEAD', '成功', '10.12.7.21'),
  (122, '2026-09-19 19:42', '系统管理员', '系统管理员', '审批', '审核通过课程', 'C-REL-01 · 《软压板逻辑》微课', '成功', '10.12.3.8'),
  (121, '2026-09-19 19:40', '王总', '公司上级', '决策', '确认组织人才建议', '继电保护 L3 缺口 4 人：转岗 2 + 招聘 2', '成功', '10.12.1.5'),
  (120, '2026-09-19 18:12', '系统管理员', '系统管理员', '执行', '统一开始考试', '考试 3 · 高压试验安全规程考试', '成功', '10.12.3.8'),
  (119, '2026-09-19 17:05', '系统管理员', '系统管理员', '回滚', '撤回试卷批次', 'PAPER-20260918-02（恢复未发放）', '成功', '10.12.3.8'),
  (118, '2026-09-19 16:30', '张伟', '员工', '登录', '登录系统', 'X-Role=EMPLOYEE', '成功', '10.12.7.33'),
  (117, '2026-09-19 15:12', '系统管理员', '系统管理员', '修改', '上传课程资料', 'MAT-002 · 定值核对 SOP 图册', '待审核', '10.12.3.8')
  ON DUPLICATE KEY UPDATE occurred_at=VALUES(occurred_at), actor=VALUES(actor), actor_role=VALUES(actor_role), category=VALUES(category), action=VALUES(action), target=VALUES(target), result=VALUES(result), ip=VALUES(ip);

-- ===== 考试与历史成绩 =====
INSERT INTO exam (exam_id, name, exam_type, skill, pass_score, question_count, duration_minutes, bank, scope, participants, enabled, status, started_at, started_by, ended_at, paper_batches, sort_no) VALUES
  ('1', '继电保护理论考试', '理论', '继电保护', 80, 20, 60, '继保题库 A（320 题）', '变电运维一班 / 二班', 20, 1, '未开始', '—', '—', NULL, 1, 1),
  ('2', '倒闸操作实操考核', '实操', '倒闸操作', 80, 12, 45, '倒闸实操评分表 v3', '全体值班员', 62, 1, '未开始', '—', '—', NULL, 0, 2),
  ('3', '高压试验安全规程考试', '安全', '安全规程', 90, 15, 30, '安全规程题库（210 题）', '电气试验班', 7, 1, '未开始', '—', '—', NULL, 1, 3),
  ('4', '有限空间作业专项考试', '安全', '安全规程', 90, 20, 40, '安全规程题库（有限空间作业专项）', '全体值班员', 62, 0, '未开始', '—', '—', NULL, 1, 4)
  ON DUPLICATE KEY UPDATE name=VALUES(name), exam_type=VALUES(exam_type), skill=VALUES(skill), pass_score=VALUES(pass_score), question_count=VALUES(question_count), duration_minutes=VALUES(duration_minutes), bank=VALUES(bank), scope=VALUES(scope), participants=VALUES(participants), enabled=VALUES(enabled), status=VALUES(status), started_at=VALUES(started_at), started_by=VALUES(started_by), ended_at=VALUES(ended_at), paper_batches=VALUES(paper_batches), sort_no=VALUES(sort_no);
INSERT INTO exam_history (id, username, exam_id, exam_name, score, pass_score, result, submitted_at, wrong_points) VALUES
  (1, 'zhangwei', '1', '继电保护理论考试', 62, 80, 'FAILED', '2026-09-10 10:20', '["软压板与硬压板","定值区切换"]'),
  (2, 'zhangwei', '2', '倒闸操作实操考核', 92, 80, 'PASSED', '2026-08-28 15:40', '[]')
  ON DUPLICATE KEY UPDATE username=VALUES(username), exam_id=VALUES(exam_id), exam_name=VALUES(exam_name), score=VALUES(score), pass_score=VALUES(pass_score), result=VALUES(result), submitted_at=VALUES(submitted_at), wrong_points=VALUES(wrong_points);

-- ===== 学习 / 资源 / 证书 / 任务 =====
INSERT INTO learning_summary (username, month_hours, target_hours, completion, required_done, required_total, streak_days, last_exam_name, last_exam_score, last_exam_pass_score, focus_skill, mentor_sessions) VALUES
  ('zhangwei', 18, 25, 72, 6, 9, 4, '继电保护理论考试', 62, 80, '继电保护', 2)
  ON DUPLICATE KEY UPDATE month_hours=VALUES(month_hours), target_hours=VALUES(target_hours), completion=VALUES(completion), required_done=VALUES(required_done), required_total=VALUES(required_total), streak_days=VALUES(streak_days), last_exam_name=VALUES(last_exam_name), last_exam_score=VALUES(last_exam_score), last_exam_pass_score=VALUES(last_exam_pass_score), focus_skill=VALUES(focus_skill), mentor_sessions=VALUES(mentor_sessions);
INSERT INTO learning_plan (id, username, course_code, course_name, course_type, hours, progress, required, skill, target_level, due_at, sort_no) VALUES
  (1, 'zhangwei', 'PROTECTION_LOGIC', '软压板逻辑', 'ONLINE', 4, 45, 1, '继电保护', 2, '2026-09-30', 1),
  (2, 'zhangwei', 'SETTING_CHECK', '继保定值核对与投退', 'PRACTICE', 8, 20, 1, '继电保护', 3, '2026-10-12', 2),
  (3, 'zhangwei', 'HV_SAFETY', '高压试验安全规程', 'ONLINE', 6, 0, 0, '高压试验', 2, '2026-10-20', 3)
  ON DUPLICATE KEY UPDATE username=VALUES(username), course_code=VALUES(course_code), course_name=VALUES(course_name), course_type=VALUES(course_type), hours=VALUES(hours), progress=VALUES(progress), required=VALUES(required), skill=VALUES(skill), target_level=VALUES(target_level), due_at=VALUES(due_at), sort_no=VALUES(sort_no);
INSERT INTO learning_record (id, username, course_name, progress, hours, studied_at, status, remark, sort_no) VALUES
  (3, 'zhangwei', '软压板逻辑', 45, 1.8, '2026-09-17', 'IN_PROGRESS', '错题回顾：软压板投退顺序', 3),
  (2, 'zhangwei', '继保定值核对与投退', 20, 1.6, '2026-09-15', 'IN_PROGRESS', '跟师傅完成 1 次现场核对', 2),
  (1, 'zhangwei', '安全规程（月度必修）', 100, 2.5, '2026-09-08', 'COMPLETED', '考试成绩合格', 1)
  ON DUPLICATE KEY UPDATE username=VALUES(username), course_name=VALUES(course_name), progress=VALUES(progress), hours=VALUES(hours), studied_at=VALUES(studied_at), status=VALUES(status), remark=VALUES(remark), sort_no=VALUES(sort_no);
INSERT INTO resource_item (id, title, item_type, duration, skill, level, origin, site, match_reason, jump_to, url, sort_no) VALUES
  (1, '《软压板逻辑》微课', '视频', '32 分钟', '继电保护', '入门', '站内', '学习总版', '对应当前重点提升项', 'learning', NULL, 1),
  (2, '定值核对标准作业卡（SOP）', '文档', '8 页', '继电保护', '进阶', '站内', '班组资料库', '实操报告暴露的准备不足', 'tasks', NULL, 2),
  (3, '国家标准全文公开系统 · 继电保护与电气装置标准', '规范', '按需检索', '继电保护', '进阶', '外网', '国家标准全文公开系统', '定值配合与压板逻辑必须对齐现行国标', NULL, 'https://openstd.samr.gov.cn/bzgk/gb/', 3),
  (4, '国家能源局 · 电力安全与行业标准政策', '规范', '按需检索', '安全能力', '入门', '外网', '国家能源局', '安全规程与一票否决条款的权威出处', NULL, 'https://www.nea.gov.cn/', 4),
  (5, '中国电力企业联合会 · 行业标准与技能人才', '规范', '按需检索', '继电保护', '进阶', '外网', '中国电力企业联合会', '技能等级评价口径与 L1-L3 要求参考', NULL, 'https://www.cec.org.cn/', 5),
  (6, '中国大学 MOOC · 电气工程专业课程', '视频', '按课程', '继电保护', '入门', '外网', '中国大学 MOOC', '继保原理与二次回路系统补课', NULL, 'https://www.icourse163.org/category/engineering', 6),
  (7, 'B 站 · 继电保护课程与定值整定讲解', '视频', '按视频', '继电保护', '入门', '外网', '哔哩哔哩', '软压板逻辑可视化讲解，适合入门补课', NULL, 'https://search.bilibili.com/all?keyword=%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4', 7),
  (8, '中国知网 · 继电保护与故障录波论文', '论文', '按需检索', '故障录波', '进阶', '外网', '中国知网', '录波分析典型案例，支撑故障录波 L2', NULL, 'https://www.cnki.net/', 8),
  (9, '北极星电力网 · 变电运维与高压试验技术', '资讯', '按需浏览', '高压试验', '进阶', '外网', '北极星电力网', '气体检测、SF6 微水等现场案例', NULL, 'https://news.bjx.com.cn/', 9),
  (10, '应急管理部 · 有限空间作业安全规定', '规范', '按需检索', '安全能力', '入门', '外网', '应急管理部', '电缆沟气体检测作业的直接依据', NULL, 'https://www.mem.gov.cn/', 10),
  (11, '万方数据 · 高压试验与设备状态检修资料', '论文', '按需检索', '高压试验', '进阶', '外网', '万方数据', '复合型人才路线中高压试验方向的资料库', NULL, 'https://www.wanfangdata.com.cn/', 11),
  (12, '国家电网公司 · 安全生产工作动态', '资讯', '按需浏览', '安全能力', '入门', '外网', '国家电网', '班组安全学习与案例通报来源', NULL, 'http://www.sgcc.com.cn/', 12)
  ON DUPLICATE KEY UPDATE title=VALUES(title), item_type=VALUES(item_type), duration=VALUES(duration), skill=VALUES(skill), level=VALUES(level), origin=VALUES(origin), site=VALUES(site), match_reason=VALUES(match_reason), jump_to=VALUES(jump_to), url=VALUES(url), sort_no=VALUES(sort_no);
INSERT INTO certificate (id, username, name, level, issued_at, expires_at, review_note, status, sort_no) VALUES
  (2, 'zhangwei', '倒闸操作 L3 资格', 'L3', '2026-08-28', '2029-08-27', '长期有效，无需复审', 'VALID', 2),
  (1, 'zhangwei', '变电运维安全规程（年度）', '-', '2026-03-15', '2027-03-14', '2027-03-14 前完成年度复审', 'VALID', 1)
  ON DUPLICATE KEY UPDATE username=VALUES(username), name=VALUES(name), level=VALUES(level), issued_at=VALUES(issued_at), expires_at=VALUES(expires_at), review_note=VALUES(review_note), status=VALUES(status), sort_no=VALUES(sort_no);
INSERT INTO task (id, title, username, skill, planned_hours, actual_hours, status, due_at, requirement, publisher, sort_no) VALUES
  (1, '110kV 线路保护定值核对与投退', 'zhangwei', '继电保护', 4, 6, '进行中', '2026-09-22', '按标准作业卡执行并回传定值单', '李民', 1),
  (2, '城北变电所电缆沟气体检测', 'zhangwei', '高压试验', 2, NULL, '待执行', '2026-09-21', '有限空间作业，先通风检测后进入', '李民', 2),
  (3, '1 号主变 SF6 气室微水检测', 'zhangwei', '高压试验', 3, 3.5, '已完成', '2026-09-18', '检测数据需与上次试验记录对比', '李民', 3)
  ON DUPLICATE KEY UPDATE title=VALUES(title), username=VALUES(username), skill=VALUES(skill), planned_hours=VALUES(planned_hours), actual_hours=VALUES(actual_hours), status=VALUES(status), due_at=VALUES(due_at), requirement=VALUES(requirement), publisher=VALUES(publisher), sort_no=VALUES(sort_no);

-- ===== 能力记忆库（种子记忆） =====
INSERT INTO memory_item (memory_id, username, type, type_label, occurred_at, title, detail, tags, source, source_label, sort_no) VALUES
  ('MEM-EXAM-001', 'zhangwei', 'EXAM', '考试记忆', '2026-09-10', '继电保护理论考试 62 分（合格线 80）', '错题 8 题，其中 5 题集中在软压板逻辑与定值配合，可补考 1 次', '["继电保护","软压板逻辑","补考"]', 'SYSTEM', '考试中心', 1),
  ('MEM-PRAC-002', 'zhangwei', 'PRACTICE', '实操记忆', '2026-09-15', '110kV 线路保护定值核对超时 2 小时', '计划 4 小时实际 6 小时，问题：未提前打印定值单、软压板投退顺序现场翻查规程', '["定值核对","超时","准备不足"]', 'TEAM_LEAD', '班组长评分', 2),
  ('MEM-MENTOR-003', 'zhangwei', 'MENTOR', '带教记忆', '2026-09-16', '王建国师傅带教：定值核对 2 次', '师傅评价：动手能力强，二次回路查线快；软压板逻辑偏弱，需再带教 2-3 次', '["带教","王建国","定值核对"]', 'MENTOR', '师傅评价', 3),
  ('MEM-ADVICE-004', 'zhangwei', 'ADVICE', '系统建议', '2026-09-20', '系统建议：补《软压板逻辑》课程', '结合考试错题、实操超时与师傅评价，建议先补 4 学时微课并做 1 次模拟考', '["学习建议","软压板逻辑"]', 'AGENT', '个人学习 Agent', 4),
  ('MEM-ERROR-005', 'zhangwei', 'ERROR', '错误记忆', '2026-09-12', '错题回顾：软压板投退顺序', '误把检修压板与出口压板顺序颠倒，属高危误操作，已重新学习 SOP 第 4 章', '["错题","压板顺序"]', 'SYSTEM', '学习记录', 5),
  ('MEM-SAFE-006', 'zhangwei', 'SAFETY', '安全记忆', '2026-09-08', '安全规程（月度必修）考试合格', '得分 95 分，连续 1280 天无违章、无事故、无一票否决记录', '["安全培训","无违章"]', 'SYSTEM', '安全培训', 6),
  ('MEM-REVIEW-007', 'zhangwei', 'REVIEW', '复盘记忆', '2026-09-17', '任务复盘：电缆沟气体检测 SOP 更新', '复盘提出“进沟前必须先通风检测”写入班组 SOP，本人参与修订并被采纳', '["复盘","SOP 更新"]', 'TEAM_LEAD', '班组复盘会', 7),
  ('MEM-LEARN-008', 'zhangwei', 'LEARNING', '学习记忆', '2026-09-17', '《软压板逻辑》微课 45%', '累计 1.8 学时，剩 2.2 学时；已跟师傅完成 1 次现场定值核对', '["在线课程","进行中"]', 'SYSTEM', '学习总版', 8)
  ON DUPLICATE KEY UPDATE username=VALUES(username), type=VALUES(type), type_label=VALUES(type_label), occurred_at=VALUES(occurred_at), title=VALUES(title), detail=VALUES(detail), tags=VALUES(tags), source=VALUES(source), source_label=VALUES(source_label), sort_no=VALUES(sort_no);

-- ===== 展示数据集：个人侧 =====
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.profile', '{"readiness":68,"years":6,"position":"变电运维值班员","org":"变电运维中心","name":"张伟"}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.gaps', '[{"title":"继电保护 L1 -> L3","priority":"HIGH","reason":"考试 62 分，定值核对任务超时","type":"技能缺失"},{"title":"软压板逻辑","priority":"MEDIUM","reason":"实操报告未提前准备定值单","type":"经验缺失"}]')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.self-portrait', '{"basic":{"name":"张伟","position":"变电运维值班员","org":"变电运维中心 / 变电运维一班","years":6,"joined_at":"2020-07-01","education":"大专 · 电气自动化技术","certificates":["倒闸操作 L3 资格（2026-08-28）","变电运维安全规程 年度（2026-03-15）"]},"goals":[{"direction":"继电保护","target_level":"L3","horizon":"1 年内","note":"班组继保力量薄弱，本人也想往继保方向发展"},{"direction":"高压试验","target_level":"L2","horizon":"2 年内","note":"作为第二技能，目标是复合型值班员"}],"willingness":{"transfer":"愿意（同城，可接受城北变电所）","mentoring":"愿意带教新员工，可承担 1-2 人","business_trip":"每月可出差 3-5 天","shift":"可接受夜班轮值"},"self_review":{"strength":"动手能力强，倒闸操作熟练，现场记录规范、交接班清楚","to_improve":"软压板逻辑、定值单提前准备、二次回路分析"},"mentor_review":{"mentor":"王建国 · 高级技师（继保班）","score":78,"scored_at":"2026-09-16","comment":"动手能力强，二次回路查线快；软压板逻辑与定值配合关系偏弱，需要 2-3 次带教后独立跟班"},"peer_review":{"team":"变电运维一班（9 人）","collaboration":86,"safety":92,"responsibility":88,"comment":"班组协作配合好，安全交底执行到位，交接班记录完整"},"match":{"current_post":"变电运维值班员","current_score":68,"current_note":"岗位匹配度良好，定值类工作仍需师傅把关","target_post":"继电保护工（L3）","target_score":32,"target_note":"需补齐继保 L2/L3 与软压板逻辑后方可申请转岗"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.abilities.extras', '{"soft_skills":[{"name":"沟通","score":82,"note":"交接班与班组沟通顺畅"},{"name":"协作","score":86,"note":"班组互评 86 分"},{"name":"带教","score":55,"note":"暂无带教记录，L3 后需承担带教"},{"name":"应急","score":70,"note":"参与 1 次应急演练，未独立处置"}],"safety":{"record_days":1280,"violations":0,"incidents":0,"veto":false,"last_training":"2026-09-08 安全规程（月度必修）","note":"无一票否决项，安全状态良好"},"practice":{"ticket_count":46,"completion_rate":94,"timeout_rate":8,"overtime_count":3,"avg_hours":3.6,"last_timeout":"2026-09-15 定值核对超时 2 小时（未提前打印定值单）"},"exams":{"theory":62,"practice":92,"simulation":74,"pass_line":80,"note":"理论未达合格线，可补考 1 次"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.growth', '{"readiness":68,"readiness_label":"距继电保护 L3 还差 2 级（预计 2026-12 达到 L2）","next_step":"完成《软压板逻辑》+ 师傅带教 2 次 → 模拟考 ≥80 分 → 报名补考","timeline":[{"occurred_at":"2026-09-20","category":"培训完成","title":"完成《软压板逻辑》微课 45%","detail":"剩余 2.2 学时，计划 09-30 前完成","badge":"进行中"},{"occurred_at":"2026-09-17","category":"任务完成","title":"电缆沟气体检测任务复盘被采纳","detail":"复盘建议写入班组 SOP","badge":"已闭环"},{"occurred_at":"2026-09-16","category":"带教记录","title":"王建国师傅带教定值核对 2 次","detail":"师傅评分 78 分","badge":"L2 进度 20%"},{"occurred_at":"2026-09-15","category":"任务完成","title":"110kV 定值核对任务超时 2 小时","detail":"计入超时率 8%，已复盘","badge":"需改进"},{"occurred_at":"2026-09-10","category":"考试记录","title":"继电保护理论考试 62 分未通过","detail":"可补考 1 次","badge":"待补考"},{"occurred_at":"2026-09-08","category":"安全记录","title":"安全规程月度必修合格（95 分）","detail":"连续 1280 天无违章","badge":"安全良好"},{"occurred_at":"2026-08-28","category":"技能等级","title":"倒闸操作晋级 L3","detail":"实操考核 92 分","badge":"已达标"},{"occurred_at":"2026-03-15","category":"证书获取","title":"变电运维安全规程（年度）","detail":"有效期至 2027-03-14","badge":"有效"}],"level_curve":[{"period":"2025-06","继电保护":0,"倒闸操作":2,"高压试验":0},{"period":"2025-12","继电保护":0,"倒闸操作":2,"高压试验":1},{"period":"2026-08","继电保护":1,"倒闸操作":3,"高压试验":1}]}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.advice', '{"generated_at":"2026-09-20T09:00:00Z","source":"rule","source_label":"个人学习 Agent（规则引擎 v1）","confidence":0.88,"need_human_confirm":true,"summary":"当前最大缺口是继电保护（L1→L3）。考试错题、实操超时、师傅评价三处证据都指向软压板逻辑与定值准备，建议按“课程 → 带教 → 模拟考 → 补考”四步推进；同时把高压试验补到 L2，成为继保 + 高压复合型值班员。","gaps":[{"skill":"继电保护","current":1,"required":3,"future":3,"gap_type":"技能缺失","severity":"HIGH","evidence":"理论 62 分未通过；定值核对超时 2 小时；师傅评价软压板逻辑偏弱"},{"skill":"高压试验","current":1,"required":2,"future":3,"gap_type":"经验缺失","severity":"MEDIUM","evidence":"仅参与 2 次，未独立开展，公司未来需求 L3"},{"skill":"故障录波","current":1,"required":2,"future":2,"gap_type":"技能缺失","severity":"MEDIUM","evidence":"能读波形，不能独立分析原因"}],"plan":[{"step":1,"kind":"课程","title":"《软压板逻辑》微课 + 定值核对 SOP","target_skill":"继电保护","to_level":"L2","due_at":"2026-09-30","reason":"考试错题与实操超时均指向软压板逻辑"},{"step":2,"kind":"带教","title":"王建国师傅带教定值核对 2 次，独立复核 1 次","target_skill":"继电保护","to_level":"L2","due_at":"2026-10-12","reason":"师傅评价已明确薄弱点，需现场带教"},{"step":3,"kind":"模拟考","title":"继电保护理论模拟考（≥80 分）后报名补考","target_skill":"继电保护","to_level":"L3","due_at":"2026-10-20","reason":"补考机会仅 1 次，需先达标再报名"},{"step":4,"kind":"课程","title":"高压试验安全规程 + 跟班实操 2 次","target_skill":"高压试验","to_level":"L2","due_at":"2026-11-15","reason":"公司未来需求 L3，先补到 L2 成为复合型"}],"compound":{"title":"复合型人才建议：继电保护 + 高压试验","detail":"班组继保仅 2 人能独立工作、高压试验 1 人即将退休。建议本人以继保为主、高压试验为辅，2027 年前达到继保 L3 + 高压 L2，可同时覆盖两类停电检修任务，减少外委 2 人次/月。","benefit":"预计每年减少外委与加班成本约 ¥3.6 万，班组排班机动性提升"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('personal.memories.insight', '{"judgement":"学习记忆与复盘记录完整；错误记忆全部集中在软压板逻辑，与考试错题、实操超时同源，说明不是能力空白而是“在岗技能不足”，可用补课 + 带教 + 复测闭环。","learning_state":"学习记忆 1 条，最近为《软压板逻辑》微课（进度 45%），另有 1 条跟师傅现场核对记录","error_state":"错误记忆 1 条，均为软压板投退顺序，近 7 天未复现","review_state":"复盘记忆 1 条，电缆沟气体检测复盘已写入班组 SOP","advice_state":"系统建议 1 条，最近一次由个性化 Agent 实时生成","risk_points":["软压板逻辑：错题与实操超时同源，需复测确认已掌握","定值准备：未提前打印定值单，属作业习惯问题","高压试验：记忆库中缺少独立开展记录"],"agent_inputs":["学习记忆","错误记忆","实操记忆","考试记忆","安全记忆","带教记忆","复盘记忆"]}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);

-- ===== 展示数据集：班组侧 =====
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('team.profile', '{"team_name":"变电运维一班","leader":"李民 · 班组长（本人也是员工，个人板块与组员一致）","members":9,"note":"组长对每次实操活动提交的检测报告负责，报告同时进入公司运行诊断 Agent 的参考因素"}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_item (dataset_key, item_key, sort_no, payload) VALUES
  ('team.reports', 'TR-001', 1, '{"id":"TR-001","member":"周强","reporter":"李民（班组长填报）","task_id":2,"task_title":"城北变电所电缆沟气体检测","detected_at":"2026-09-18 10:20","status":"SUBMITTED","report_id":"RPT-20260918-0001","judgment":"超限","severity":"高","summary":"H2S 12 ppm 超过阈值 10 ppm，已通风复测并通知检修","document_pdf":"/api/v1/reports/RPT-20260918-0001/document?format=pdf"}'),
  ('team.reports', 'TR-002', 2, '{"id":"TR-002","member":"张伟","reporter":"李民（班组长填报）","task_id":1,"task_title":"110kV 线路保护定值核对与投退","detected_at":"2026-09-15 09:00","status":"SUBMITTED","report_id":"RPT-20260915-0002","judgment":"正常","severity":"低","summary":"定值核对无误，软压板投退顺序现场复核 1 次","document_pdf":"/api/v1/reports/RPT-20260915-0002/document?format=pdf"}'),
  ('team.reports', 'TR-003', 3, '{"id":"TR-003","member":"刘洋","reporter":"李民（班组长填报）","task_id":3,"task_title":"1 号主变 SF6 气室微水检测","detected_at":"2026-09-19 15:40","status":"MISSING","report_id":null,"judgment":null,"severity":null,"summary":"任务已完成但未上传报告，需在 09-22 前补交","document_pdf":null}'),
  ('team.reports', 'TR-004', 4, '{"id":"TR-004","member":"陈晓","reporter":"李民（班组长填报）","task_id":2,"task_title":"城北变电所电缆沟气体检测","detected_at":"2026-09-19 16:10","status":"SUBMITTED","report_id":"RPT-20260919-0003","judgment":"超限","severity":"高","summary":"O2 18.2% 低于阈值 19.5%，判定有限空间缺氧风险","document_pdf":"/api/v1/reports/RPT-20260919-0003/document?format=pdf"}')
  ON DUPLICATE KEY UPDATE sort_no=VALUES(sort_no), payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('team.sop.template', '{"title":"SOP 练习资料生成模板（规定填写内容）","notice":"组长按模板填入 SOP 内容，Agent 会逐条解析判定标准与考核要点，自动生成练习题并写入题库，供普通员工抽题时调用。","sections":[{"key":"basic","title":"一、SOP 基础信息","fields":[{"name":"sop_name","label":"SOP 名称","required":true,"example":"110kV 线路保护定值核对标准作业卡","hint":"写清电压等级与设备，例如“110kV 线路保护定值核对标准作业卡”"},{"name":"skill","label":"对应技能","required":true,"example":"继电保护","hint":"可填：继电保护 / 倒闸操作 / 高压试验 / 故障录波 / 安全规程"},{"name":"level","label":"适用技能等级","required":true,"example":"L2","hint":"L1 / L2 / L3，决定题目难度标注"}]},{"key":"steps","title":"二、作业步骤（每行一步）","fields":[{"name":"steps","label":"作业步骤","required":true,"example":"核对定值单版本号\\n打印最新定值单并与调度核对\\n逐项核对装置内实际定值","hint":"每行一条，至少 3 条；Agent 会按步骤生成单选题"}]},{"key":"criteria","title":"三、判定标准（每行一条）","fields":[{"name":"criteria","label":"判定标准","required":true,"example":"定值单版本号必须与调度下发版本一致\\n软压板投退顺序不得颠倒","hint":"每行一条，Agent 会逐条生成判断题"}]},{"key":"points","title":"四、考核要点（每行一条）","fields":[{"name":"points","label":"考核要点","required":true,"example":"未打印定值单不得开始核对\\n核对结果必须由第二人复核","hint":"每行一条，Agent 会逐条生成判断题"}]},{"key":"risks","title":"五、风险点与控制措施（选填）","fields":[{"name":"risks","label":"风险点与控制措施","required":false,"example":"误碰运行压板 → 作业前用绝缘胶带封贴并挂牌","hint":"每行一条，会作为题目解析引用"}]}]}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);

-- ===== 展示数据集：老总侧 =====
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('exec.company-overview', '{"company":"城东供电公司 · 变电运维中心","as_of":"2026-09-20","headcount":86,"teams":9,"leader_count":9,"skill_pass_rate":74,"cert_valid_rate":91,"training_completion":72,"safety_risk_teams":3,"retention_risk_people":6,"retention_risk_posts":3,"avg_level":1.8,"level_l3":14,"talent_risk":{"safety_teams":3,"safety_note":"3 个班组安全风险等级上升，集中在有限空间气体检测与定值核对过程管控","retention_people":6,"retention_posts":3,"retention_note":"6 人存在稳定性风险，其中 3 人处在关键岗位且暂无备份，靠内部转岗与继任者培养化解","cert_expiring":4,"cert_note":"4 本证书 90 天内到期，复审提醒已推送到班组长"},"cost":{"training":420000,"overtime":186000,"hiring":160000,"outsourcing":240000,"total":1006000,"trend_unit":"元","trend_note":"2026 年 1—9 月用人成本月度发生额，四类支出逐月合计与年度累计卡片口径一致","trend":[{"month":"1月","training":62000,"overtime":14000,"hiring":12000,"outsourcing":18000,"total":106000,"cumulative":106000},{"month":"2月","training":28000,"overtime":9000,"hiring":8000,"outsourcing":16000,"total":61000,"cumulative":167000},{"month":"3月","training":58000,"overtime":16000,"hiring":22000,"outsourcing":30000,"total":126000,"cumulative":293000},{"month":"4月","training":40000,"overtime":15000,"hiring":28000,"outsourcing":26000,"total":109000,"cumulative":402000},{"month":"5月","training":35000,"overtime":18000,"hiring":18000,"outsourcing":24000,"total":95000,"cumulative":497000},{"month":"6月","training":55000,"overtime":26000,"hiring":16000,"outsourcing":28000,"total":125000,"cumulative":622000},{"month":"7月","training":30000,"overtime":34000,"hiring":14000,"outsourcing":32000,"total":110000,"cumulative":732000},{"month":"8月","training":38000,"overtime":32000,"hiring":20000,"outsourcing":34000,"total":124000,"cumulative":856000},{"month":"9月","training":74000,"overtime":22000,"hiring":22000,"outsourcing":32000,"total":150000,"cumulative":1006000}]},"by_team":[{"team":"变电运维一班","members":9,"skill_pass":78,"reports":12,"risk":"继保 L3 缺口 2 人"},{"team":"变电运维二班","members":11,"skill_pass":82,"reports":10,"risk":"高压试验仅 1 人 L3"},{"team":"继电保护班","members":8,"skill_pass":88,"reports":6,"risk":"2 年内退休 2 人"},{"team":"电气试验班","members":7,"skill_pass":71,"reports":5,"risk":"外委依赖度高"},{"team":"综合检修班","members":9,"skill_pass":66,"reports":4,"risk":"技能等级整体偏低"}],"talent_gap":[{"skill":"继电保护 L3+","required":12,"current":8,"gap":4,"recommendation":"内部转岗 3 人 + 招聘 1 人"},{"skill":"高压试验 L2+","required":6,"current":3,"gap":3,"recommendation":"招聘 2 人 + 外委 1 人"},{"skill":"故障录波分析 L2+","required":8,"current":5,"gap":3,"recommendation":"内部培养 3 人（成本最低）"}],"report_signal":{"reports_month":37,"abnormal_rate":24,"missing_reports":3,"note":"组长实操报告是诊断依据之一：本月有 3 份缺报，24% 报告判定超限，集中在定值准备与有限空间气体检测"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('exec.skill-matrix', '{"company":"城东供电公司 · 变电运维中心","as_of":"2026-09-20","scope":"9 个班组 · 86 人 · 5 类核心技能","single_point_posts":3,"single_point_note":"继电保护主值班员、高压试验负责人、定值整定校核 3 个关键岗位备份不足，其中前两个暂无合格备份","level_legend":[{"level":"L0","label":"未入门","note":"尚未取得资格，只能跟班学习"},{"level":"L1","label":"初级","note":"可在监护下作业"},{"level":"L2","label":"中级","note":"可独立作业"},{"level":"L3","label":"高级","note":"可独立作业并带教他人"}],"level_distribution":[{"level":"L3","count":14,"share":16,"note":"关键岗位主力与带教师傅"},{"level":"L2","count":27,"share":31,"note":"可独立作业，是继任者池"},{"level":"L1","count":33,"share":39,"note":"需监护作业，培训重点人群"},{"level":"L0","count":12,"share":14,"note":"未入门，需跟班与取证"}],"skills":[{"skill":"继电保护","required_level":"L3","required_people":12,"actual_people":8,"need":4,"met_rate":67,"coverage":"5 / 9 班组","severity":"HIGH","strong_team":"继电保护班、变电运维二班","weak_team":"综合检修班、电气试验班","note":"定值类工作依赖 2 名老员工，优先内部转岗 2 人 + 培养 L2→L3 2 人"},{"skill":"高压试验","required_level":"L2+","required_people":6,"actual_people":3,"need":3,"met_rate":50,"coverage":"4 / 9 班组","severity":"HIGH","strong_team":"电气试验班","weak_team":"变电运维一班、变电运维二班、变电运维三班","note":"唯一 L3 两年内退休，后备仅 1 人 L2，需先补 L2 形成第二梯队"},{"skill":"倒闸操作","required_level":"L3","required_people":26,"actual_people":26,"need":0,"met_rate":100,"coverage":"9 / 9 班组","severity":"LOW","strong_team":"变电运维一班、变电运维二班、变电运维三班","weak_team":"无","note":"整体达标，可作为班组内生师资与跨班组支援力量"},{"skill":"故障录波","required_level":"L2+","required_people":8,"actual_people":5,"need":3,"met_rate":63,"coverage":"6 / 9 班组","severity":"MEDIUM","strong_team":"继电保护班、自动化班","weak_team":"综合检修班、带电作业班","note":"能读波形但不能独立分析原因，建议以案例会 + 仿真演练培养 3 人"},{"skill":"安全规程","required_level":"合格","required_people":86,"actual_people":79,"need":7,"met_rate":92,"coverage":"9 / 9 班组","severity":"MEDIUM","strong_team":"安全监察班","weak_team":"综合检修班","note":"7 人未完成本年度安全规程考试，属一票否决相关项，需当月闭环"}],"teams":[{"team":"变电运维一班","members":9,"avg_level":1.9,"met_rate":78,"high_level":2,"strong_skills":"倒闸操作、安全规程","weak_skills":"继电保护","backup":"继保 L3 暂无备份","risk":"MEDIUM"},{"team":"变电运维二班","members":11,"avg_level":2,"met_rate":82,"high_level":3,"strong_skills":"倒闸操作、继电保护","weak_skills":"高压试验","backup":"高压试验 L2 备份 1 人","risk":"MEDIUM"},{"team":"变电运维三班","members":12,"avg_level":1.7,"met_rate":69,"high_level":2,"strong_skills":"倒闸操作","weak_skills":"继电保护、高压试验","backup":"继保 L3 暂无备份","risk":"HIGH"},{"team":"继电保护班","members":8,"avg_level":2.4,"met_rate":88,"high_level":4,"strong_skills":"继电保护、故障录波","weak_skills":"高压试验","backup":"关键岗位有 1 名继任者","risk":"LOW"},{"team":"电气试验班","members":7,"avg_level":1.6,"met_rate":71,"high_level":1,"strong_skills":"高压试验","weak_skills":"继电保护、故障录波","backup":"高压试验 L3 继任者未定","risk":"HIGH"},{"team":"自动化班","members":10,"avg_level":1.8,"met_rate":80,"high_level":2,"strong_skills":"故障录波","weak_skills":"高压试验","backup":"录波分析有 2 名备份","risk":"LOW"},{"team":"综合检修班","members":9,"avg_level":1.4,"met_rate":66,"high_level":1,"strong_skills":"倒闸操作","weak_skills":"继电保护、故障录波、安全规程","backup":"多项技能无备份","risk":"HIGH"},{"team":"带电作业班","members":10,"avg_level":1.7,"met_rate":73,"high_level":2,"strong_skills":"安全规程","weak_skills":"故障录波","backup":"安全监护备份充足","risk":"MEDIUM"},{"team":"安全监察班","members":10,"avg_level":1.9,"met_rate":85,"high_level":2,"strong_skills":"安全规程","weak_skills":"高压试验","backup":"安全监护备份 8 人","risk":"LOW"}],"key_posts":[{"post":"继电保护主值班员","required_level":"L3","holders":8,"required":12,"backup_count":0,"backup_label":"暂无备份","risk":"HIGH","successor":"继任者培养 2 人","suggestion":"内部转岗 2 人 + L2→L3 培养 2 人，2027Q1 前补齐"},{"post":"高压试验负责人","required_level":"L2+","holders":3,"required":6,"backup_count":1,"backup_label":"仅 1 名 L2 备份","risk":"HIGH","successor":"继任者培养 2 人","suggestion":"先补 L2 到 5 人，再选 1 人冲刺 L3"},{"post":"定值整定校核","required_level":"L3","holders":2,"required":4,"backup_count":1,"backup_label":"老员工带教中","risk":"MEDIUM","successor":"带教 1 名 L2 人员","suggestion":"由继电保护班王建国带教，纳入继任者计划"},{"post":"故障录波分析","required_level":"L2+","holders":5,"required":8,"backup_count":2,"backup_label":"2 名备份","risk":"MEDIUM","successor":"案例会培养 3 人","suggestion":"以月度案例会 + 仿真演练培养 3 人"},{"post":"安全监护（工作票许可）","required_level":"合格","holders":26,"required":26,"backup_count":8,"backup_label":"备份充足","risk":"LOW","successor":"无需新增","suggestion":"保持现状，可承接跨班组安全监护"}],"strong":[{"name":"王建国","team":"继电保护班","skill":"继电保护","level":"L3","note":"带教 4 人，定值整定校核主力，可承接继任者培养"},{"name":"周强","team":"变电运维一班","skill":"倒闸操作","level":"L3","note":"实操考核 92 分，可跨班组支援与带教"},{"name":"赵敏","team":"电气试验班","skill":"高压试验","level":"L3","note":"全公司唯一 L3，两年内退休，需尽快确定继任者"},{"name":"孙倩","team":"自动化班","skill":"故障录波","level":"L2","note":"录波分析主力，可牵头月度故障案例会"}],"focus":[{"name":"张伟","team":"变电运维一班","skill":"继电保护","level":"L1","note":"理论 62 分未过线，软压板逻辑偏弱，已排 2 次师傅带教"},{"name":"陈磊","team":"电气试验班","skill":"高压试验","level":"L0","note":"尚未取证，只能跟班，纳入 L1 取证计划"},{"name":"刘洋","team":"变电运维一班","skill":"故障录波","level":"L1","note":"能读波形但不能独立分析原因"},{"name":"黄涛","team":"综合检修班","skill":"安全规程","level":"未合格","note":"本年度安全规程考试未完成，属一票否决相关项，需当月闭环"}]}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('exec.training-board', '{"company":"城东供电公司 · 变电运维中心","as_of":"2026-09-20","period":"2026 年 1-9 月","summary":"培训完成率 72%（目标 80%）；累计投入 ¥42.0 万、人均 ¥4,884；技能达标率由 68% 提升到 74%，可量化收益 ¥79.8 万，投入产出比 1.9 : 1。综合检修班与电气试验班完成率偏低，是下一步跟进重点。","completion":{"rate":72,"target":80,"month":"2026-09","done_people":62,"total_people":86,"gap_people":24,"note":"9 月完成率 72%，距 80% 目标差 8 个百分点；24 人未完成本月必修，其中 2 人为滞后跟进对象"},"cost":{"invested":420000,"per_head":4884,"budget":480000,"usage_rate":88,"items":[{"name":"线上课程与外购课件","amount":186000,"share":44},{"name":"实操带教与仿真演练","amount":142000,"share":34},{"name":"外部讲师与专项培训","amount":92000,"share":22}],"note":"年度预算 ¥48.0 万，已使用 88%；剩余 ¥6.0 万用于四季度补考与取证"},"effect":{"skill_pass_before":68,"skill_pass_after":74,"delta":6,"exam_pass_rate":78,"mentor_sessions":21,"timeout_before":8,"timeout_after":6,"report_missing_before":8,"report_missing_after":3,"note":"投入集中在继电保护与高压试验，效果已在达标率、考试通过率、超时率与报告质量四个指标上体现"},"roi":{"ratio":1.9,"label":"1.9 : 1","benefit":798000,"invested":420000,"payback_months":7,"note":"可量化收益口径（年度）：外委支出下降 ¥24.0 万 + 加班成本下降 ¥18.6 万 + 招聘成本下降 ¥16.0 万 + 返工与超时工时回收 ¥12.2 万 + 师傅带教工时折价 ¥9.0 万","items":[{"name":"外委支出下降","amount":240000,"basis":"继保与高压试验能力提升后减少外委工时"},{"name":"加班成本下降","amount":186000,"basis":"可独立作业人数增加，排班机动性提升"},{"name":"招聘成本下降","amount":160000,"basis":"内部转岗优先，减少外部招聘 2 人"},{"name":"返工与超时工时回收","amount":122000,"basis":"定值核对超时率 8% → 6%"},{"name":"师傅带教工时折价","amount":90000,"basis":"21 次带教沉淀为标准化课件，可复用"}]},"departments":[{"team":"继电保护班","members":8,"completion":88,"invested":66000,"per_head":8250,"effect":"+9 个百分点","roi":2.4,"rank":1},{"team":"变电运维二班","members":11,"completion":82,"invested":54000,"per_head":4909,"effect":"+7 个百分点","roi":2.2,"rank":2},{"team":"自动化班","members":10,"completion":80,"invested":42000,"per_head":4200,"effect":"+6 个百分点","roi":2.1,"rank":3},{"team":"变电运维一班","members":9,"completion":78,"invested":60000,"per_head":6667,"effect":"+6 个百分点","roi":2,"rank":4},{"team":"安全监察班","members":10,"completion":76,"invested":31000,"per_head":3100,"effect":"+4 个百分点","roi":1.7,"rank":5},{"team":"带电作业班","members":10,"completion":71,"invested":34000,"per_head":3400,"effect":"+4 个百分点","roi":1.7,"rank":6},{"team":"变电运维三班","members":12,"completion":69,"invested":48000,"per_head":4000,"effect":"+3 个百分点","roi":1.5,"rank":7},{"team":"电气试验班","members":7,"completion":65,"invested":46000,"per_head":6571,"effect":"+2 个百分点","roi":1.2,"rank":8},{"team":"综合检修班","members":9,"completion":58,"invested":39000,"per_head":4333,"effect":"+1 个百分点","roi":0.9,"rank":9}],"plans":[{"name":"张伟","team":"变电运维一班","plan":"继电保护 L1 → L3","required":true,"progress":45,"on_track":true,"due_at":"2026-09-30","note":"《软压板逻辑》微课进行中，师傅带教 2 次已排期"},{"name":"刘洋","team":"变电运维一班","plan":"继电保护 L1 → L2","required":true,"progress":70,"on_track":true,"due_at":"2026-10-12","note":"按计划推进，跟师傅完成 1 次现场核对"},{"name":"周强","team":"变电运维一班","plan":"高压试验 L1 → L2","required":false,"progress":30,"on_track":false,"due_at":"2026-10-20","note":"滞后：需在 10-20 前补 2 次跟班实操"},{"name":"王磊","team":"继电保护班","plan":"继电保护 L2 → L3","required":true,"progress":65,"on_track":true,"due_at":"2026-11-15","note":"模拟考 ≥80 分后报名补考"},{"name":"陈磊","team":"电气试验班","plan":"高压试验 L2 → L3","required":true,"progress":55,"on_track":true,"due_at":"2026-11-30","note":"跟随外委项目跟班学习，独立完成 1 次试验"},{"name":"孙倩","team":"自动化班","plan":"故障录波 L1 → L2","required":false,"progress":80,"on_track":true,"due_at":"2026-10-31","note":"已主讲 1 次月度故障案例会"},{"name":"黄涛","team":"综合检修班","plan":"安全规程（年度必修）","required":true,"progress":25,"on_track":false,"due_at":"2026-09-30","note":"滞后：本年度安全规程考试未完成，需当月闭环"}],"plans_summary":{"total":7,"on_track":5,"lagging":2,"note":"7 人纳入学习计划：5 人按计划执行、2 人滞后；滞后人员由班组长 3 日内跟进补课，纳入班组月度看板"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('exec.diagnosis', '{"generated_at":"2026-09-20T09:00:00Z","source":"rule","source_label":"公司运行诊断 Agent（规则引擎 v1）","confidence":0.83,"need_human_confirm":true,"inputs":["员工学习情况","证书与有效期","技能掌握与岗位要求差距","组长提交的实操检测报告","人工成本与外委支出"],"verdict":{"cause":"MIXED","label":"人才缺失与技能不足并存，当前以“在岗技能不足”为主因","headline":"在岗技能不足为主因：继电保护 L3 缺口 4 人，软压板逻辑与定值准备是共同诱因","confidence":0.83,"evidence":["继电保护 L3+ 岗位需 12 人，实际 8 人 → 人才缺失（缺口 4 人）","9 名值班员中 4 人继保理论未达 80 分 → 在岗技能不足","本月 37 份实操报告中 24% 判定超限、3 份缺报 → 过程管控与技能双重问题"]},"findings":[{"title":"继电保护 L3+ 缺口 4 人","impact":"关键定值工作依赖 2 名老员工，一人请假即无法排班","evidence":"岗位要求 12 人 / 实际 8 人；继保班 2 年内退休 2 人"},{"title":"在岗技能不足集中在软压板逻辑与定值准备","impact":"定值核对超时率 8%，需师傅复核才能闭环","evidence":"近 3 次考试平均 62 分；师傅评价 4 人软压板逻辑偏弱"},{"title":"有限空间气体检测暴露流程短板","impact":"3 个班组安全风险等级上升","evidence":"组长报告 TR-001（H2S 12ppm）、TR-004（O2 18.2%）"},{"title":"高压试验 2 年内断档","impact":"外委支出 24 万/年且不可控","evidence":"L3 仅 1 人即将退休，后备仅 1 人 L2"}],"actions":[{"priority":"HIGH","owner":"人资 + 变电运维中心","action":"招聘继保 L3 2 人，内部转岗 2 人","cost_impact":"+¥16 万招聘成本","expected":"2027Q1 继保 L3 缺口归零"},{"priority":"HIGH","owner":"培训中心","action":"对 4 名在岗人员开展软压板逻辑专项培训 + 模拟考","cost_impact":"+¥1.2 万","expected":"定值超时率 8% → 4%，减少师傅复核工时"},{"priority":"MEDIUM","owner":"班组长","action":"未上传报告的实操任务 3 日内补交，纳入班组考核","cost_impact":"0","expected":"报告上传率 92% → 100%，诊断数据完整"},{"priority":"MEDIUM","owner":"分管老总","action":"外委名额保留到 2027Q2 作为高压试验过渡","cost_impact":"+¥6 万过渡成本","expected":"避免高压试验断档"}],"cost_summary":{"current_total":1006000,"optimized_total":928000,"saving":78000,"note":"以在岗技能提升替代 2 名外委/月，全年约省 ¥7.8 万；招聘只补真实缺口岗位，避免超编"}}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('management.dashboard', '{"training_cost":420000,"training_completion":72,"critical_gaps":7,"employees":86,"safety_risk":3,"hiring_cost":160000}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('management.talent-gap', '[{"gap":4,"recommendation":"内部转岗 3 人 + 招聘 1 人","current":8,"required":12,"skill":"继电保护 L3+"},{"gap":3,"recommendation":"招聘 2 人 + 外包 1 人","current":3,"required":6,"skill":"高压试验"}]')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);

-- ===== 展示数据集：管理员侧 =====
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('admin.overview', '{"scope_note":"系统管理员只管理全公司数据，不展示员工个人页面与老总页面","employees":86,"teams":9,"courses":54,"questions":1280,"exams":12,"papers_issued":9,"reports":37,"audit_events":128,"storage":"12.4 GB","last_backup":"2026-09-19 02:00","service_status":"运行正常（API / MySQL 数据库）"}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('admin.iam.summary', '{"users":86,"roles":4,"orgs":10,"positions":6,"pending_accounts":3,"pending_reviews":2,"note":"账号权限按角色统一放行，越权请求由 RoleInterceptor 按路径前缀拦截并记入审计"}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('admin.exam-config', '{"summary":{"paper_rules":4,"anti_cheat":5,"scoring":4,"pass_lines":4,"exams":4,"note":"组卷、防作弊、评分与及格线统一在此维护；开考与发卷由管理员在「考试清单 / 试卷发放」统一操作"},"paper_rules":[{"name":"组卷规则 A","exam":"继电保护理论考试","mix":"单选 40% / 多选 30% / 判断 30%","scope":"继保题库 A（320 题）","pass_line":"80 分","enabled":true},{"name":"组卷规则 B","exam":"高压试验安全规程考试","mix":"单选 50% / 判断 30% / 案例 20%","scope":"安全规程题库（210 题）","pass_line":"90 分","enabled":true},{"name":"评分表规则","exam":"倒闸操作实操考核","mix":"评分项 12 项（含扣分项）","scope":"倒闸实操评分表 v3","pass_line":"80 分","enabled":true},{"name":"组卷规则 C","exam":"有限空间作业专项考试","mix":"单选 60% / 判断 40%","scope":"有限空间题库（86 题）","pass_line":"90 分","enabled":false}],"anti_cheat":[{"item":"人脸核验","value":"启用","detail":"开考前比对本人照片，不通过不允许入场"},{"item":"切屏检测","value":"启用（阈值 3 次）","detail":"切屏 3 次自动强制交卷并记录"},{"item":"题目乱序","value":"启用","detail":"每人题序与选项顺序随机"},{"item":"限时交卷","value":"启用","detail":"到时自动提交，超时不再接受作答"},{"item":"IP 限制","value":"启用","detail":"仅允许考场网段提交，异常 IP 记入审计"}],"scoring":[{"item":"客观题判分","rule":"系统自动判分（单选 / 多选 / 判断）","value":"100% 系统判定","detail":"交卷即出分"},{"item":"实操评分","rule":"师傅评分 60% + 班组长评分 40%","value":"双评合计","detail":"两人差异 > 10 分触发复核"},{"item":"仿真成绩","rule":"扣分制，超时每分钟 -1 分","value":"满分 100","detail":"低于 85 分需重做"},{"item":"安全项","rule":"安全项不合格即 0 分（一票否决）","value":"一票否决","detail":"需当月闭合并重考安全规程"}],"pass_lines":[{"exam_type":"理论考试","pass_line":80,"retake":"1 次","detail":"补考仍未过进入带教计划"},{"exam_type":"实操考核","pass_line":80,"retake":"1 次","detail":"超时项单独扣分并记录"},{"exam_type":"安全类考试","pass_line":90,"retake":"1 次","detail":"一票否决，需当月闭环"},{"exam_type":"仿真演练","pass_line":85,"retake":"不限（模拟）","detail":"模拟成绩不计入考试档案"}]}')
  ON DUPLICATE KEY UPDATE payload=VALUES(payload);

-- ===== 实操检测报告种子（含文档正文与归因结果） =====
INSERT INTO task_report (report_id, task_id, task_title, member, reporter, reporter_position, detected_at, shift, location, gas_type, gas_label, unit, gas_value, threshold_value, direction, judgment, severity, phenomenon, measures, sop_status, sop_deviation, document_text, analysis, submitted_at) VALUES
  ('RPT-20260920-0001', 3, '1 号主变 SF6 气室微水检测', '李民', '李民', '变电运维一班班组长', '2026-09-18 15:40', '白班（08:00-16:00）', '110kV 城北变电所 · 1 号主变本体间隔', 'SF6_H2O', 'SF6 微水', 'μL/L', 186, 150, 'HIGH', '超限', '高', '2026-09-18 15:40 在 1 号主变本体气室取样阀处测得 SF6 微水 186μL/L，超过标准 150μL/L，较上次试验记录（128μL/L）持续上升，现场闻到轻微刺激性气味，已停止取样并上报班组长。', '已停止取样、恢复取样阀并上报班组长，等待安排气体处理',
 'FOLLOWED', '', '一、基础信息
报告编号：RPT-20260920-0001
任务名称：1 号主变 SF6 气室微水检测
检测时间：2026-09-18 15:40
班次：白班（08:00-16:00）
检测地点：110kV 城北变电所 · 1 号主变本体间隔
填报人：李民 · 变电运维一班班组长
提交时间：2026-09-20 17:10
二、检测数据
气体类型：SF6 微水（SF6_H2O）
检测数值：186 μL/L
报警阈值：150 μL/L
报警方向：高于阈值报警
判定结论：超限（严重度：高）
执行依据：GB/T 11022 / DL/T 596 电力设备预防性试验规程
三、异常现象描述
异常现象描述：2026-09-18 15:40 在 1 号主变本体气室取样阀处测得 SF6 微水 186μL/L，超过标准 150μL/L，较上次试验记录（128μL/L）持续上升，现场闻到轻微刺激性气味，已停止取样并上报班组长。
已采取措施：已停止取样、恢复取样阀并上报班组长，等待安排气体处理
', '{"source":"rule","model":"内置规则引擎 v1","abnormal":true,"severity":"高","conclusion":"SF6 微水（SF6_H2O）检测值 186 μL/L 超过报警阈值 150 μL/L（超出 24.0%），结合现场现象描述判定为：气室受潮或吸附剂失效，导致 SF6 气体微水含量升高。严重度：高。","causes":["气室受潮或吸附剂失效，导致 SF6 气体微水含量升高","SF6 分解产物（SO2、H2S 类）超标，存在放电或局部过热","现象持续未恢复，缺陷可能正在发展"],"actions":["核查吸附剂更换与气室补气记录，判断受潮来源","安排气体处理（再生/置换）并同步检测分解产物","处理后 24 小时复测微水，合格后更新设备台账","带电检测分解产物并安排气体处理，作业时佩戴防毒面具","提高监测频次至每 2 小时一次，并升级上报至技术负责人"],"rule_refs":["RULE-GAS-ABOVE","RULE-KW-DECOMP","RULE-KW-WORSENING","RULE-SEV-ESCALATE"],"standard":"GB/T 11022 / DL/T 596 电力设备预防性试验规程","confidence":0.9,"need_human_confirm":true,"input_excerpt":"一、基础信息\\n报告编号：RPT-20260920-0001\\n任务名称：1 号主变 SF6 气室微水检测\\n检测时间：2026-09-18 15:40\\n班次：白班（08:00-16:00）\\n检测地点：110kV 城北变电所 · 1 号主变本体间隔\\n填报人：李民 · 变电运维一班班组长\\n提交时间：2026-09-20 17:10\\n二、检测数据\\n气体类型：SF6 微水（SF6_H2O）\\n检测数值：186 μL/L\\n报警阈值：150 μL/L\\n报警方向：高于阈值报警\\n判定结论：超限（严重度：高）\\n执行依据：GB/T 11022 / DL/T 596 电力设备预防性试验规程\\n三、异常现象描述\\n异常现象描述：2026-09-18 15:40 在 1 号主变本体气室取样阀处测得 SF6 微水 186μL/L，超过标准 150μL/L，较上次试验记录（128μL/L）持续上升，现场闻到轻微刺激性气味，已停止取样并上报班组长。\\n已采取措施：已停止取样、恢复取样阀并上报班组长，等待安排气体处理","generated_at":"2026-09-20T09:10:01.125101300Z","source_label":"内置规则引擎 v1"}', '2026-09-20 17:10:01'),
('RPT-20260918-0001', 2, '城北变电所电缆沟气体检测', '周强', '李民', '变电运维一班班组长', '2026-09-18 10:20', '白班（08:00-16:00）',
 '110kV 城北变电所 · 电缆沟 B 段 #3 检查井', 'H2S', '硫化氢', 'ppm', 12, 10, 'HIGH', '超限', '高',
 '2026-09-18 10:20 在城北变电所电缆沟 B 段 #3 检查井口测得 H2S 12 ppm，超过报警阈值 10 ppm，已令作业人员全部撤出并在井口设置警戒，禁止未通风复测前进入。',
 '已撤出作业人员、设置警戒并开启轴流风机强制通风 30 分钟，复测 H2S 降至 6 ppm 后通知检修班组检查电缆接头',
 'FOLLOWED', '',
 '一、基础信息
报告编号：RPT-20260918-0001
任务名称：城北变电所电缆沟气体检测
检测时间：2026-09-18 10:20
班次：白班（08:00-16:00）
检测地点：110kV 城北变电所 · 电缆沟 B 段 #3 检查井
填报人：李民 · 变电运维一班班组长
提交时间：2026-09-18 10:52
二、检测数据
气体类型：硫化氢（H2S）
检测数值：12 ppm
报警阈值：10 ppm
报警方向：高于阈值报警
判定结论：超限（严重度：高）
执行依据：GBZ 2.1 工作场所有害因素职业接触限值
三、异常现象描述
异常现象描述：2026-09-18 10:20 在城北变电所电缆沟 B 段 #3 检查井口测得 H2S 12 ppm，超过报警阈值 10 ppm，已令作业人员全部撤出并在井口设置警戒，禁止未通风复测前进入。
已采取措施：已撤出作业人员、设置警戒并开启轴流风机强制通风 30 分钟，复测 H2S 降至 6 ppm 后通知检修班组检查电缆接头
',
 '{"source":"rule","model":"内置规则引擎 v1","abnormal":true,"severity":"高","conclusion":"硫化氢（H2S）检测值 12 ppm 超过报警阈值 10 ppm（超出 20.0%），结合现场现象描述判定为：电缆沟内有机材料分解、积水腐败或防腐层破坏释放硫化氢。严重度：高。","causes":["电缆沟内有机材料分解、积水腐败或防腐层破坏释放硫化氢"],"actions":["强制通风并撤离无关人员，佩戴防毒面具后方可进入","排查沟内积水、破损电缆与腐蚀点并清理","复测 H2S 合格且通风记录留存后方可恢复作业"],"rule_refs":["RULE-GAS-ABOVE"],"standard":"GBZ 2.1 工作场所有害因素职业接触限值","confidence":0.82,"need_human_confirm":true,"input_excerpt":"一、基础信息\\n报告编号：RPT-20260918-0001\\n任务名称：城北变电所电缆沟气体检测\\n检测时间：2026-09-18 10:20\\n班次：白班（08:00-16:00）\\n检测地点：110kV 城北变电所 · 电缆沟 B 段 #3 检查井\\n填报人：李民 · 变电运维一班班组长\\n提交时间：2026-09-18 10:52\\n二、检测数据\\n气体类型：硫化氢（H2S）\\n检测数值：12 ppm\\n报警阈值：10 ppm\\n报警方向：高于阈值报警\\n判定结论：超限（严重度：高）\\n执行依据：GBZ 2.1 工作场所有害因素职业接触限值\\n三、异常现象描述\\n异常现象描述：2026-09-18 10:20 在城北变电所电缆沟 B 段 #3 检查井口测得 H2S 12 ppm，超过报警阈值 10 ppm，已令作业人员全部撤出并在井口设置警戒，禁止未通风复测前进入。\\n已采取措施：已撤出作业人员、设置警戒并开启轴流风机强制通风 30 分钟，复测 H2S 降至 6 ppm 后通知检修班组检查电缆接头","generated_at":"2026-09-18T02:52:07Z","source_label":"内置规则引擎 v1"}',
 '2026-09-18 10:52:07'),
('RPT-20260915-0002', 2, '城北变电所电缆沟气体检测', '张伟', '李民', '变电运维一班班组长', '2026-09-15 09:00', '白班（08:00-16:00）',
 '110kV 城北变电所 · 电缆沟 A 段 #2 检查井', 'CO', '一氧化碳', 'ppm', 6, 30, 'HIGH', '正常', '低',
 '2026-09-15 09:00 在城北变电所电缆沟 A 段 #2 检查井内完成气体检测，CO 读数 6 ppm，各项读数均在阈值内，通风良好，具备进入作业条件。',
 '按有限空间作业要求办理作业票后进入，检测记录已留存',
 'FOLLOWED', '',
 '一、基础信息
报告编号：RPT-20260915-0002
任务名称：城北变电所电缆沟气体检测
检测时间：2026-09-15 09:00
班次：白班（08:00-16:00）
检测地点：110kV 城北变电所 · 电缆沟 A 段 #2 检查井
填报人：李民 · 变电运维一班班组长
提交时间：2026-09-15 09:34
二、检测数据
气体类型：一氧化碳（CO）
检测数值：6 ppm
报警阈值：30 ppm
报警方向：高于阈值报警
判定结论：正常（严重度：低）
执行依据：GBZ 2.1 工作场所有害因素职业接触限值
三、异常现象描述
异常现象描述：2026-09-15 09:00 在城北变电所电缆沟 A 段 #2 检查井内完成气体检测，CO 读数 6 ppm，各项读数均在阈值内，通风良好，具备进入作业条件。
已采取措施：按有限空间作业要求办理作业票后进入，检测记录已留存
',
 '{"source":"rule","model":"内置规则引擎 v1","abnormal":false,"severity":"低","conclusion":"一氧化碳（CO）检测值 6 ppm 未超过报警阈值 30 ppm（余量 80.0%），现场描述已记录，暂判定为正常范围；严重度：低。","causes":["检测值处于标准阈值范围内，未发现异常"],"actions":["按周期复测并留存检测记录"],"rule_refs":["RULE-VALUE-NORMAL"],"standard":"GBZ 2.1 工作场所有害因素职业接触限值","confidence":0.72,"need_human_confirm":true,"input_excerpt":"一、基础信息\\n报告编号：RPT-20260915-0002\\n任务名称：城北变电所电缆沟气体检测\\n检测时间：2026-09-15 09:00\\n班次：白班（08:00-16:00）\\n检测地点：110kV 城北变电所 · 电缆沟 A 段 #2 检查井\\n填报人：李民 · 变电运维一班班组长\\n提交时间：2026-09-15 09:34\\n二、检测数据\\n气体类型：一氧化碳（CO）\\n检测数值：6 ppm\\n报警阈值：30 ppm\\n报警方向：高于阈值报警\\n判定结论：正常（严重度：低）\\n执行依据：GBZ 2.1 工作场所有害因素职业接触限值\\n三、异常现象描述\\n异常现象描述：2026-09-15 09:00 在城北变电所电缆沟 A 段 #2 检查井内完成气体检测，CO 读数 6 ppm，各项读数均在阈值内，通风良好，具备进入作业条件。\\n已采取措施：按有限空间作业要求办理作业票后进入，检测记录已留存","generated_at":"2026-09-15T01:34:11Z","source_label":"内置规则引擎 v1"}',
 '2026-09-15 09:34:11'),
('RPT-20260919-0003', 2, '城北变电所电缆沟气体检测', '陈晓', '李民', '变电运维一班班组长', '2026-09-19 16:10', '中班（16:00-24:00）',
 '110kV 城北变电所 · 电缆沟 A 段 #1 检查井', 'O2', '氧气', '%VOL', 18.2, 19.5, 'LOW', '超限', '高',
 '2026-09-19 16:10 在城北变电所电缆沟 A 段 #1 检查井内测得 O2 18.2%VOL，低于报警阈值 19.5%VOL，先行进入的作业人员出现头晕、胸闷不适，已紧急撤出并开启强制通风。',
 '已紧急撤出作业人员并送医观察，开启两台轴流风机连续通风 40 分钟，复测 O2 回升至 20.4% 后才允许再次进入',
 'DEVIATED', '作业人员先行进入检查井后才检测氧含量，未执行“先检测、后进入”的有限空间作业程序',
 '一、基础信息
报告编号：RPT-20260919-0003
任务名称：城北变电所电缆沟气体检测
检测时间：2026-09-19 16:10
班次：中班（16:00-24:00）
检测地点：110kV 城北变电所 · 电缆沟 A 段 #1 检查井
填报人：李民 · 变电运维一班班组长
提交时间：2026-09-19 17:05
二、检测数据
气体类型：氧气（O2）
检测数值：18.2 %VOL
报警阈值：19.5 %VOL
报警方向：低于阈值报警
判定结论：超限（严重度：高）
执行依据：GBZ 2.1 工作场所有害因素职业接触限值 / 受限空间作业规程
三、异常现象描述
异常现象描述：2026-09-19 16:10 在城北变电所电缆沟 A 段 #1 检查井内测得 O2 18.2%VOL，低于报警阈值 19.5%VOL，先行进入的作业人员出现头晕、胸闷不适，已紧急撤出并开启强制通风。
已采取措施：已紧急撤出作业人员并送医观察，开启两台轴流风机连续通风 40 分钟，复测 O2 回升至 20.4% 后才允许再次进入
',
 '{"source":"rule","model":"内置规则引擎 v1","abnormal":true,"severity":"高","conclusion":"氧气（O2）检测值 18.2 %VOL 低于报警阈值 19.5 %VOL（低于 6.7%），结合现场现象描述判定为：受限空间通风不足，或 SF6 气体聚集置换空气导致氧含量下降。严重度：高。","causes":["受限空间通风不足，或 SF6 气体聚集置换空气导致氧含量下降","人员出现身体不适，存在中毒或缺氧风险"],"actions":["立即停止作业并撤出人员，开启强制通风不少于 15 分钟","进入前复测 O2 浓度，≥ 19.5% 且有毒气体合格后方可作业","作业期间保持连续通风并安排监护人全程监护","立即撤离人员并就医，通风检测合格前禁止再次进入"],"rule_refs":["RULE-GAS-BELOW","RULE-KW-HEALTH","RULE-SEV-ESCALATE"],"standard":"GBZ 2.1 工作场所有害因素职业接触限值 / 受限空间作业规程","confidence":0.86,"need_human_confirm":true,"input_excerpt":"一、基础信息\\n报告编号：RPT-20260919-0003\\n任务名称：城北变电所电缆沟气体检测\\n检测时间：2026-09-19 16:10\\n班次：中班（16:00-24:00）\\n检测地点：110kV 城北变电所 · 电缆沟 A 段 #1 检查井\\n填报人：李民 · 变电运维一班班组长\\n提交时间：2026-09-19 17:05\\n二、检测数据\\n气体类型：氧气（O2）\\n检测数值：18.2 %VOL\\n报警阈值：19.5 %VOL\\n报警方向：低于阈值报警\\n判定结论：超限（严重度：高）\\n执行依据：GBZ 2.1 工作场所有害因素职业接触限值 / 受限空间作业规程\\n三、异常现象描述\\n异常现象描述：2026-09-19 16:10 在城北变电所电缆沟 A 段 #1 检查井内测得 O2 18.2%VOL，低于报警阈值 19.5%VOL，先行进入的作业人员出现头晕、胸闷不适，已紧急撤出并开启强制通风。\\n已采取措施：已紧急撤出作业人员并送医观察，开启两台轴流风机连续通风 40 分钟，复测 O2 回升至 20.4% 后才允许再次进入","generated_at":"2026-09-19T09:05:22Z","source_label":"内置规则引擎 v1"}',
 '2026-09-19 17:05:22')
ON DUPLICATE KEY UPDATE task_id=VALUES(task_id), member=VALUES(member), reporter=VALUES(reporter), reporter_position=VALUES(reporter_position), gas_label=VALUES(gas_label), unit=VALUES(unit), direction=VALUES(direction), judgment=VALUES(judgment), severity=VALUES(severity), phenomenon=VALUES(phenomenon), measures=VALUES(measures), sop_status=VALUES(sop_status), sop_deviation=VALUES(sop_deviation), submitted_at=VALUES(submitted_at), analysis=VALUES(analysis), document_text=VALUES(document_text);
