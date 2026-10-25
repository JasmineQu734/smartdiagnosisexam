package com.power.train.agent;

import com.power.train.report.ReportAttributionService;
import com.power.train.report.ReportRecord;
import com.power.train.report.ReportService;
import com.power.train.rule.RuleEngine;
import com.power.train.rule.RuleResultStore;
import com.power.train.rule.RuleSuggestionService;
import com.power.train.store.Sql;
import com.power.train.support.Actor;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;

/**
 * 三个 Agent 接口的统一分派：把原来的「写死三条文案」换成真正的规则执行。
 *
 * 对外契约一个字没动 —— 路径 `/agent/{agentType}/{action}`、请求体 `{agent_type, target_id, context, options}`、
 * 响应字段 `{suggestion_id, agent_type, target_id, suggestions, confidence, source, need_human_confirm, status}` 全部沿用。
 * 变化只发生在本类内部：按 agent_type 组装事实 → 执行对应场景 → 把命中动作投影成可读建议。
 *
 * 三条设计约束：
 *   1. 事实只从库里组装，不采信请求体里自带的「结论」，避免调用方伪造输入；
 *   2. 每条建议末尾带规则编号（如 SKILL_GAP_L3），这是「可解释到数据」的最小凭证；
 *   3. 没有命中不是错误：照样落一条低置信度建议，并写明为什么没命中（unmatched 的原因）。
 */
@Service
public class AgentDispatchService {

    private static final String SCENE_PERSONAL = "PERSONAL_GAP";
    private static final String SCENE_TALENT = "TALENT_GAP";

    /** 与 RuleEngine 同口径：命中越多置信度越高，上限 0.95；未命中给 0.30，不装确信。 */
    private static final BigDecimal CONFIDENCE_BASE = new BigDecimal("0.72");
    private static final BigDecimal CONFIDENCE_STEP = new BigDecimal("0.04");
    private static final BigDecimal CONFIDENCE_CAP = new BigDecimal("0.95");
    private static final BigDecimal CONFIDENCE_UNMATCHED = new BigDecimal("0.30");
    private static final int EXPLANATION_LIMIT = 600;

    /** 动作编码 → 人话。规则表里存的是稳定编码，展示层才需要中文，改文案不用动规则。 */
    private static final Map<String, String> ACTION_LABELS;

    static {
        Map<String, String> labels = new LinkedHashMap<>();
        labels.put("COURSE", "补课");
        labels.put("MENTORING", "师傅带教");
        labels.put("SIMULATION", "模拟考");
        labels.put("WRONG_KNOWLEDGE_REVIEW", "错题知识点复盘");
        labels.put("ALERT", "预警");
        labels.put("INTERNAL_TRANSFER", "内部转岗");
        labels.put("RECRUITMENT", "招聘");
        labels.put("OUTSOURCE", "外包");
        labels.put("SOP_UPDATE", "SOP 更新");
        labels.put("REASSESS", "复考");
        ACTION_LABELS = Collections.unmodifiableMap(labels);
    }

    private final RuleEngine engine;
    private final RuleResultStore results;
    private final RuleSuggestionService suggestions;
    private final ReportAttributionService attribution;
    private final ReportService reports;
    private final Actor actor;
    private final Sql sql;

    public AgentDispatchService(RuleEngine engine, RuleResultStore results, RuleSuggestionService suggestions,
                                ReportAttributionService attribution, ReportService reports, Actor actor, Sql sql) {
        this.engine = engine;
        this.results = results;
        this.suggestions = suggestions;
        this.attribution = attribution;
        this.reports = reports;
        this.actor = actor;
        this.sql = sql;
    }

    /** 统一入口：Controller 只调这一行，返回的 Map 就是响应里的 data。 */
    public Map<String, Object> dispatch(String agentType, String action, Map<String, Object> request) {
        String type = agentType + "/" + action;
        Map<String, Object> context = asMap(request == null ? null : request.get("context"));
        String targetId = text(request == null ? null : request.get("target_id"));
        String currentUser = text(actor.username());
        String operator = currentUser.isEmpty() ? "system" : currentUser;

        return switch (agentType) {
            case "personal" -> personal(type, targetId, currentUser, operator);
            case "management" -> management(type, targetId, operator);
            case "report" -> report(type, targetId, context, operator);
            default -> fallback(type, targetId, "未知的 agent_type：" + agentType
                + "（只支持 personal / management / report）", operator);
        };
    }

    // ------------------------------------------------------------------ 个人学习 Agent

    /**
     * 个人建议：逐条技能核对岗位要求，命中 PERSONAL_GAP 的规则。
     *
     * 逐技能执行而不是只取「缺口最大的一项」，是因为一个人可能同时缺两三种技能；
     * 只报一项会让学习计划漏掉其他缺口（这也是评测里 62.7% 漏报的直接原因之一）。
     */
    private Map<String, Object> personal(String type, String targetId, String currentUser, String operator) {
        String username = targetId.isEmpty() ? currentUser : targetId;
        if (username.isEmpty()) {
            return fallback(type, "", "缺少 target_id，且当前请求没有登录身份，无法定位员工", operator);
        }

        List<Map<String, Object>> rows = sql.rows(
            "SELECT skill, level, required_level, future_level FROM employee_skill "
                + "WHERE username = ? ORDER BY sort_no, skill", username);
        if (rows.isEmpty()) {
            return fallback(type, username, "未找到 " + username + " 的技能档案，无法组装 PERSONAL_GAP 事实", operator);
        }

        List<RuleEngine.Hit> hits = new ArrayList<>();
        List<RuleEngine.Skipped> skipped = new ArrayList<>();
        List<Map<String, Object>> gaps = new ArrayList<>();
        List<Map<String, Object>> factRows = new ArrayList<>();
        int checked = 0;

        for (Map<String, Object> row : rows) {
            int required = number(row.get("required_level"));
            if (required <= 0) {
                continue;
            }
            checked++;
            int level = number(row.get("level"));
            int future = number(row.get("future_level"));
            Map<String, Object> fact = new LinkedHashMap<>();
            fact.put("skill", text(row.get("skill")));
            fact.put("current_level", level);
            fact.put("required_level", required);
            fact.put("future_level", future);
            factRows.add(fact);

            RuleEngine.Outcome outcome = engine.execute(SCENE_PERSONAL, fact);
            skipped.addAll(outcome.skipped());
            if (!outcome.matched()) {
                continue;
            }
            hits.addAll(outcome.hits());

            Map<String, Object> gap = new LinkedHashMap<>(fact);
            gap.put("actions", actionsOf(outcome.hits()));
            gap.put("rule_refs", codesOf(outcome.hits()));
            gaps.add(gap);
        }

        Map<String, Object> input = new LinkedHashMap<>();
        input.put("username", username);
        input.put("skills", factRows);
        input.put("scene", SCENE_PERSONAL);

        if (gaps.isEmpty()) {
            List<String> plain = List.of("当前无技能缺口：已核对 " + checked + " 项岗位技能要求，均达到岗位要求");
            RuleEngine.Outcome outcome = merge(hits, skipped, SCENE_PERSONAL);
            return finish(type, username, input, plain, CONFIDENCE_UNMATCHED, operator, null, outcome, SCENE_PERSONAL);
        }

        List<String> texts = new ArrayList<>();
        for (Map<String, Object> gap : gaps) {
            String skill = text(gap.get("skill"));
            int current = number(gap.get("current_level"));
            int required = number(gap.get("required_level"));
            int future = number(gap.get("future_level"));
            String futureNote = future > required ? "，未来需求 L" + future : "";
            texts.add(skill + "：当前 L" + current + "，岗位要求 L" + required + futureNote
                + "；建议" + labelList(gap.get("actions")) + "（" + String.join("、", textsOf(gap.get("rule_refs"))) + "）");
        }

        RuleEngine.Outcome merged = merge(hits, skipped, SCENE_PERSONAL);
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("scene", SCENE_PERSONAL);
        output.put("gaps", gaps);
        output.put("rule_refs", textsOf(merged.verdict().get("rule_refs")));
        output.put("explanation", merged.explanation());
        return finish(type, username, input, texts, merged.confidence(), operator, output, merged, SCENE_PERSONAL);
    }

    // ------------------------------------------------------------------ 组织人才 Agent

    /**
     * 组织建议：关键岗位备份 + 未来需求缺口。事实全部来自 position / employee_skill 的实时聚合，
     * 不读 dataset 展示数据 —— 展示数据可以被人为调整，决策事实不行。
     */
    private Map<String, Object> management(String type, String targetId, String operator) {
        Map<String, Object> summary = sql.row(
            "SELECT COALESCE(MIN(backup_count), 0) AS min_backup, COALESCE(SUM(headcount), 0) AS demand, "
                + "COUNT(*) AS key_posts FROM position WHERE key_post = 1");
        // 供给口径：在岗的一线人员（员工 + 组长）。不用「有技能档案的人数」——
        // 档案没补全的人也是在岗的人，用档案数会把供给算少，结论会被一眼看出不对。
        long supply = sql.count(
            "SELECT COUNT(*) FROM app_user WHERE status = 'ACTIVE' AND role_code IN ('EMPLOYEE', 'TEAM_LEAD')");
        long singlePoint = sql.count("SELECT COUNT(*) FROM position WHERE key_post = 1 AND backup_count < 2");

        Map<String, Object> facts = new LinkedHashMap<>();
        facts.put("backup_count", summary == null ? 0 : number(summary.get("min_backup")));
        facts.put("future_demand", summary == null ? 0 : number(summary.get("demand")));
        facts.put("current_supply", supply);
        facts.put("key_post_count", summary == null ? 0 : number(summary.get("key_posts")));
        facts.put("single_point_posts", singlePoint);

        RuleEngine.Outcome outcome = engine.execute(SCENE_TALENT, facts);
        List<String> texts = new ArrayList<>();
        for (RuleEngine.Hit hit : outcome.hits()) {
            texts.add(talentSentence(hit, facts));
        }

        Map<String, Object> input = new LinkedHashMap<>(facts);
        input.put("scene", SCENE_TALENT);
        input.put("target", targetId.isEmpty() ? "company" : targetId);

        Map<String, Object> output = new LinkedHashMap<>();
        output.put("scene", SCENE_TALENT);
        output.put("facts", facts);
        output.put("rule_refs", textsOf(outcome.verdict().get("rule_refs")));
        output.put("explanation", outcome.explanation());

        if (texts.isEmpty()) {
            texts = List.of("当前关键岗位备份与未来需求均未触发预警："
                + "备份最少 " + facts.get("backup_count") + " 人，编制 " + facts.get("future_demand")
                + " 人 / 现有人才 " + supply + " 人");
        }
        return finish(type, targetId.isEmpty() ? "company" : targetId, input, texts,
            outcome.confidence(), operator, output, outcome, SCENE_TALENT);
    }

    /** 组织侧文案带实时数字，避免「建议招聘」却说不清缺多少。 */
    private static String talentSentence(RuleEngine.Hit hit, Map<String, Object> facts) {
        String actions = labelList(hit.output().get("actions"));
        return switch (hit.ruleCode()) {
            case "BACKUP_SHORTAGE" -> "关键岗位备份不足：最少的岗位仅 " + facts.get("backup_count")
                + " 人可顶（底线 2 人），建议" + actions + "（" + hit.ruleCode() + "）";
            case "FUTURE_DEMAND_GAP" -> "关键岗位编制 " + facts.get("future_demand") + " 人 / 库内一线在岗 "
                + facts.get("current_supply") + " 人，存在缺口，建议" + actions + "（" + hit.ruleCode() + "）";
            default -> hit.ruleName() + "：建议" + actions + "（" + hit.ruleCode() + "）";
        };
    }

    // ------------------------------------------------------------------ 报告分析 Agent

    /**
     * 报告归因：复用 ReportAttributionService 已经验证过的事实口径与留痕链路。
     *
     * 这里不重复实现 REPORT_GAS 的条件判断 —— 报告侧和规则侧的边界早就定好了，
     * 通用桩只是同一套能力的另一个入口。report_id 取 target_id 或 context.report_id。
     */
    private Map<String, Object> report(String type, String targetId, Map<String, Object> context, String operator) {
        String reportId = targetId.isEmpty() ? text(context.get("report_id")) : targetId;
        if (reportId.isEmpty()) {
            return fallback(type, "", "缺少 report_id：请在 target_id 或 context.report_id 里给出报告编号", operator);
        }

        ReportRecord record = reports.byId(reportId);
        if (record == null) {
            return fallback(type, reportId, "报告 " + reportId + " 不存在，无法归因", operator);
        }

        String runId = results.nextRunId();
        Map<String, Object> analysis = attribution.attribute(record, record.documentText(), runId, operator);

        List<String> texts = new ArrayList<>();
        String conclusion = text(analysis.get("conclusion"));
        if (!conclusion.isEmpty()) {
            texts.add(conclusion);
        }
        List<String> actions = textsOf(analysis.get("actions"));
        List<String> refs = textsOf(analysis.get("rule_refs"));
        if (!actions.isEmpty()) {
            texts.add("建议措施：" + labelList(actions) + (refs.isEmpty() ? "" : "（" + String.join("、", refs) + "）"));
        }
        if (texts.isEmpty()) {
            texts.add("规则未给出可用结论，请管理员检查 REPORT_GAS 场景的规则配置");
        }

        Map<String, Object> input = new LinkedHashMap<>();
        input.put("report_id", reportId);
        input.put("gas_type", record.gasType());
        input.put("value", record.value());
        input.put("threshold", record.threshold());
        input.put("sop_status", record.sopStatus());

        BigDecimal confidence = decimal(analysis.get("confidence"), CONFIDENCE_UNMATCHED);
        return finish(type, reportId, input, texts, confidence, operator, analysis, null, null, runId);
    }

    // ------------------------------------------------------------------ 落库与响应

    /**
     * 一次结论的收尾：生成 run_id（已有则复用）→ 写 rule_result → 写 agent_suggestion → 组装响应。
     *
     * suggestion_id 与 run_id 相同，这是既有约定：从一条建议能直接反查到那次执行命中了什么。
     */
    private Map<String, Object> finish(String type, String targetId, Map<String, Object> input, List<String> texts,
                                       BigDecimal confidence, String operator, Map<String, Object> output,
                                       RuleEngine.Outcome outcome, String scene) {
        return finish(type, targetId, input, texts, confidence, operator, output, outcome, scene, null);
    }

    private Map<String, Object> finish(String type, String targetId, Map<String, Object> input, List<String> texts,
                                       BigDecimal confidence, String operator, Map<String, Object> output,
                                       RuleEngine.Outcome outcome, String scene, String existingRunId) {
        String runId = existingRunId == null || existingRunId.isBlank() ? results.nextRunId() : existingRunId;
        Map<String, Object> body = output == null ? new LinkedHashMap<>() : new LinkedHashMap<>(output);
        body.put("run_id", runId);
        body.put("suggestions", texts);
        body.put("source", "rule");

        if (outcome != null && scene != null) {
            results.save(runId, scene, targetId, input, outcome, runId, operator);
        }

        String suggestionId = suggestions.publish(runId, type, targetId, input, body, confidence, "rule");
        return view(suggestionId, type, targetId, texts, confidence);
    }

    /** 兜底：不报错，落一条「为什么给不出建议」的低置信度结论，前端照常展示。 */
    private Map<String, Object> fallback(String type, String targetId, String reason, String operator) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("scene", "NONE");
        body.put("unmatched_reason", reason);
        return finish(type, targetId, Map.of("reason", reason), List.of(reason),
            CONFIDENCE_UNMATCHED, operator, body, null, null);
    }

    /** 响应字段与原桩完全一致，顺序也保持，避免前端或截图对比时出现无意义差异。 */
    private static Map<String, Object> view(String suggestionId, String type, String targetId,
                                            List<String> texts, BigDecimal confidence) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("suggestion_id", suggestionId);
        data.put("agent_type", type);
        data.put("target_id", targetId);
        data.put("suggestions", texts);
        data.put("confidence", confidence);
        data.put("source", "rule");
        data.put("need_human_confirm", true);
        data.put("status", "PENDING");
        data.put("created_at", java.time.Instant.now().toString());
        return data;
    }

    // ------------------------------------------------------------------ 合并与格式化

    /**
     * 把多次执行（逐技能）的命中合并成一份结论。
     *
     * 只合并展示需要的三类字段：动作去重保序、规则编号去重保序、严重度取最严重。
     * 不重算业务判定 —— 判定已经在各次 execute 里完成，这里只做归并。
     */
    private static RuleEngine.Outcome merge(List<RuleEngine.Hit> hits, List<RuleEngine.Skipped> skipped, String scene) {
        List<Object> actions = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        Set<String> actionSeen = new LinkedHashSet<>();
        String severity = null;
        int severityRank = -1;

        for (RuleEngine.Hit hit : hits) {
            if (!refs.contains(hit.ruleCode())) {
                refs.add(hit.ruleCode());
            }
            Object raw = hit.output().get("actions");
            if (raw instanceof List<?> list) {
                for (Object item : list) {
                    if (item != null && actionSeen.add(String.valueOf(item))) {
                        actions.add(item);
                    }
                }
            }
            Object sev = hit.output().get("severity");
            if (sev != null) {
                int rank = severityRank(String.valueOf(sev));
                if (rank > severityRank) {
                    severityRank = rank;
                    severity = String.valueOf(sev);
                }
            }
        }

        BigDecimal confidence = hits.isEmpty() ? CONFIDENCE_UNMATCHED
            : CONFIDENCE_BASE.add(CONFIDENCE_STEP.multiply(BigDecimal.valueOf(hits.size()))).min(CONFIDENCE_CAP);

        Map<String, Object> verdict = new LinkedHashMap<>();
        verdict.put("actions", actions);
        verdict.put("rule_refs", refs);
        if (severity != null) {
            verdict.put("severity", severity);
        }
        verdict.put("confidence", confidence);

        String explanation = hits.isEmpty()
            ? "场景 " + scene + " 下没有规则命中：请核对事实是否齐全或规则阈值是否过严"
            : clip(String.join("；", hits.stream().map(RuleEngine.Hit::explanation).toList()));

        return new RuleEngine.Outcome(!hits.isEmpty(), hits, skipped, verdict, explanation, confidence,
            hits.isEmpty() ? explanation : null);
    }

    private static int severityRank(String severity) {
        return switch (severity) {
            case "高" -> 3;
            case "中" -> 2;
            case "低" -> 1;
            default -> 0;
        };
    }

    private static List<String> actionsOf(List<RuleEngine.Hit> hits) {
        List<String> codes = new ArrayList<>();
        for (RuleEngine.Hit hit : hits) {
            Object raw = hit.output().get("actions");
            if (raw instanceof List<?> list) {
                for (Object item : list) {
                    if (item != null && !codes.contains(String.valueOf(item))) {
                        codes.add(String.valueOf(item));
                    }
                }
            }
        }
        return codes;
    }

    private static List<String> codesOf(List<RuleEngine.Hit> hits) {
        List<String> codes = new ArrayList<>();
        for (RuleEngine.Hit hit : hits) {
            if (!codes.contains(hit.ruleCode())) {
                codes.add(hit.ruleCode());
            }
        }
        return codes;
    }

    /** 动作编码列表 → 中文短句；无法识别的编码原样保留，排障时能看出规则里写了什么。 */
    private static String labelList(Object raw) {
        List<String> values = textsOf(raw);
        List<String> labels = new ArrayList<>(values.size());
        for (String code : values) {
            labels.add(ACTION_LABELS.getOrDefault(code, code));
        }
        return String.join(" + ", labels);
    }

    private static List<String> textsOf(Object raw) {
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

    private static String clip(String text) {
        if (text == null) return "";
        return text.length() <= EXPLANATION_LIMIT ? text : text.substring(0, EXPLANATION_LIMIT);
    }

    private static String text(Object raw) {
        return raw == null ? "" : String.valueOf(raw).trim();
    }

    private static int number(Object raw) {
        if (raw instanceof Number value) return value.intValue();
        try {
            return Integer.parseInt(String.valueOf(raw).trim());
        } catch (RuntimeException ignored) {
            return 0;
        }
    }

    private static BigDecimal decimal(Object raw, BigDecimal fallback) {
        if (raw instanceof BigDecimal value) return value;
        if (raw instanceof Number value) return new BigDecimal(value.toString());
        try {
            return new BigDecimal(String.valueOf(raw).trim());
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object raw) {
        return raw instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }
}
