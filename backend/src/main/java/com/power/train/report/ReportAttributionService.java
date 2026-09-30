package com.power.train.report;

import com.power.train.rule.RuleEngine;
import com.power.train.rule.RuleResultStore;
import com.power.train.support.Texts;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

/**
 * 报告归因适配层：报告侧是消费者、规则引擎是提供者，两者之间只通过本类打交道。
 *
 * 本类只做三件事：
 *   1. 组装 facts —— 报告字段 + gas_rule 配置 + 文档正文。引擎不认识 task_report 的原始行，
 *      事实口径由这里定死，不会出现「同一场景两套口径」；
 *   2. 执行场景并把 Outcome 落成 rule_result 留痕，run_id 就是这次归因的凭证；
 *   3. 把结论映射回报告原有的 analysis 结构（键不变，前端与文档渲染都不用改）。
 *
 * 业务数据（task_report）不在这里写：写回由 ReportService 负责，规则引擎不反客为主改业务。
 * 结论句子（conclusion）属于展示层：决策来自规则（cause / severity / actions），句子在这里按报告数值拼。
 */
@Service
public class ReportAttributionService {

    /** 归因场景：气体检测报告。规则内容全在 rule 表里（scene = REPORT_GAS），改库即改规则。 */
    public static final String SCENE = "REPORT_GAS";

    /** 待人工确认的建议类型（agent_suggestion.agent_type）。 */
    public static final String AGENT_TYPE = "report-attribution";

    /** 规则来源的展示名：报告与文档上写的就是它。 */
    public static final String MODEL_LABEL = "内置规则引擎 v1";

    private static final int EXCERPT_LIMIT = 600;

    private final RuleEngine engine;
    private final RuleResultStore results;

    public ReportAttributionService(RuleEngine engine, RuleResultStore results) {
        this.engine = engine;
        this.results = results;
    }

    /**
     * 组装 REPORT_GAS 场景的事实。管理员在 POST /rules/execute 里试算规则时，也要照这份清单给 facts。
     *
     * 关键约定：ratio = |检测值 − 阈值| ÷ 阈值；over_threshold 按报警方向判断（LOW=低于阈值报警）；
     * gas_attribution / gas_actions 来自 gas_rule 表里该气体的配置，规则用 *_from 引用它们，
     * 因此不必为每种气体各写一套规则。
     */
    public static Map<String, Object> facts(ReportRecord report, String documentText) {
        ReportTemplate.GasRule gas = ReportTemplate.gasRule(report.gasType());
        BigDecimal value = report.value();
        BigDecimal threshold = report.threshold();

        Map<String, Object> facts = new LinkedHashMap<>();
        facts.put("report_id", report.reportId());
        facts.put("task_id", report.taskId());
        facts.put("gas_type", report.gasType());
        facts.put("gas_label", report.gasLabel());
        facts.put("unit", report.unit());
        facts.put("value", value);
        facts.put("threshold", threshold);
        facts.put("direction", report.direction());
        facts.put("high_direction", !"LOW".equals(report.direction()));
        facts.put("ratio", ratio(value, threshold));
        facts.put("over_threshold", ReportTemplate.abnormal(report.direction(), value, threshold));
        facts.put("standard", gas == null ? null : gas.standard());
        facts.put("gas_attribution", gas == null ? null : gas.attribution());
        facts.put("gas_actions", gas == null ? List.of() : gas.actions());
        facts.put("phenomenon", report.phenomenon());
        facts.put("measures", report.measures());
        facts.put("document_text", documentText == null ? "" : documentText);
        return facts;
    }

    /**
     * 执行归因并把执行留痕写入 rule_result，返回报告侧要的 analysis。
     * runId 由调用方生成并复用为建议编号，这样「报告 → 执行留痕 → 建议 → 人工决定」是一条链。
     */
    public Map<String, Object> attribute(ReportRecord report, String documentText, String runId, String executedBy) {
        Map<String, Object> facts = facts(report, documentText);
        RuleEngine.Outcome outcome = engine.execute(SCENE, facts);
        results.save(runId, SCENE, report.reportId(), facts, outcome, runId,
            executedBy == null || executedBy.isBlank() ? "system" : executedBy.trim());
        return analysis(report, documentText, facts, outcome, runId);
    }

    private Map<String, Object> analysis(ReportRecord report, String documentText, Map<String, Object> facts,
                                         RuleEngine.Outcome outcome, String runId) {
        Map<String, Object> verdict = outcome.verdict();
        boolean abnormal = Texts.truthy(facts.get("over_threshold"));
        String severity = text(verdict.get("severity"));
        String conclusion;

        Map<String, Object> analysis = new LinkedHashMap<>();
        analysis.put("source", "rule");
        analysis.put("model", MODEL_LABEL);
        analysis.put("run_id", runId);
        analysis.put("abnormal", abnormal);
        if (!outcome.matched()) {
            conclusion = "未命中可用规则：" + outcome.unmatchedReason() + "；请管理员在 rule 表里补该场景的规则后重新分析。";
            analysis.put("unmatched_reason", outcome.unmatchedReason());
        } else {
            conclusion = conclusion(report, facts, verdict, severity);
        }
        if (severity != null) {
            analysis.put("severity", severity);
        }
        analysis.put("conclusion", conclusion);
        analysis.put("causes", stringList(verdict.get("causes")));
        analysis.put("actions", stringList(verdict.get("actions")));
        analysis.put("rule_refs", stringList(verdict.get("rule_refs")));
        analysis.put("standard", facts.get("standard"));
        analysis.put("confidence", outcome.confidence().setScale(2, RoundingMode.HALF_UP));
        analysis.put("need_human_confirm", true);
        analysis.put("input_excerpt", Texts.excerpt(documentText, EXCERPT_LIMIT));
        if (!outcome.skipped().isEmpty()) {
            List<Map<String, Object>> skipped = new ArrayList<>();
            for (RuleEngine.Skipped item : outcome.skipped()) skipped.add(item.view());
            analysis.put("skipped_rules", skipped);
        }
        analysis.put("generated_at", Instant.now().toString());
        return analysis;
    }

    /** 结论句子分三种说法：超限 / 未超限且正常 / 未超限但有风险提示 —— 不让「暂判定为正常」和「严重度：高」出现在同一句里。 */
    private static String conclusion(ReportRecord report, Map<String, Object> facts, Map<String, Object> verdict,
                                     String severity) {
        boolean abnormal = Texts.truthy(facts.get("over_threshold"));
        boolean highDirection = Texts.truthy(facts.get("high_direction"));
        String label = text(facts.get("gas_label"));
        String unit = nullToEmpty(text(facts.get("unit")));
        String value = Texts.plain(Texts.decimal(facts.get("value")));
        String threshold = Texts.plain(Texts.decimal(facts.get("threshold")));
        String ratioText = percent(Texts.decimal(facts.get("ratio")));
        String cause = nullToEmpty(text(verdict.get("cause")));
        String severityText = severity == null ? "未定" : severity;
        String directionWord = highDirection ? "超过" : "低于";

        if (abnormal) {
            return String.format("%s（%s）检测值 %s %s %s报警阈值 %s %s（%s %s），结合现场现象描述判定为：%s。严重度：%s。",
                label, report.gasType(), value, unit, directionWord, threshold, unit,
                highDirection ? "超出" : "低于", ratioText, cause, severityText);
        }
        if ("低".equals(severity)) {
            return String.format("%s（%s）检测值 %s %s 未%s报警阈值 %s %s（余量 %s），现场描述已记录，暂判定为正常范围；严重度：%s。",
                label, report.gasType(), value, unit, directionWord, threshold, unit, ratioText, severityText);
        }
        return String.format("%s（%s）检测值 %s %s 未%s报警阈值 %s %s（余量 %s），未达报警条件，但结合现场描述判定为：%s。严重度：%s。",
            label, report.gasType(), value, unit, directionWord, threshold, unit, ratioText, cause, severityText);
    }

    /** 余量比例：阈值为 0 时无法算比例，按 0 处理（规则里 ratio 相关档位会自然落到最低档）。 */
    private static BigDecimal ratio(BigDecimal value, BigDecimal threshold) {
        if (value == null || threshold == null) {
            return null;
        }
        if (threshold.signum() == 0) {
            return BigDecimal.ZERO;
        }
        return value.subtract(threshold).abs().divide(threshold, 4, RoundingMode.HALF_UP);
    }

    private static List<String> stringList(Object raw) {
        List<String> values = new ArrayList<>();
        if (raw instanceof List<?> list) {
            for (Object item : list) {
                if (item != null) values.add(String.valueOf(item));
            }
        } else if (raw != null) {
            values.add(String.valueOf(raw));
        }
        return values;
    }

    private static String percent(BigDecimal ratio) {
        return ratio == null ? "" : ratio.multiply(new BigDecimal("100")).setScale(1, RoundingMode.HALF_UP) + "%";
    }

    private static String text(Object raw) {
        return raw == null ? null : String.valueOf(raw);
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
