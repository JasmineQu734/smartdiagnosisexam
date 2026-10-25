package com.power.train.company;

import com.power.train.report.ReportService;
import com.power.train.store.DatasetStore;
import com.power.train.store.Sql;
import com.power.train.support.AiJsonClient;
import com.power.train.support.DiagnosisContract;
import com.power.train.support.DiagnosisPipeline;
import com.power.train.support.Texts;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * 公司运行诊断 Agent：与个人诊断同构 —— 查事实 → 提示词 → 大模型出结论 → 契约校验 → 兜底。
 *
 * 事实来源（每条形如 F3，是结论里所有数字的唯一出处）：position 关键岗位编制与备份、employee_skill 在岗技能达标、
 * exam_history 考试成绩、task_report 实操检测报告、task 缺报、certificate 证书到期、safety_record 安全记录（一票否决）、
 * cost_record 成本台账（台账为空时取人才驾驶舱同一份口径 exec.company-overview.cost，避免两处口径打架）。
 *
 * 兜底：未配置大模型 / 调用失败 / 返回不合契约时，原样返回既有 exec.diagnosis 结论并写 fallback_note。
 * 运行时字段（编号、时间、来源、证据条数、实时报告份数、输入清单、同步板块）一律由后端写死。
 */
@Component
public class ExecDiagnosisService {

    /** 兜底口径：与改造前完全一致的静态结论。 */
    private static final String BASELINE_KEY = "exec.diagnosis";
    private static final String LABEL_RULE = "公司运行诊断 Agent（规则引擎 v1 · 实时计算）";

    /** 事实来源 → 人话，用于生成「本次诊断读取的输入」清单（不再硬编码输入项）。 */
    private static final Map<String, String> SOURCE_LABELS = Map.of(
        "position", "关键岗位编制与备份",
        "employee_skill", "在岗技能达标情况",
        "exam_history", "考试成绩记录",
        "task_report", "组长提交的实操检测报告",
        "task", "实操任务与缺报",
        "certificate", "证书与有效期",
        "safety_record", "安全记录与一票否决",
        "cost_record", "人工成本台账",
        "exec.company-overview", "用人成本口径（驾驶舱同源）");

    private final Sql sql;
    private final DatasetStore datasets;
    private final ReportService reportService;
    private final AiJsonClient client;

    public ExecDiagnosisService(Sql sql, DatasetStore datasets, ReportService reportService, AiJsonClient client) {
        this.sql = sql;
        this.datasets = datasets;
        this.reportService = reportService;
        this.client = client;
    }

    /** 跑一次公司运行诊断。diagnosisId / ranAt 由 Controller 生成，保证编号口径不变。 */
    public Map<String, Object> diagnose(String diagnosisId, String ranAt) {
        Map<String, Object> baseline = new LinkedHashMap<>(datasets.meta(BASELINE_KEY));
        List<Map<String, Object>> facts = facts();

        // 1. 走一遍公共管道：查事实 → 提示词 → 大模型出结论 → 契约硬校验（不过就回退内置规则结论）
        //    exec=true：走 ai.exec-* 专属端点（本地 sft17_exec 专用模型），未配置时回落共用端点
        DiagnosisPipeline.ModelRun run = DiagnosisPipeline.generate(client, "公司诊断", systemPrompt(),
            userPrompt(DiagnosisPipeline.renderFacts(facts)), DiagnosisContract::validateExec, true);
        Map<String, Object> result = new LinkedHashMap<>(run.usable() ? run.payload() : baseline);

        // 2. 运行时字段由后端写死：编号、时间、来源、证据条数、实时报告份数、输入清单、同步板块
        result.put("diagnosis_id", diagnosisId);
        result.put("ran_at", ranAt);
        result.put("source", run.usable() ? "model" : "rule");
        result.put("source_label", run.usable()
            ? "公司运行诊断 Agent（大模型 " + client.execModelName() + " · 实时计算）"
            : LABEL_RULE);
        result.put("live_reports", reportService.list().size());
        result.put("evidence_count", facts.size());
        result.put("inputs", inputsOf(facts));
        result.put("need_human_confirm", true);
        result.put("updated_modules", baseline.getOrDefault("updated_modules", List.of()));

        // 3. 收尾：模型结论做数字软校验，规则兜底写 fallback_note
        return DiagnosisPipeline.finish(result, run, facts);
    }

    /** 事实清单：只读，不改任何业务数据。 */
    private List<Map<String, Object>> facts() {
        List<Map<String, Object>> facts = new ArrayList<>();

        // 1. 关键岗位：编制、备份、风险 —— 人才缺失的事实来源
        for (Map<String, Object> row : sql.rows(
            "SELECT name, org, required_level, headcount, backup_count, risk FROM position "
                + "WHERE key_post = 1 ORDER BY sort_no")) {
            DiagnosisPipeline.addFact(facts, "position",
                "关键岗位《" + row.get("name") + "》（" + Texts.orDash(row.get("org")) + "）要求 " + Texts.orDash(row.get("required_level")),
                "编制 " + row.get("headcount") + " 人，现有备份 " + row.get("backup_count") + " 人，风险 " + Texts.orDash(row.get("risk")));
        }

        // 2. 在岗技能达标：把「技能不足」变成可核对的数字
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, COUNT(*) AS total, SUM(CASE WHEN level >= required_level THEN 1 ELSE 0 END) AS ok "
                + "FROM employee_skill GROUP BY skill ORDER BY skill")) {
            long total = Texts.number(row.get("total"), 0);
            long ok = Texts.number(row.get("ok"), 0);
            DiagnosisPipeline.addFact(facts, "employee_skill", "技能 " + row.get("skill") + "：在岗 " + total + " 人",
                "达到岗位要求 " + ok + " 人，未达标 " + (total - ok) + " 人");
        }

        // 3. 考试成绩（未通过的要逐条给出，否则结论说不清是谁没达标）
        DiagnosisPipeline.addFact(facts, "exam_history",
            "全公司考试记录 " + sql.count("SELECT COUNT(*) FROM exam_history") + " 条",
            "未达合格线 " + sql.count("SELECT COUNT(*) FROM exam_history WHERE score < pass_score") + " 条");
        for (Map<String, Object> row : sql.rows(
            "SELECT username, exam_name, score, pass_score, submitted_at FROM exam_history "
                + "WHERE score < pass_score ORDER BY submitted_at DESC LIMIT 5")) {
            DiagnosisPipeline.addFact(facts, "exam_history",
                "未通过：" + row.get("username") + "《" + row.get("exam_name") + "》" + row.get("score")
                    + " 分（合格线 " + row.get("pass_score") + "）",
                "考试时间 " + Texts.orDash(row.get("submitted_at")));
        }

        // 4. 实操检测报告与超限比例
        long reports = sql.count("SELECT COUNT(*) FROM task_report");
        long abnormal = sql.count("SELECT COUNT(*) FROM task_report WHERE judgment = ?", "超限");
        DiagnosisPipeline.addFact(facts, "task_report", "系统内实操检测报告 " + reports + " 份", "判定超限 " + abnormal + " 份");

        // 5. 缺报：有任务但没有报告，会让诊断输入不完整
        DiagnosisPipeline.addFact(facts, "task", "实操任务缺报 " + sql.count(
            "SELECT COUNT(*) FROM task t WHERE NOT EXISTS (SELECT 1 FROM task_report r WHERE r.task_id = t.id)") + " 项",
            "缺报会让诊断输入不完整");

        // 6. 证书到期
        DiagnosisPipeline.addFact(facts, "certificate", "证书合计 " + sql.count("SELECT COUNT(*) FROM certificate") + " 本",
            "90 天内到期或已过期 " + sql.count(
                "SELECT COUNT(*) FROM certificate WHERE expires_at IS NOT NULL AND expires_at <= ?",
                LocalDate.now().plusDays(90).toString()) + " 本");

        // 7. 安全记录：安全不合格优先级最高并一票否决，必须显式给出
        long safety = sql.count("SELECT COUNT(*) FROM safety_record");
        long veto = sql.count("SELECT COUNT(*) FROM safety_record WHERE veto = 1");
        DiagnosisPipeline.addFact(facts, "safety_record", "安全记录合计 " + safety + " 条",
            veto > 0 ? "其中一票否决 " + veto + " 条（安全不合格优先级最高）" : "无一票否决记录");

        // 8. 用人成本：优先成本台账；台账为空时取驾驶舱同源口径
        long costRows = sql.count("SELECT COUNT(*) FROM cost_record");
        if (costRows > 0) {
            for (Map<String, Object> row : sql.rows(
                "SELECT cost_type, SUM(amount) AS amount FROM cost_record GROUP BY cost_type ORDER BY cost_type")) {
                DiagnosisPipeline.addFact(facts, "cost_record", "成本台账：" + Texts.orDash(row.get("cost_type")), "合计 " + row.get("amount") + " 元");
            }
        } else {
            Map<String, Object> overview = datasets.meta("exec.company-overview");
            Object cost = overview.get("cost");
            Object total = cost instanceof Map<?, ?> map ? map.get("total") : null;
            DiagnosisPipeline.addFact(facts, "exec.company-overview", "用人成本年度累计（与人才驾驶舱同一份口径）", "合计 " + Texts.text(total) + " 元");
        }
        return facts;
    }

    /** 本次真正读了哪些数据 —— 输入清单由事实来源反推，不再硬编码。 */
    private static List<String> inputsOf(List<Map<String, Object>> facts) {
        Set<String> inputs = new LinkedHashSet<>();
        for (Map<String, Object> fact : facts) {
            String source = Texts.text(fact.get("source"));
            inputs.add(SOURCE_LABELS.getOrDefault(source, source));
        }
        return new ArrayList<>(inputs);
    }

    private String systemPrompt() {
        StringBuilder builder = new StringBuilder();
        DiagnosisPipeline.line(builder, "你是变电运维中心的「公司运行诊断专家」，面向老总出报告。");
        DiagnosisPipeline.line(builder, "你只能依据用户提供的【事实清单】写结论；事实清单之外的数据、数字、人名、时间一律不得出现。");
        DiagnosisPipeline.line(builder, "硬性要求：");
        DiagnosisPipeline.line(builder, "1. 只输出一个 JSON 对象，不要输出解释文字，不要用 markdown 代码块。");
        DiagnosisPipeline.line(builder, "2. 字段名、层级、枚举取值必须与【输出模板】完全一致，不得增删或改名。");
        DiagnosisPipeline.line(builder, "3. verdict.cause 只能取 MIXED/TALENT_GAP/SKILL_GAP：MIXED=人才缺失与技能不足并存，TALENT_GAP=以缺人为主，SKILL_GAP=以在岗技能不足为主。");
        DiagnosisPipeline.line(builder, "4. priority 只能取 HIGH/MEDIUM/LOW。");
        DiagnosisPipeline.line(builder, "5. 所有数字必须来自【事实清单】，禁止编造人数、分数、金额、比例；每条 evidence 末尾标注事实编号（如 F7），便于追溯。");
        DiagnosisPipeline.line(builder, "6. 安全记录里出现一票否决时，安全必须是最高优先级，结论里要点名；不得被成本或效率理由盖过。");
        DiagnosisPipeline.line(builder, "7. 判断人才缺失还是技能不足时，必须同时引用「岗位编制缺口」与「在岗技能未达标」两类事实。");
        DiagnosisPipeline.line(builder, "8. findings 写 3-4 项，每项都要能在事实清单里找到依据；actions 写 3-4 条，写清责任方、成本影响与预期效果。");
        DiagnosisPipeline.line(builder, "9. cost_summary 的当前成本、优化后测算、预计节省三个数字都必须能在事实清单里找到出处。");
        DiagnosisPipeline.line(builder, "10. summary 先交代当前运行基本面（编制、在岗、证书、培训、成本里已达标或正常的部分），再讲卡点、成因与优先动作；只讲问题、不提基本面视为不合格。");
        DiagnosisPipeline.line(builder, "11. findings 的 impact 要写清对哪项业务动作或成本的影响，evidence 要给出可核对的事实编号。");
        return builder.toString();
    }

    private String userPrompt(String factsText) {
        StringBuilder builder = new StringBuilder();
        DiagnosisPipeline.line(builder, "【事实清单】（结论里出现的每个数字都必须在这里找到出处）");
        DiagnosisPipeline.line(builder, factsText);
        DiagnosisPipeline.line(builder, "【输出模板】");
        DiagnosisPipeline.line(builder, "{");
        DiagnosisPipeline.line(builder, "  \"summary\": \"3-5 句总述：现在卡在哪、是缺人还是缺技能、先做什么、能省多少钱\",");
        DiagnosisPipeline.line(builder, "  \"confidence\": 0.0 到 1.0 之间的小数,");
        DiagnosisPipeline.line(builder, "  \"verdict\": {\"cause\": \"MIXED\", \"label\": \"主因表述\", \"headline\": \"一句话结论\", \"evidence\": [\"证据1\", \"证据2\", \"证据3\"]},");
        DiagnosisPipeline.line(builder, "  \"findings\": [{\"title\": \"问题标题\", \"impact\": \"影响\", \"evidence\": \"依据\"}],");
        DiagnosisPipeline.line(builder, "  \"actions\": [{\"priority\": \"HIGH\", \"owner\": \"责任方\", \"action\": \"措施\", \"cost_impact\": \"成本影响\", \"expected\": \"预期效果\"}],");
        DiagnosisPipeline.line(builder, "  \"cost_summary\": {\"current_total\": 0, \"optimized_total\": 0, \"saving\": 0, \"note\": \"口径说明\"}");
        DiagnosisPipeline.line(builder, "}");
        DiagnosisPipeline.line(builder, "只输出上面这个 JSON，字段名照抄，取值按事实清单填写。");
        return builder.toString();
    }
}
