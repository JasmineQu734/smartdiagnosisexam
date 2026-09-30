package com.power.train.rule;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.store.Sql;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 规则引擎管理端接口：只给系统管理员做规则核对与执行留痕查询，前端不直接调用。
 *
 * 业务侧（三个 Agent 桩）走 RuleEngine 的 Service 接口，不经这里；
 * 本接口只读规则 + 试算 + 查留痕，不提供改规则的能力，避免「测试接口顺手改了线上规则」。
 */
@RestController
@RequestMapping("/api/v1")
public class RuleController {

    private static final int MAX_PAGE_SIZE = 200;

    public record ExecuteRequest(String scene, String target_id, Map<String, Object> facts, Map<String, Object> options) {
    }

    private final RuleEngine engine;
    private final RuleResultStore results;
    private final Sql sql;

    public RuleController(RuleEngine engine, RuleResultStore results, Sql sql) {
        this.engine = engine;
        this.results = results;
        this.sql = sql;
    }

    /** 规则清单：管理员核对条件、动作、优先级与启停。 */
    @GetMapping("/rules")
    public Map<String, Object> rules(@RequestParam(value = "scene", required = false) String scene,
                                     @RequestParam(value = "enabled", required = false) Boolean enabled) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        List<Object> args = new ArrayList<>();
        if (scene != null && !scene.isBlank()) {
            where.append(" AND scene = ?");
            args.add(scene.trim());
        }
        if (enabled != null) {
            where.append(" AND enabled = ?");
            args.add(enabled ? 1 : 0);
        }

        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> item : sql.rows("SELECT rule_code, rule_name, scene, condition_json, action_json, "
            + "priority, enabled, stop_on_match, status, remark, updated_by, updated_at FROM rule" + where
            + " ORDER BY scene, priority DESC, rule_code", args.toArray())) {
            item.put("enabled", sql.bool(item.get("enabled")));
            item.put("stop_on_match", sql.bool(item.get("stop_on_match")));
            item.put("condition", sql.parse(item.remove("condition_json")));
            item.put("action", sql.parse(item.remove("action_json")));
            items.add(item);
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("total", items.size());
        data.put("items", items);
        return ok(data);
    }

    /** 规则试算：管理员直传 facts 验证条件；options.persist=true 时才写 rule_result 留痕。 */
    @PostMapping("/rules/execute")
    public Map<String, Object> execute(@RequestBody(required = false) ExecuteRequest request,
                                       @RequestHeader(value = "X-User", required = false) String user) {
        String scene = request == null ? null : request.scene();
        Map<String, Object> facts = request == null || request.facts() == null ? Map.of() : request.facts();

        Map<String, List<String>> fieldErrors = new LinkedHashMap<>();
        if (scene == null || scene.isBlank()) {
            fieldErrors.put("scene", List.of("scene 必填，取值如 PERSONAL_GAP / EXAM_RESULT / TALENT_GAP / REPORT_ANALYSIS"));
        }
        if (facts.isEmpty()) {
            fieldErrors.put("facts", List.of("facts 必填：规则按事实求值，空事实只会得到「不可判定」"));
        }
        if (!fieldErrors.isEmpty()) {
            return row("code", 40001, "message", "规则试算参数校验未通过",
                "data", row("field_errors", fieldErrors), "trace_id", UUID.randomUUID().toString());
        }

        String normalizedScene = scene.trim();
        String targetId = request.target_id();
        Map<String, Object> options = request.options() == null ? Map.of() : request.options();
        boolean persist = booleanOption(options.get("persist"));

        RuleEngine.Outcome outcome = engine.execute(normalizedScene, facts);
        String runId = results.nextRunId();
        if (persist) {
            String executedBy = user == null || user.isBlank() ? "admin" : user.trim();
            results.save(runId, normalizedScene, targetId, facts, outcome, null, executedBy);
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("run_id", runId);
        data.put("scene", normalizedScene);
        data.put("target_id", targetId);
        data.put("matched", outcome.matched());
        data.put("hits", outcome.hits().stream().map(RuleEngine.Hit::view).toList());
        data.put("skipped", outcome.skipped().stream().map(RuleEngine.Skipped::view).toList());
        data.put("verdict", outcome.verdict());
        data.put("explanation", outcome.explanation());
        data.put("unmatched_reason", outcome.unmatchedReason());
        data.put("persisted", persist);
        data.put("source", "rule");
        data.put("need_human_confirm", true);
        data.put("executed_at", Instant.now().toString());
        return ok(data);
    }

    /** 执行留痕：按场景 / 对象 / 日期区间倒序分页，用于复盘「当时为什么这么判」。 */
    @GetMapping("/rules/results")
    public Map<String, Object> history(@RequestParam(value = "scene", required = false) String scene,
                                       @RequestParam(value = "target_id", required = false) String targetId,
                                       @RequestParam(value = "from", required = false) String from,
                                       @RequestParam(value = "to", required = false) String to,
                                       @RequestParam(value = "page", defaultValue = "1") int page,
                                       @RequestParam(value = "size", defaultValue = "20") int size) {
        int safePage = Math.max(page, 1);
        int safeSize = Math.min(Math.max(size, 1), MAX_PAGE_SIZE);
        return ok(results.history(scene, targetId, from, to, safePage, safeSize));
    }

    private static boolean booleanOption(Object raw) {
        if (raw instanceof Boolean value) return value;
        if (raw instanceof Number value) return value.intValue() != 0;
        return raw != null && "true".equalsIgnoreCase(String.valueOf(raw).trim());
    }
}
