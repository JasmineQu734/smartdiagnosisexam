package com.power.train.rule;

import com.power.train.store.Sql;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

/**
 * 规则执行留痕（rule_result 表）：一次执行一行，命中明细放 hits_json。
 *
 * 这里的 run_id 是排障抓手，也是「规则算出了什么」的证据；转成建议后回填 suggestion_id，
 * 就能从一条建议一路查到命中了哪条规则、人工又是怎么决定的。
 */
@Component
public class RuleResultStore {

    private static final DateTimeFormatter RUN_STAMP =
        DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss").withZone(ZoneId.of("Asia/Shanghai"));

    private final Sql sql;

    public RuleResultStore(Sql sql) {
        this.sql = sql;
    }

    /** 未落库的执行也会返回 run_id，管理员测试时能直接拿它对日志。 */
    public String nextRunId() {
        return "R-" + RUN_STAMP.format(Instant.now()) + "-"
            + UUID.randomUUID().toString().substring(0, 4).toUpperCase();
    }

    public void save(String runId, String scene, String targetId, Map<String, Object> facts,
                     RuleEngine.Outcome outcome, String suggestionId, String executedBy) {
        List<Map<String, Object>> hits = new ArrayList<>();
        for (RuleEngine.Hit hit : outcome.hits()) hits.add(hit.view());
        sql.update("INSERT INTO rule_result (run_id, scene, target_id, input_json, matched, hits_json, verdict_json, "
                + "explanation, confidence, source, suggestion_id, executed_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            runId, scene, targetId, sql.json(facts == null || facts.isEmpty() ? Map.of() : facts),
            outcome.matched() ? 1 : 0, sql.json(hits), sql.json(outcome.verdict()), outcome.explanation(),
            outcome.confidence(), "rule", suggestionId, executedBy);
    }

    /** 执行历史：按场景 / 对象 / 日期区间过滤，倒序分页。 */
    public Map<String, Object> history(String scene, String targetId, String from, String to, int page, int size) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (scene != null && !scene.isBlank()) {
            where.append(" AND scene = ?");
            args.add(scene.trim());
        }
        if (targetId != null && !targetId.isBlank()) {
            where.append(" AND target_id = ?");
            args.add(targetId.trim());
        }
        if (from != null && !from.isBlank()) {
            where.append(" AND created_at >= ?");
            args.add(from.trim());
        }
        if (to != null && !to.isBlank()) {
            where.append(" AND created_at < DATE_ADD(?, INTERVAL 1 DAY)");
            args.add(to.trim());
        }

        long total = sql.count("SELECT COUNT(*) FROM rule_result" + where, args.toArray());

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size);
        pageArgs.add((page - 1) * size);

        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT run_id, scene, target_id, matched, hits_json, verdict_json, "
            + "explanation, confidence, source, suggestion_id, executed_by, created_at FROM rule_result" + where
            + " ORDER BY id DESC LIMIT ? OFFSET ?", pageArgs.toArray())) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("run_id", row.get("run_id"));
            item.put("scene", row.get("scene"));
            item.put("target_id", row.get("target_id"));
            item.put("matched", sql.bool(row.get("matched")));
            item.put("hit_count", sql.parseList(row.get("hits_json")).size());
            item.put("matched_rules", matchedRules(row.get("hits_json")));
            item.put("verdict", sql.parse(row.get("verdict_json")));
            item.put("explanation", row.get("explanation"));
            item.put("confidence", row.get("confidence"));
            item.put("source", row.get("source"));
            item.put("suggestion_id", row.get("suggestion_id"));
            item.put("executed_by", row.get("executed_by"));
            item.put("created_at", row.get("created_at"));
            items.add(item);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        result.put("items", items);
        return result;
    }

    private List<String> matchedRules(Object hitsJson) {
        List<String> codes = new ArrayList<>();
        for (Object item : sql.parseList(hitsJson)) {
            if (item instanceof Map<?, ?> hit && hit.get("rule_code") != null) {
                codes.add(String.valueOf(hit.get("rule_code")));
            }
        }
        return codes;
    }
}
