package com.power.train.report;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.power.train.store.Sql;
import com.power.train.support.Texts;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * 报告归因的入口：只决定「这次归因走哪条路」，不自己实现判定。
 *
 * 两条路：
 *   source=rule  → 规则引擎（由 ReportAttributionService 适配成报告侧结论）；
 *   source=model → 大模型（读取报告文档正文 + 规则目录，产出同样结构的结论）。
 * 不传 source 时按配置自动选：配好 ai.enabled + api-key 走大模型，否则走规则引擎。
 * 大模型失败一律回退规则引擎，并在结论里留 fallback_note，不能因为外部接口挂了就没有归因结果。
 *
 * 两条路的结论结构完全一致（前端与文档渲染只认这些键）：
 * source / model / run_id / abnormal / severity / conclusion / causes / actions / rule_refs /
 * standard / confidence / need_human_confirm / input_excerpt / generated_at（规则路另有 skipped_rules、unmatched_reason）。
 */
@Service
public class ReportAnalysisService {

    private static final Logger log = LoggerFactory.getLogger(ReportAnalysisService.class);

    private final ObjectMapper objectMapper = new ObjectMapper();

    private final Sql sql;
    private final ReportAttributionService attribution;

    public ReportAnalysisService(Sql sql, ReportAttributionService attribution) {
        this.sql = sql;
        this.attribution = attribution;
    }

    /** 送进大模型的正文与留痕里的 input_excerpt 共用一个长度上限，避免一处截断、一处把全文外发。 */
    private static final int EXCERPT_LIMIT = 600;

    @Value("${ai.enabled:false}") private boolean aiEnabled;
    @Value("${ai.base-url:https://api.openai.com/v1}") private String aiBaseUrl;
    @Value("${ai.model:gpt-4o-mini}") private String aiModel;
    @Value("${ai.api-key:}") private String aiApiKey;
    @Value("${ai.timeout-seconds:20}") private int aiTimeoutSeconds;

    /**
     * 执行归因分析。
     *
     * @param source     rule / model，留空按配置自动选；别的取值直接拒掉
     * @param executedBy 触发人（写进 rule_result.executed_by）
     * @param runId      本次归因的执行编号（写 rule_result，并复用为待确认建议的编号）
     */
    public Map<String, Object> analyze(ReportRecord report, String documentText, String source, String executedBy,
                                       String runId) {
        String wanted = source == null ? "" : source.trim().toLowerCase();
        if (!wanted.isEmpty() && !"rule".equals(wanted) && !"model".equals(wanted)) {
            throw new IllegalArgumentException("source 只能是 rule 或 model");
        }

        boolean configured = aiEnabled && aiApiKey != null && !aiApiKey.isBlank();
        boolean wantModel = "model".equals(wanted) || (wanted.isEmpty() && configured);
        if (!wantModel) {
            return attribution.attribute(report, documentText, runId, executedBy);
        }
        if (!configured) {
            Map<String, Object> result = attribution.attribute(report, documentText, runId, executedBy);
            result.put("fallback_note", "未配置大模型（ai.enabled=false 或 ai.api-key 为空），已回退内置规则引擎");
            return result;
        }
        try {
            Map<String, Object> result = aiAnalyze(report, documentText);
            log.info("report {} analyzed by ai model {}", report.reportId(), aiModel);
            return result;
        } catch (Exception error) {
            log.warn("AI 归因分析失败，回退规则引擎：{}", error.getMessage());
            Map<String, Object> result = attribution.attribute(report, documentText, runId, executedBy);
            result.put("fallback_note", "AI 接口调用失败，已回退内置规则引擎：" + error.getMessage());
            return result;
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> aiAnalyze(ReportRecord report, String documentText) throws Exception {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(aiTimeoutSeconds));
        factory.setReadTimeout(Duration.ofSeconds(aiTimeoutSeconds));
        RestClient client = RestClient.builder().requestFactory(factory).build();

        String system = "你是变电运维异常归因专家。只依据给定的报告文档和运维规则目录输出 JSON，"
            + "不要编造文档中没有的数值。字段：severity(高/中/低)、conclusion、causes(数组)、actions(数组)、"
            + "rule_refs(数组)、confidence(0-1)、need_human_confirm(true)。";
        String user = "【报告文档正文】\n" + Texts.excerpt(documentText, EXCERPT_LIMIT) + "\n\n【运维规则目录】\n" + ruleCatalog();

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", aiModel);
        payload.put("temperature", 0.2);
        payload.put("response_format", Map.of("type", "json_object"));
        payload.put("messages", List.of(
            Map.of("role", "system", "content", system),
            Map.of("role", "user", "content", user)));

        Map<String, Object> response = client.post()
            .uri(aiBaseUrl + "/chat/completions")
            .header("Authorization", "Bearer " + aiApiKey)
            .contentType(MediaType.APPLICATION_JSON)
            .body(payload)
            .retrieve()
            .body(Map.class);
        if (response == null) throw new IllegalStateException("AI 返回为空");

        List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
        if (choices == null || choices.isEmpty()) throw new IllegalStateException("AI 未返回候选结果");
        Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
        Map<String, Object> content = objectMapper.readValue(String.valueOf(message.get("content")), Map.class);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("source", "model");
        result.put("model", aiModel);
        result.put("abnormal", ReportTemplate.abnormal(report.direction(), report.value(), report.threshold()));
        result.put("severity", String.valueOf(content.getOrDefault("severity", "中")));
        result.put("conclusion", String.valueOf(content.getOrDefault("conclusion", "")));
        result.put("causes", content.getOrDefault("causes", List.of()));
        result.put("actions", content.getOrDefault("actions", List.of()));
        result.put("rule_refs", content.getOrDefault("rule_refs", List.of()));
        result.put("standard", ReportTemplate.gasRule(report.gasType()) == null
            ? "" : ReportTemplate.gasRule(report.gasType()).standard());
        result.put("confidence", content.getOrDefault("confidence", 0.85));
        result.put("need_human_confirm", content.getOrDefault("need_human_confirm", true));
        result.put("input_excerpt", Texts.excerpt(documentText, EXCERPT_LIMIT));
        result.put("generated_at", Instant.now().toString());
        return result;
    }

    /**
     * 给大模型看的运维规则目录：气体阈值口径来自 gas_rule 表，关键词口径来自 rule 表
     * （scene=REPORT_GAS、rule_group=KEYWORD）。关键词只有这一份数据，不另存一张表。
     */
    private String ruleCatalog() {
        StringBuilder builder = new StringBuilder();
        ReportTemplate.gasRules().values().forEach(rule -> builder
            .append("- ").append(rule.code()).append(' ').append(rule.label())
            .append(" 阈值 ").append(Texts.plain(rule.threshold())).append(rule.unit())
            .append("（").append("LOW".equals(rule.direction()) ? "低于阈值报警" : "高于阈值报警").append("）")
            .append(" 依据 ").append(rule.standard())
            .append(" 归因 ").append(rule.attribution()).append('\n'));
        for (String[] keyword : keywordCatalog()) {
            builder.append("- ").append(keyword[0]).append(" 关键词 ").append(keyword[1])
                .append(" 归因 ").append(keyword[2]).append('\n');
        }
        return builder.toString();
    }

    /** 关键词规则目录视图：[编号, 关键词, 归因]；条件树里写的就是 contains / contains_any。 */
    private List<String[]> keywordCatalog() {
        List<String[]> catalog = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT rule_code, condition_json, action_json FROM rule "
            + "WHERE scene = ? AND rule_group = 'KEYWORD' AND enabled = 1 ORDER BY priority DESC, rule_code",
            ReportAttributionService.SCENE)) {
            List<String> keywords = keywords(sql.parse(row.get("condition_json")));
            if (keywords.isEmpty()) continue;
            Map<String, Object> action = sql.parse(row.get("action_json")) instanceof Map<?, ?> map
                ? castMap(map) : Map.of();
            catalog.add(new String[]{String.valueOf(row.get("rule_code")), String.join("/", keywords),
                String.valueOf(action.getOrDefault("cause", ""))});
        }
        return catalog;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Map<?, ?> raw) {
        return (Map<String, Object>) raw;
    }

    /** 从条件树里收集 contains / contains_any 的关键词，顺序与规则里写的一致。 */
    private static List<String> keywords(Object node) {
        List<String> found = new ArrayList<>();
        collectKeywords(node, found);
        return found;
    }

    private static void collectKeywords(Object node, List<String> found) {
        if (node instanceof Map<?, ?> map) {
            Object op = map.get("op");
            if (op != null && ("contains".equals(String.valueOf(op)) || "contains_any".equals(String.valueOf(op)))) {
                Object value = map.get("value");
                if (value instanceof List<?> list) {
                    for (Object item : list) found.add(String.valueOf(item));
                } else if (value != null) {
                    found.add(String.valueOf(value));
                }
            }
            for (Object value : map.values()) collectKeywords(value, found);
        } else if (node instanceof List<?> list) {
            for (Object item : list) collectKeywords(item, found);
        }
    }
}
