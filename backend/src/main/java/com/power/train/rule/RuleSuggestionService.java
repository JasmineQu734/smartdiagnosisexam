package com.power.train.rule;

import com.power.train.store.Sql;
import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 决策层：规则（或模型）算出的结论 → 待人工确认的建议 → 人工决定留痕。
 *
 * 三层职责分开：规则引擎只写 rule_result（这次算出了什么、命中哪条、为什么），
 * 这里写 agent_suggestion（给了谁什么建议）与 decision_log（人怎么决定的）。
 * 本类不改任何业务数据 —— 建议采不采纳、采纳后怎么落库，由人工确认后走业务接口。
 *
 * 建议编号就是规则执行编号（runId）：一条建议对应一次执行，从建议能直接反查到命中的规则。
 */
@Component
public class RuleSuggestionService {

    /** 人工动作 → 建议状态。只认这三个动作，别的一律拒掉，避免库里出现没人认识的状态值。 */
    private static final Map<String, String> DECISIONS = Map.of(
        "accept", "ACCEPTED",
        "reject", "REJECTED",
        "modify", "MODIFIED");

    /** 结论来源：rule=规则引擎，model=大模型。别的取值直接拒掉，防止报告上出现第三套口径。 */
    private static final List<String> SOURCES = List.of("rule", "model");

    private final Sql sql;

    public RuleSuggestionService(Sql sql) {
        this.sql = sql;
    }

    /**
     * 发布一条待人工确认的建议。suggestionId 传空时自动生成；传 runId 时与规则执行一一对应。
     * 同一对象上还没确认的旧建议转 SUPERSEDED：报告重新归因后，人只该确认最新那份结论。
     */
    public String publish(String suggestionId, String agentType, String targetId, Map<String, Object> input,
                          Map<String, Object> output, BigDecimal confidence, String source) {
        String id = suggestionId == null || suggestionId.isBlank() ? "SUG-" + System.currentTimeMillis() : suggestionId.trim();
        String normalizedSource = normalizeSource(source);
        sql.update("UPDATE agent_suggestion SET status = 'SUPERSEDED' "
            + "WHERE agent_type = ? AND target_id = ? AND status = 'PENDING'", agentType, targetId);
        sql.update("INSERT INTO agent_suggestion (suggestion_id, agent_type, target_id, input_json, output_json, "
                + "confidence, source, need_human_confirm, status) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'PENDING')",
            id, agentType, targetId, sql.json(input == null ? Map.of() : input),
            sql.json(output == null ? Map.of() : output), confidence == null ? BigDecimal.ZERO : confidence,
            normalizedSource);
        return id;
    }

    /** 该对象上最新的待确认建议；没有就返回 null（调用方据此给出「先做归因」的提示）。 */
    public Map<String, Object> latestPending(String agentType, String targetId) {
        return sql.row("SELECT suggestion_id, agent_type, target_id, output_json, confidence, source, status, created_at "
            + "FROM agent_suggestion WHERE agent_type = ? AND target_id = ? AND status = 'PENDING' "
            + "ORDER BY created_at DESC, suggestion_id DESC LIMIT 1", agentType, targetId);
    }

    /**
     * 人工确认：流转建议状态并写 decision_log（采纳 / 驳回 / 修改），reason 是留痕的关键字段。
     * 驳回与修改必须给理由 —— 没有理由的驳回，过一阵没人知道当时为什么否掉。
     */
    public Map<String, Object> confirm(String agentType, String targetId, String decision, String reason, String user) {
        String action = decision == null ? "" : decision.trim().toLowerCase();
        String status = DECISIONS.get(action);
        if (status == null) {
            throw new IllegalArgumentException("decision 只能是 accept / reject / modify");
        }
        String note = reason == null ? "" : reason.trim();
        if (!"accept".equals(action) && note.isEmpty()) {
            throw new IllegalArgumentException("驳回或修改结论必须写明理由（reason）");
        }

        Map<String, Object> pending = latestPending(agentType, targetId);
        if (pending == null) {
            return null;
        }
        String suggestionId = String.valueOf(pending.get("suggestion_id"));
        String decisionUser = user == null || user.isBlank() ? "unknown" : user.trim();

        sql.update("UPDATE agent_suggestion SET status = ? WHERE suggestion_id = ?", status, suggestionId);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("suggestion_id", suggestionId);
        result.put("target_id", targetId);
        result.put("status", status);
        result.put("output", sql.parse(pending.get("output_json")));
        sql.update("INSERT INTO decision_log (suggestion_id, decision_user, decision, reason, result_json) "
            + "VALUES (?, ?, ?, ?, ?)", suggestionId, decisionUser, status, note.isEmpty() ? null : note,
            sql.json(result));

        result.put("decision", status);
        result.put("decision_user", decisionUser);
        result.put("reason", note);
        result.put("source", pending.get("source"));
        result.put("confidence", pending.get("confidence"));
        return result;
    }

    private static String normalizeSource(String source) {
        String value = source == null ? "" : source.trim().toLowerCase();
        if (value.isEmpty()) {
            return "rule";
        }
        if (!SOURCES.contains(value)) {
            throw new IllegalArgumentException("结论来源 source 只能是 rule 或 model");
        }
        return value;
    }
}
