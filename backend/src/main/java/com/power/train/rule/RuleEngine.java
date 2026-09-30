package com.power.train.rule;

import com.power.train.store.Sql;
import com.power.train.support.Texts;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;

/**
 * 规则引擎：按场景取启用中的规则，按 priority 降序逐条求值 condition_json，命中即产出可解释的结论。
 *
 * 规则内容、优先级、启停全部在 MySQL 的 rule 表里，改库即改规则；引擎只负责匹配与解释，不直接改任何业务数据。
 */
@Service
public class RuleEngine {

    private static final BigDecimal CONFIDENCE_BASE = new BigDecimal("0.72");
    private static final BigDecimal CONFIDENCE_STEP = new BigDecimal("0.04");
    private static final BigDecimal CONFIDENCE_CAP = new BigDecimal("0.95");
    /** 无规则命中时的置信度：给结论但不装确信，前端据此提示「未命中规则」。 */
    private static final BigDecimal UNMATCHED_CONFIDENCE = new BigDecimal("0.30");
    private static final int EXPLANATION_LIMIT = 600;

    private final Sql sql;

    public RuleEngine(Sql sql) {
        this.sql = sql;
    }

    /**
     * 一条启用中的规则：condition 是解析后的条件树，action 是解析后的动作定义。
     *
     * group 是匹配分组：同一场景里「取值定档」和「关键词补充」必须各判各的，否则一条命中就整场结束，
     * 关键词永远轮不到。未分组的规则同属默认组（空串），组内语义与加分组之前完全一致。
     * maxHits 限制本组最多命中几条（0 = 不限），用于「关键词最多补 3 条」这类上限。
     */
    public record Rule(String code, String name, String scene, String group, Object condition,
                       Map<String, Object> action, int priority, boolean stopOnMatch, int maxHits, String remark) {
    }

    /** 一次命中的完整依据，足够还原「为什么给这个结论」。 */
    public record Hit(String ruleCode, String ruleName, int priority, List<String> conditionHit,
                      Map<String, Object> output, String explanation) {

        public Map<String, Object> view() {
            Map<String, Object> view = new LinkedHashMap<>();
            view.put("rule_code", ruleCode);
            view.put("rule_name", ruleName);
            view.put("priority", priority);
            view.put("condition_hit", conditionHit);
            view.put("actions", output.getOrDefault("actions", List.of()));
            view.put("output", output);
            view.put("explanation", explanation);
            return view;
        }
    }

    /** 判不了的规则：缺事实、算子不支持、类型不匹配。这是排障最需要的信息，不能悄悄丢掉。 */
    public record Skipped(String ruleCode, String reason) {

        public Map<String, Object> view() {
            Map<String, Object> view = new LinkedHashMap<>();
            view.put("rule_code", ruleCode);
            view.put("skipped_reason", reason);
            return view;
        }
    }

    /** 一次执行的结论：命中清单 + 跳过的规则 + 合并后的判定 + 置信度。 */
    public record Outcome(boolean matched, List<Hit> hits, List<Skipped> skipped, Map<String, Object> verdict,
                          String explanation, BigDecimal confidence, String unmatchedReason) {
    }

    /** 取某场景下启用中的规则：priority 降序、同优先级按 rule_code 升序，保证结果稳定可复现。 */
    public List<Rule> enabledRules(String scene) {
        List<Rule> rules = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT rule_code, rule_name, scene, rule_group, condition_json, action_json, priority, stop_on_match, "
                + "max_hits, remark FROM rule WHERE enabled = 1 AND scene = ? ORDER BY priority DESC, rule_code", scene)) {
            rules.add(new Rule(
                String.valueOf(row.get("rule_code")),
                row.get("rule_name") == null ? "" : String.valueOf(row.get("rule_name")),
                String.valueOf(row.get("scene")),
                Texts.text(row.get("rule_group")),
                sql.parse(row.get("condition_json")),
                asMap(sql.parse(row.get("action_json"))),
                Texts.number(row.get("priority"), 0),
                sql.bool(row.get("stop_on_match")),
                Texts.number(row.get("max_hits"), 0),
                row.get("remark") == null ? null : String.valueOf(row.get("remark"))));
        }
        return rules;
    }

    /**
     * 执行一个场景。facts 由调用方按场景组装（管理员测试可直传），引擎不认业务库里的原始行，
     * 这样「同一场景两套事实口径」这种坑不会出现。
     *
     * 匹配按 rule_group 分组：组内按 priority 降序逐条求值，stop_on_match 只结束本组，
     * max_hits 达到上限也只关本组；其它组照常匹配。未分组的规则同属默认组，
     * 因此单人场景「最高优先级命中即出结果」的老语义不变。
     */
    public Outcome execute(String scene, Map<String, Object> facts) {
        List<Rule> rules = enabledRules(scene);
        List<Hit> hits = new ArrayList<>();
        List<Skipped> skipped = new ArrayList<>();
        Map<String, Integer> groupHits = new LinkedHashMap<>();
        Set<String> closedGroups = new LinkedHashSet<>();

        for (Rule rule : rules) {
            // 组一旦停止匹配（命中 stop_on_match 规则或达到 max_hits），组内后面的规则不再看
            if (closedGroups.contains(rule.group())) continue;

            RuleCondition.Result result = RuleCondition.evaluate(rule.condition(), facts);
            switch (result.outcome()) {
                case HIT -> {
                    Map<String, Object> output = resolve(rule.action(), facts);
                    hits.add(new Hit(rule.code(), rule.name(), rule.priority(), result.traces(), output,
                        explain(rule, result, output)));
                    int count = groupHits.merge(rule.group(), 1, Integer::sum);
                    if (rule.stopOnMatch() || (rule.maxHits() > 0 && count >= rule.maxHits())) {
                        closedGroups.add(rule.group());
                    }
                }
                case UNDECIDABLE -> skipped.add(new Skipped(rule.code(), result.reason()));
                case MISS -> {
                    // 条件不满足是正常结果，不记 skipped（skipped 只放「判不了」的规则）
                }
            }
        }
        return outcome(hits, skipped, scene, rules.size());
    }

    /**
     * 把命中清单合并成一份结论。合并口径是通用的，引擎不认识业务词汇：
     *
     * - 数组字段（`actions` / `causes` / `findings` …）：按命中顺序去重后合并，**保留原始对象**，
     *   所以动作照样可以写成 {priority, owner, action} 这样的富结构，不会被字符串化成 "{priority=HIGH}"；
     * - 标量字段（`cause` / `cause_label` …）：取第一条命中的值（cause 同时汇总进 causes 列表）；
     * - `severity`：取所有命中里最严重的一个（低 < 中 < 高），这样「基准档归定档组、关键词规则命中即抬档」
     *   不需要引擎认识「持续恶化」这类业务词汇。
     */
    private Outcome outcome(List<Hit> hits, List<Skipped> skipped, String scene, int ruleCount) {
        Map<String, Map<String, Object>> arrays = new LinkedHashMap<>();
        Map<String, Object> scalars = new LinkedHashMap<>();
        List<String> ruleRefs = new ArrayList<>();
        String severity = null;
        int severityRank = -1;

        for (Hit hit : hits) {
            ruleRefs.add(hit.ruleCode());
            for (Map.Entry<String, Object> entry : hit.output().entrySet()) {
                String key = entry.getKey();
                Object value = entry.getValue();
                if (value == null) continue;

                if (value instanceof List<?> list) {
                    Map<String, Object> merged = arrays.computeIfAbsent(key, name -> new LinkedHashMap<>());
                    for (Object item : list) {
                        if (item != null) merged.putIfAbsent(literal(item), item);
                    }
                    continue;
                }
                if ("severity".equals(key)) {
                    int rank = severityRank(String.valueOf(value));
                    if (rank > severityRank) {
                        severity = String.valueOf(value);
                        severityRank = rank;
                    }
                    continue;
                }
                if (!scalars.containsKey(key)) {
                    scalars.put(key, value);
                }
                if ("cause".equals(key)) {
                    arrays.computeIfAbsent("causes", name -> new LinkedHashMap<>())
                        .putIfAbsent(literal(value), value);
                }
            }
        }

        boolean matched = !hits.isEmpty();
        BigDecimal confidence = matched
            ? CONFIDENCE_BASE.add(CONFIDENCE_STEP.multiply(BigDecimal.valueOf(hits.size()))).min(CONFIDENCE_CAP)
            : UNMATCHED_CONFIDENCE;

        Map<String, Object> verdict = new LinkedHashMap<>();
        for (Map.Entry<String, Map<String, Object>> entry : arrays.entrySet()) {
            verdict.put(entry.getKey(), new ArrayList<>(entry.getValue().values()));
        }
        for (Map.Entry<String, Object> entry : scalars.entrySet()) {
            verdict.put(entry.getKey(), entry.getValue());
        }
        if (severity != null) {
            verdict.put("severity", severity);
        }
        verdict.put("rule_refs", ruleRefs);
        verdict.put("confidence", confidence);

        String unmatchedReason = matched ? null : unmatchedReason(scene, ruleCount);
        String explanation = clip(matched ? summary(hits) : unmatchedReason);
        return new Outcome(matched, hits, skipped, verdict, explanation, confidence, unmatchedReason);
    }

    private static String explain(Rule rule, RuleCondition.Result result, Map<String, Object> output) {
        String name = rule.name() == null || rule.name().isBlank() ? "" : "（" + rule.name() + "）";
        String basis = result.traces().isEmpty() ? String.valueOf(rule.remark()) : String.join("；", result.traces());
        List<String> unresolved = new ArrayList<>();
        for (Map.Entry<String, Object> entry : output.entrySet()) {
            if (entry.getKey().endsWith("_from")) unresolved.add(String.valueOf(entry.getValue()));
        }
        String suffix = unresolved.isEmpty() ? "" : "（引用事实 " + String.join("、", unresolved) + " 没取到，输出里缺对应字段）";
        return "命中 " + rule.code() + name + "：" + basis + suffix;
    }

    /**
     * 解析 action_json 里以 _from 结尾的字段：值写事实名，输出时换成该事实的当前值。
     *
     * 这条是为了让规则不必为每种气体、每个档位各写一条（3 种气体 × 6 个档位 = 18 条），
     * 「归因取 gas_rule 的 attribution、措施取 gas_rule 的 actions」就能写成一条规则。
     * 取不到时把 _from 原样留在输出里：排障时一眼能看出是哪个事实没给到，不会悄悄少一个字段。
     * action_json 里若同时写了同名字段（如 cause），显式值优先。
     */
    static Map<String, Object> resolve(Map<String, Object> action, Map<String, Object> facts) {
        Map<String, Object> output = new LinkedHashMap<>();
        for (Map.Entry<String, Object> entry : action.entrySet()) {
            String key = entry.getKey();
            Object value = entry.getValue();
            if (!key.endsWith("_from") || !(value instanceof String name) || name.isBlank()) {
                output.put(key, fill(value, facts));
                continue;
            }
            String target = key.substring(0, key.length() - "_from".length());
            Object referenced = facts.get(name);
            if (referenced == null) {
                output.put(key, name);
                continue;
            }
            if (!output.containsKey(target)) output.put(target, fill(referenced, facts));
        }
        return output;
    }

    /**
     * 输出里的字符串支持 {fact} 占位：替换成该事实的当前值，让规则文案带得上实时数字
     * （如「岗位要求 {skill_required_people} 人 / 实际 {skill_level_people} 人」）。
     *
     * 事实是「量」、规则是「阈值与文案」——引擎不做算术，所以比例、金额这类派生值由调用方在
     * 组装 facts 时算好，规则只负责判档与说人话。取不到的事实保留原占位符，排障时一眼可见。
     */
    private static Object fill(Object value, Map<String, Object> facts) {
        if (value instanceof String text) {
            return placeholders(text, facts);
        }
        if (value instanceof List<?> list) {
            List<Object> filled = new ArrayList<>(list.size());
            for (Object item : list) filled.add(fill(item, facts));
            return filled;
        }
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> filled = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                filled.put(String.valueOf(entry.getKey()), fill(entry.getValue(), facts));
            }
            return filled;
        }
        return value;
    }

    private static String placeholders(String template, Map<String, Object> facts) {
        if (template.indexOf('{') < 0) {
            return template;
        }
        String result = template;
        for (Map.Entry<String, Object> fact : facts.entrySet()) {
            String token = "{" + fact.getKey() + "}";
            if (result.contains(token)) {
                result = result.replace(token, factText(fact.getValue()));
            }
        }
        return result;
    }

    /** 事实值的展示形态：数值去掉多余的零（12.00 → 12），其余照原样。 */
    private static String factText(Object raw) {
        if (raw == null) return "";
        if (raw instanceof BigDecimal value) return value.stripTrailingZeros().toPlainString();
        if (raw instanceof Number value) {
            BigDecimal decimal = new BigDecimal(value.toString()).stripTrailingZeros();
            return decimal.scale() <= 0 ? decimal.toBigInteger().toString() : decimal.toPlainString();
        }
        return String.valueOf(raw);
    }

    /** 去重用的字面量：富结构（Map / List）按内容展开，保证「同样的动作只留一条」可复现。 */
    private static String literal(Object raw) {
        if (raw instanceof Map<?, ?> map) {
            StringBuilder builder = new StringBuilder("{");
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                builder.append(entry.getKey()).append('=').append(literal(entry.getValue())).append(';');
            }
            return builder.append('}').toString();
        }
        if (raw instanceof List<?> list) {
            StringBuilder builder = new StringBuilder("[");
            for (Object item : list) builder.append(literal(item)).append(',');
            return builder.append(']').toString();
        }
        return String.valueOf(raw);
    }

    /** 严重度排序：低 < 中 < 高；认不出的取值按 0 算，只在还没有取值时兜底。 */
    private static int severityRank(String severity) {
        return switch (severity) {
            case "高" -> 3;
            case "中" -> 2;
            case "低" -> 1;
            default -> 0;
        };
    }

    private static String summary(List<Hit> hits) {
        List<String> parts = new ArrayList<>();
        for (Hit hit : hits) parts.add(hit.explanation());
        return String.join("；", parts);
    }

    private static String unmatchedReason(String scene, int ruleCount) {
        return ruleCount == 0
            ? "场景 " + scene + " 下没有启用中的规则"
            : "场景 " + scene + " 下 " + ruleCount + " 条启用规则均未命中";
    }

    private static String clip(String text) {
        if (text == null) return "";
        return text.length() <= EXPLANATION_LIMIT ? text : text.substring(0, EXPLANATION_LIMIT);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object raw) {
        return raw instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }
}
