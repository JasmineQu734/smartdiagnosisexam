package com.power.train.persona;

import com.power.train.store.DatasetStore;
import com.power.train.store.Sql;
import com.power.train.support.AiJsonClient;
import com.power.train.support.DiagnosisContract;
import com.power.train.support.DiagnosisPipeline;
import com.power.train.support.Texts;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/**
 * 个性化诊断 Agent（个人学习 Agent）：把原来写死的诊断结论，改成「查事实 → 提示词 → 大模型出结论 → 契约校验 → 兜底」。
 *
 * 1. 取事实：全部来自 MySQL（岗位技能要求、技能雷达、考试与错题、记忆库、学习计划、练习统计、证书、安全记录、实操报告），
 *    每条形如 F3，是结论里所有数字的唯一出处。
 * 2. 组装提示词：事实清单 + 输出契约模板 + 强约束条款，一次请求拿 JSON。
 * 3. 契约校验：字段缺失、类型不对、枚举越界一律判不合格，整份丢弃（见 DiagnosisContract）。
 * 4. 兜底：未配置大模型 / 调用失败 / 格式不合格时，原样返回既有 personal.diagnosis.core，并写明 fallback_note。
 *
 * 心理与关怀数据（care_record）不进事实清单：它默认本人可见、管理端只做脱敏聚合，不参与大模型推理。
 * 运行时字段（编号、时间、来源、证据条数、同步板块）一律由后端写死，不采用模型输出。
 */
@Component
public class PersonalDiagnosisService {

    /** 兜底口径：与改造前完全一致的静态结论，保证大模型不可用时前端不变。 */
    private static final String BASELINE_KEY = "personal.diagnosis.core";
    private static final String LABEL_RULE = "个人学习 Agent（规则引擎 v1 · 实时计算）";
    /** 本 Agent 把结论写回记忆库时用的来源前缀：构事实清单时要排掉它，避免模型引用自己的旧结论。 */
    private static final String SELF_SOURCE_PREFIX = "个人学习 Agent%";
    /** gaps.severity 的取值与排序权重（与 DiagnosisContract 的枚举保持一致）。 */
    private static final List<String> SEVERITIES = List.of("HIGH", "MEDIUM", "LOW");
    /** 技能等级标签「L3」的解析式：只认 1-5，其余（如「合格」）一律跳过。 */
    private static final Pattern LEVEL = Pattern.compile("L([1-5])");

    private final Sql sql;
    private final DatasetStore datasets;
    private final AiJsonClient client;

    public PersonalDiagnosisService(Sql sql, DatasetStore datasets, AiJsonClient client) {
        this.sql = sql;
        this.datasets = datasets;
        this.client = client;
    }

    /** 跑一次个性化诊断。diagnosisId / ranAt 由 Controller 生成，保证编号口径不变。 */
    public Map<String, Object> diagnose(String username, String diagnosisId, String ranAt) {
        Map<String, Object> baseline = new LinkedHashMap<>(datasets.meta(BASELINE_KEY));
        List<Map<String, Object>> facts = facts(username);

        // 1. 走一遍公共管道：查事实 → 提示词 → 大模型出结论 → 契约硬校验（不过就回退内置规则结论）
        DiagnosisPipeline.ModelRun run = DiagnosisPipeline.generate(client, "个人诊断", systemPrompt(),
            userPrompt(DiagnosisPipeline.renderFacts(facts), gapHint(facts), ranAt), DiagnosisContract::validatePersonal);
        Map<String, Object> result;
        if (run.usable()) {
            // 契约通过之后再规范：缺口优先级、计划排期、重复文案都由后端兜住，模型的职责只剩事实层面的判断
            applyRadarPriority(run.payload(), username);
            DiagnosisPipeline.polishPersonal(run.payload(), todayOf(ranAt));
            result = new LinkedHashMap<>(run.payload());
        } else {
            result = new LinkedHashMap<>(baseline);
        }

        // 2. 运行时字段由后端写死：编号、时间、来源、证据条数、同步板块，模型无权决定
        result.put("diagnosis_id", diagnosisId);
        result.put("ran_at", ranAt);
        result.put("source", run.usable() ? "model" : "rule");
        result.put("source_label", run.usable()
            ? "个人学习 Agent（大模型 " + client.modelName() + " · 实时计算）"
            : LABEL_RULE);
        result.put("evidence_count", facts.size());
        result.put("need_human_confirm", true);
        result.put("updated_modules", baseline.getOrDefault("updated_modules", List.of()));

        // 3. 收尾：模型结论做数字软校验，规则兜底写 fallback_note
        return DiagnosisPipeline.finish(result, run, facts);
    }

    /** 事实清单：只读，不改任何业务数据。每条 fact 一个 id（F1、F2…），供结论出处引用。 */
    private List<Map<String, Object>> facts(String username) {
        List<Map<String, Object>> facts = new ArrayList<>();
        Map<String, Object> account = sql.row(
            "SELECT display_name, position, team FROM app_user WHERE username = ?", username);
        String displayName = account == null ? username : Texts.text(account.get("display_name"));
        String position = account == null ? "" : Texts.text(account.get("position"));

        // 1. 岗位技能要求（带制度依据，结论才能解释到出处）
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, required_level, future_level, basis_role, standard_no FROM position_skill_requirement "
                + "WHERE position = ? ORDER BY sort_no", position)) {
            DiagnosisPipeline.addFact(facts, "position_skill_requirement",
                "岗位《" + position + "》要求技能 " + row.get("skill"),
                "要求 " + row.get("required_level") + "，未来需求 " + row.get("future_level")
                    + "；依据 " + Texts.orDash(row.get("basis_role")) + " / " + Texts.orDash(row.get("standard_no")));
        }

        // 2. 技能雷达现状（当前等级 vs 岗位要求 vs 未来需求）
        List<String> unmet = new ArrayList<>();
        List<String> met = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, level_label, required_label, future_label, state, priority, evidence, radar_note "
                + "FROM employee_skill WHERE username = ? AND in_radar = 1 ORDER BY sort_no", username)) {
            DiagnosisPipeline.addFact(facts, "employee_skill",
                "技能 " + row.get("skill") + "：当前 " + row.get("level_label") + "，岗位要求 "
                    + row.get("required_label") + "，未来需求 " + row.get("future_label") + "（" + Texts.orDash(row.get("state")) + "）",
                "证据：" + Texts.orDash(row.get("evidence")) + "；雷达评语：" + Texts.orDash(row.get("radar_note")));
            // 技能雷达的 state 是「谁该进 gaps」的唯一权威口径：模型没有汇总能力，容易少写或多写，
            // 所以在这里把两类技能分开存下来，由后端拼成一条汇总事实（见方法末尾）。
            String summary = "（当前 " + row.get("level_label") + "，岗位要求 " + row.get("required_label")
                + "，未来需求 " + row.get("future_label") + "，" + Texts.orDash(row.get("state"))
                + "，雷达优先级 " + Texts.orDash(row.get("priority")) + "）";
            if (Texts.text(row.get("state")).contains("达标")) {
                met.add(Texts.text(row.get("skill")) + summary);
            } else {
                unmet.add(Texts.text(row.get("skill")) + summary);
            }
        }

        // 3. 考试成绩与错题知识点
        for (Map<String, Object> row : sql.rows(
            "SELECT exam_name, score, pass_score, result, submitted_at, wrong_points FROM exam_history "
                + "WHERE username = ? ORDER BY submitted_at DESC LIMIT 3", username)) {
            String wrong = String.join("、", sql.parseStrings(row.get("wrong_points")));
            DiagnosisPipeline.addFact(facts, "exam_history",
                "考试《" + row.get("exam_name") + "》" + row.get("score") + " 分（合格线 " + row.get("pass_score")
                    + "，" + ("PASSED".equals(Texts.text(row.get("result"))) ? "已通过" : "未通过") + "，" + Texts.orDash(row.get("submitted_at")) + "）",
                wrong.isEmpty() ? "无错题记录" : "错题知识点：" + wrong);
        }

        // 4. 能力记忆库：考试、实操、带教评价都在这一张表里
        //    必须排掉本 Agent 自己写回去的诊断结论（source_label = 本 Agent）：否则跑过几次之后，
        //    记忆库按时间倒序取到的全是「我上次说过什么」，模型会把自己的旧输出当证据引用，形成自我确认。
        //    只影响推理输入，不影响前端「记忆展示」读同一张表。
        for (Map<String, Object> row : sql.rows(
            "SELECT type_label, title, detail, occurred_at, source_label FROM memory_item "
                + "WHERE username = ? AND (source_label IS NULL OR source_label NOT LIKE ?) "
                + "ORDER BY occurred_at DESC, sort_no DESC LIMIT 6", username, SELF_SOURCE_PREFIX)) {
            DiagnosisPipeline.addFact(facts, "memory_item", Texts.orDash(row.get("occurred_at")) + " " + Texts.orDash(row.get("type_label")) + "：" + row.get("title"),
                Texts.orDash(row.get("detail")) + "（来源：" + Texts.orDash(row.get("source_label")) + "）");
        }

        // 5. 学习计划执行情况
        for (Map<String, Object> row : sql.rows(
            "SELECT course_name, skill, target_level, progress, due_at FROM learning_plan "
                + "WHERE username = ? ORDER BY due_at", username)) {
            DiagnosisPipeline.addFact(facts, "learning_plan",
                "学习计划《" + row.get("course_name") + "》：目标 " + row.get("skill") + " → L" + row.get("target_level")
                    + "，进度 " + row.get("progress") + "%",
                "截止 " + Texts.orDash(row.get("due_at")));
        }

        // 6. 练习正确率
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, answered, correct FROM practice_stat WHERE username = ?", username)) {
            DiagnosisPipeline.addFact(facts, "practice_stat", "练习统计：" + row.get("skill"),
                "答对 " + row.get("correct") + " / " + row.get("answered") + " 题");
        }

        // 7. 证书与复审
        for (Map<String, Object> row : sql.rows(
            "SELECT name, level, expires_at, status FROM certificate WHERE username = ? ORDER BY sort_no", username)) {
            DiagnosisPipeline.addFact(facts, "certificate", "证书《" + row.get("name") + "》" + Texts.orDash(row.get("level")),
                "有效期至 " + Texts.orDash(row.get("expires_at")) + "，状态 " + Texts.orDash(row.get("status")));
        }

        // 8. 安全记录：安全不合格在人才决策里优先级最高，必须作为事实显式给出来
        for (Map<String, Object> row : sql.rows(
            "SELECT record_type, severity, veto, occurred_at, description FROM safety_record WHERE username = ?", username)) {
            DiagnosisPipeline.addFact(facts, "safety_record",
                "安全记录 " + Texts.orDash(row.get("record_type")) + "（" + Texts.orDash(row.get("severity")) + "）",
                "一票否决=" + (Texts.truthy(row.get("veto")) ? "是" : "否") + "；" + Texts.orDash(row.get("description")));
        }

        // 9. 本人相关的实操检测报告（缺报、超限直接来自报告台账）
        long reports = sql.count("SELECT COUNT(*) FROM task_report WHERE member = ? OR reporter = ?", displayName, displayName);
        long abnormal = sql.count("SELECT COUNT(*) FROM task_report WHERE (member = ? OR reporter = ?) AND judgment = ?",
            displayName, displayName, "超限");
        DiagnosisPipeline.addFact(facts, "task_report", "本人相关实操检测报告 " + reports + " 份", "其中判定超限 " + abnormal + " 份");

        // 10. 技能雷达差距汇总：刻意放在最后，保证前面 9 组事实的编号（F1…）保持不变。
        // 这是唯一一条「结论性」事实，作用是把「谁该进 gaps、谁该写进优势」从模型的归纳变成后端给定：
        // 实测中模型最容易出的两类错就是 gaps 少写（与 summary 自相矛盾）和多写不该有的技能。
        // 没有未达标技能时换一个 source，提示词据此不施加「必须覆盖」的约束（否则会逼模型写出空 gaps）。
        DiagnosisPipeline.addFact(facts, unmet.isEmpty() ? "skill_status_summary" : "skill_gap_summary",
            unmet.isEmpty() ? "技能雷达差距汇总：没有未达岗位要求的技能"
                : "技能雷达差距汇总：未达岗位要求的技能共 " + unmet.size() + " 项",
            (unmet.isEmpty() ? "未达标技能：无" : "未达标技能：" + String.join("；", unmet))
                + "。已达标技能：" + (met.isEmpty() ? "无" : String.join("；", met)));
        return facts;
    }

    private String systemPrompt() {
        StringBuilder builder = new StringBuilder();
        DiagnosisPipeline.line(builder, "你是变电运维人才培训系统的「个人学习诊断专家」。");
        DiagnosisPipeline.line(builder, "你只能依据用户提供的【事实清单】写结论；事实清单之外的数据、数字、人名、时间一律不得出现。");
        DiagnosisPipeline.line(builder, "硬性要求：");
        DiagnosisPipeline.line(builder, "1. 只输出一个 JSON 对象，不要输出解释文字，不要用 markdown 代码块。");
        DiagnosisPipeline.line(builder, "2. 字段名、层级、枚举取值必须与【输出模板】完全一致，不得增删或改名。");
        DiagnosisPipeline.line(builder, "3. severity 只能取 HIGH/MEDIUM/LOW；priority 只能取 P1/P2/P3；kind 只能取 课程/带教/模拟考。");
        DiagnosisPipeline.line(builder, "4. 所有数字必须来自【事实清单】，禁止编造分数、人数、金额、日期、时长。");
        DiagnosisPipeline.line(builder, "5. 每条 reasons 都要能对应到事实清单里的具体一条，并在句末标注事实编号（如 F7）；其中至少一条写已达标或已持证的基础项（优势），其余写缺口项，不要只列缺口。");
        DiagnosisPipeline.line(builder, "6. 事实不足以判断时写「现有数据不足以判断」，不要猜测 —— 但这条只管叙述字段（summary / reasons / impact）。");
        DiagnosisPipeline.line(builder, "   plan 的 due_at 是「计划日期」、不是事实数据，照【今天】往后排期即可，必须写成 YYYY-MM-DD。");
        DiagnosisPipeline.line(builder, "7. gaps 只写事实清单中明确未达岗位要求的技能；plan 写 3-4 步；compound_path 写 3-4 个阶段。");
        DiagnosisPipeline.line(builder, "8. summary 先交代岗位与已达标/已持证的基础项（优势），再说最大缺口与方向；只谈缺口、不提已有基础视为不合格。");
        DiagnosisPipeline.line(builder, "9. impact 写清缺口导致的业务后果（现在哪个动作做不了或必须依赖他人），action 写清下一步可执行的动作，不要写成空泛口号。");
        DiagnosisPipeline.line(builder, "10. verdict.reasons 各条之间不得互相复读，每条必须给出不同的事实依据；plan 各步的 reason 也必须各不相同，并说清这一步在整条路径里的位置。");
        DiagnosisPipeline.line(builder, "11. summary 里提到的每一个缺口技能，都要能在 gaps 里找到同名条目；不要在 summary 里提一个 gaps 里没有的技能。");
        DiagnosisPipeline.line(builder, "12. compound_path 的 why 回答「为什么把这几项合在一起学」，benefit 回答「学完之后能做什么」，两者不得互相摘抄或复述。");
        DiagnosisPipeline.line(builder, "13. plan 的 due_at 必须晚于【今天】并随 step 递增，不要几步挤在同一天。");
        return builder.toString();
    }

    /** 诊断基准日：模型不知道今天是几号，【今天】与计划排期都以它为准。 */
    private String todayOf(String ranAt) {
        return ranAt == null || ranAt.length() < 10 ? LocalDate.now().toString() : ranAt.substring(0, 10);
    }

    /** 把「技能雷达差距汇总」那条事实拎出来当【本次缺口清单】，并带上它的事实编号，供提示词直接引用。 */
    private String gapHint(List<Map<String, Object>> facts) {
        for (Map<String, Object> fact : facts) {
            if ("skill_gap_summary".equals(fact.get("source"))) {
                return fact.get("id") + "：" + fact.get("value");
            }
        }
        return "";
    }

    /**
     * gaps 由技能雷达说了算：技能、等级、severity、priority 都是库里的既定口径，模型只该转述。
     * 实测中模型会把两个缺口都标成 P1/HIGH，也会漏写其中一个（reasons 里提了、gaps 里却没有），
     * 所以这里按雷达逐条对齐：能对上的覆盖字段；雷达有而模型漏掉的补一条（叙述字段用兜底文案，
     * 不含任何新事实）；雷达里没有的技能（模型自己加的缺口）原样保留。
     */
    private void applyRadarPriority(Map<String, Object> payload, String username) {
        Object value = payload.get("gaps");
        List<Map<String, Object>> gaps = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> raw) {
                    Map<String, Object> gap = new LinkedHashMap<>();
                    raw.forEach((key, element) -> gap.put(String.valueOf(key), element));
                    gaps.add(gap);
                }
            }
        }

        // 只有「未达岗位要求」的技能才是 gaps 的合法成员；等级解析不出来（如「合格」）的也跳过
        Map<String, Map<String, Object>> radar = new LinkedHashMap<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, level_label, required_label, future_label, state, priority FROM employee_skill "
                + "WHERE username = ? AND in_radar = 1 AND state NOT LIKE '%达标%' ORDER BY sort_no", username)) {
            Integer current = levelNumber(Texts.text(row.get("level_label")));
            Integer required = levelNumber(Texts.text(row.get("required_label")));
            Integer future = levelNumber(Texts.text(row.get("future_label")));
            String severity = Texts.text(row.get("priority"));
            if (current == null || required == null || future == null || !SEVERITIES.contains(severity)) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("current", current);
            item.put("required", required);
            item.put("future", future);
            item.put("severity", severity);
            radar.put(Texts.text(row.get("skill")), item);
        }
        if (radar.isEmpty()) {
            return;
        }

        Set<String> covered = new LinkedHashSet<>();
        for (Map<String, Object> gap : gaps) {
            Map<String, Object> item = radar.get(Texts.text(gap.get("skill")));
            if (item != null) {
                gap.putAll(item);
                covered.add(Texts.text(gap.get("skill")));
            }
        }
        for (Map.Entry<String, Map<String, Object>> entry : radar.entrySet()) {
            if (covered.contains(entry.getKey())) {
                continue;
            }
            Map<String, Object> item = entry.getValue();
            Map<String, Object> gap = new LinkedHashMap<>();
            gap.put("skill", entry.getKey());
            gap.putAll(item);
            gap.put("priority", "P1");
            gap.put("impact", entry.getKey() + "当前 L" + item.get("current") + "、岗位要求 L" + item.get("required")
                + "，该缺口会限制本人在现场作业中的授权范围，关键步骤仍需他人复核。");
            gap.put("action", "按技能雷达要求补齐" + entry.getKey() + "的课程学习与带教验证，经师傅复核通过后再申请等级评定。");
            gaps.add(gap);
        }

        gaps.sort(Comparator.comparingInt((Map<String, Object> gap) -> severityRank(Texts.text(gap.get("severity")))));
        for (int index = 0; index < gaps.size(); index++) {
            gaps.get(index).put("priority", "P" + Math.min(index + 1, 3));
        }
        payload.put("gaps", gaps);
    }

    /** 「L3」→ 3；解析不出 1-5 的（如「合格」）返回 null，调用方据此跳过。 */
    private static Integer levelNumber(String label) {
        Matcher matcher = LEVEL.matcher(label == null ? "" : label);
        if (!matcher.find()) {
            return null;
        }
        return Integer.parseInt(matcher.group(1));
    }

    private static int severityRank(String severity) {
        int index = SEVERITIES.indexOf(severity);
        return index < 0 ? SEVERITIES.size() : index;
    }

    private String userPrompt(String factsText, String gapText, String ranAt) {
        // 模型不知道今天是几号，不给日期它就会把 due_at 写成「现有数据不足以判断」，直接被契约判不合格
        String today = todayOf(ranAt);
        String dueExample = LocalDate.parse(today).plusDays(14).toString();
        StringBuilder builder = new StringBuilder();
        DiagnosisPipeline.line(builder, "【今天】" + today + "（plan.due_at 是计划日期，从今天往后排，例如 " + dueExample + "；它不参与事实核对）");
        DiagnosisPipeline.line(builder, "【事实清单】（结论里出现的每个数字都必须在这里找到出处）");
        DiagnosisPipeline.line(builder, factsText);
        // 缺口清单由后端直接从技能雷达给出。实测中模型最容易犯的错就是 gaps 少写一项（与 summary 自相矛盾）
        // 或把已达标技能也写进 gaps；给死清单比给「写作示例」可靠 —— 示例会被模型整段照抄，连事实编号一起抄错。
        if (gapText != null && !gapText.isBlank()) {
            DiagnosisPipeline.line(builder, "【本次缺口清单】（来自技能雷达，是 gaps 的唯一来源，不要另找技能）");
            DiagnosisPipeline.line(builder, "  " + gapText);
            DiagnosisPipeline.line(builder, "  gaps 必须正好覆盖「未达标技能」，一项不多、一项不少，顺序照清单排；");
            DiagnosisPipeline.line(builder, "  「已达标技能」必须写进 summary，并至少出现在一条 reasons 里作为优势项；");
            DiagnosisPipeline.line(builder, "  写等级差距、考试分数这类句子时，句末标出对应的事实编号。");
        }
        DiagnosisPipeline.line(builder, "【输出模板】");
        DiagnosisPipeline.line(builder, "{");
        DiagnosisPipeline.line(builder, "  \"summary\": \"2-3 句总述：属于能力空白还是在岗技能不足，最大缺口是什么\",");
        DiagnosisPipeline.line(builder, "  \"confidence\": 0.0 到 1.0 之间的小数,");
        DiagnosisPipeline.line(builder, "  \"verdict\": {\"headline\": \"一句话结论\", \"reasons\": [\"依据1\", \"依据2\", \"依据3\", \"依据4\"]},");
        DiagnosisPipeline.line(builder, "  \"gaps\": [{\"skill\": \"技能名\", \"current\": 1, \"required\": 3, \"future\": 3,");
        DiagnosisPipeline.line(builder, "            \"severity\": \"HIGH\", \"priority\": \"P1\", \"impact\": \"业务影响\", \"action\": \"怎么做\"}],");
        DiagnosisPipeline.line(builder, "  \"plan\": [{\"step\": 1, \"kind\": \"课程\", \"title\": \"动作标题\", \"target_skill\": \"技能名\",");
        DiagnosisPipeline.line(builder, "            \"to_level\": \"L2\", \"due_at\": \"2026-10-01\", \"reason\": \"为什么先做这一步\"}],");
        DiagnosisPipeline.line(builder, "  \"compound_path\": {\"title\": \"复合型路线标题\", \"why\": \"为什么走这条路\",");
        DiagnosisPipeline.line(builder, "     \"stages\": [{\"phase\": \"第 1 阶段 · 0-2 个月\", \"focus\": \"聚焦点\", \"skills\": \"学什么\", \"milestone\": \"达标标志\"}],");
        DiagnosisPipeline.line(builder, "     \"benefit\": \"收益\"}");
        DiagnosisPipeline.line(builder, "}");
        DiagnosisPipeline.line(builder, "照【输出模板】的字段名填写，只输出一个 JSON 对象，不要输出任何解释文字。");
        return builder.toString();
    }
}
