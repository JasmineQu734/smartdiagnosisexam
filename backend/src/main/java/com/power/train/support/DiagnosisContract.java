package com.power.train.support;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 诊断结论的输出契约校验（字段定义见 docs/diagnosis_schema.json）。
 *
 * 1）validate*：硬校验。字段缺失、类型不对、枚举越界、数组为空，任意一条不过就判整份结论不合格，
 *    调用方必须回退内置规则结论 —— 宁可用旧结论，也不能把不合格 JSON 送给前端。
 * 2）unverifiedNumbers：软校验。结论正文里出现、但事实清单里查不到的数字，不拦截结论，只留痕到
 *    unverified_numbers，让人一眼看出哪句话的数字对不上库（结论必须可解释到数据）。
 */
public final class DiagnosisContract {

    private static final List<String> SEVERITY = List.of("HIGH", "MEDIUM", "LOW");
    private static final List<String> PRIORITY = List.of("P1", "P2", "P3");
    private static final List<String> KINDS = List.of("课程", "带教", "模拟考");
    private static final List<String> CAUSES = List.of("MIXED", "TALENT_GAP", "SKILL_GAP");

    /** 等级（L3）、步骤（第 2 步）、日期、以及事实编号（F7）都不算「数字结论」：前三个本就不是数字，
     *  事实编号恰恰是结论可解释到数据的最强证据，不能反过来被判成编造。 */
    private static final Pattern IGNORED =
        Pattern.compile("F[0-9]+|L[1-5]|第[0-9]+步|[0-9]{4}-[0-9]{2}-[0-9]{2}");
    private static final Pattern NUMBER = Pattern.compile("[0-9]+(?:[.][0-9]+)?");

    /**
     * 参与数字核对的正文路径（数组会自动展开）。
     * 只核对「陈述现状」的字段：测算类字段（actions.cost_impact / actions.expected / plan.title /
     * compound_path.benefit）本来就允许是预测值，不参与核对，避免把噪声当问题报出来。
     */
    private static final String[][] NARRATIVE = {
        {"summary"},
        {"verdict", "headline"}, {"verdict", "label"}, {"verdict", "reasons"}, {"verdict", "evidence"},
        {"gaps", "impact"},
        {"plan", "reason"},
        {"findings", "title"}, {"findings", "impact"}, {"findings", "evidence"},
        {"compound_path", "why"}
    };

    private DiagnosisContract() {
    }

    // ---- 硬校验 ----

    public static List<String> validatePersonal(Map<String, Object> payload) {
        List<String> errors = new ArrayList<>();
        if (payload == null) {
            return List.of("结论为空");
        }
        text(payload, "summary", "根", errors);
        ratio(payload, "confidence", "根", errors);

        Map<String, Object> verdict = childMap(payload, "verdict", "根", errors);
        if (verdict != null) {
            text(verdict, "headline", "verdict", errors);
            strings(verdict, "reasons", "verdict", errors);
        }

        List<Map<String, Object>> gaps = childMaps(payload, "gaps", "根", errors);
        Set<String> skills = new LinkedHashSet<>();
        for (int index = 0; index < gaps.size(); index++) {
            Map<String, Object> gap = gaps.get(index);
            String where = "gaps[" + index + "]";
            text(gap, "skill", where, errors);
            text(gap, "impact", where, errors);
            text(gap, "action", where, errors);
            level(gap, "current", where, errors);
            level(gap, "required", where, errors);
            level(gap, "future", where, errors);
            enumOf(gap, "severity", SEVERITY, where, errors);
            enumOf(gap, "priority", PRIORITY, where, errors);
            if (!skills.add(String.valueOf(gap.get("skill")))) {
                errors.add(where + ".skill 重复出现：" + gap.get("skill"));
            }
        }

        List<Map<String, Object>> plan = childMaps(payload, "plan", "根", errors);
        for (int index = 0; index < plan.size(); index++) {
            Map<String, Object> step = plan.get(index);
            String where = "plan[" + index + "]";
            positive(step, "step", where, errors);
            enumOf(step, "kind", KINDS, where, errors);
            text(step, "title", where, errors);
            text(step, "target_skill", where, errors);
            text(step, "reason", where, errors);
            pattern(step, "to_level", "L[1-5]", where, errors);
            pattern(step, "due_at", "[0-9]{4}-[0-9]{2}-[0-9]{2}", where, errors);
        }

        Map<String, Object> compound = childMap(payload, "compound_path", "根", errors);
        if (compound != null) {
            text(compound, "title", "compound_path", errors);
            text(compound, "why", "compound_path", errors);
            text(compound, "benefit", "compound_path", errors);
            List<Map<String, Object>> stages = childMaps(compound, "stages", "compound_path", errors);
            for (int index = 0; index < stages.size(); index++) {
                Map<String, Object> stage = stages.get(index);
                String where = "compound_path.stages[" + index + "]";
                text(stage, "phase", where, errors);
                text(stage, "focus", where, errors);
                text(stage, "skills", where, errors);
                text(stage, "milestone", where, errors);
            }
        }
        return errors;
    }

    public static List<String> validateExec(Map<String, Object> payload) {
        List<String> errors = new ArrayList<>();
        if (payload == null) {
            return List.of("结论为空");
        }
        text(payload, "summary", "根", errors);
        ratio(payload, "confidence", "根", errors);

        Map<String, Object> verdict = childMap(payload, "verdict", "根", errors);
        if (verdict != null) {
            enumOf(verdict, "cause", CAUSES, "verdict", errors);
            text(verdict, "label", "verdict", errors);
            text(verdict, "headline", "verdict", errors);
            strings(verdict, "evidence", "verdict", errors);
        }

        List<Map<String, Object>> findings = childMaps(payload, "findings", "根", errors);
        Set<String> titles = new LinkedHashSet<>();
        for (int index = 0; index < findings.size(); index++) {
            Map<String, Object> finding = findings.get(index);
            String where = "findings[" + index + "]";
            text(finding, "title", where, errors);
            text(finding, "impact", where, errors);
            text(finding, "evidence", where, errors);
            if (!titles.add(String.valueOf(finding.get("title")))) {
                errors.add(where + ".title 重复出现：" + finding.get("title"));
            }
        }

        List<Map<String, Object>> actions = childMaps(payload, "actions", "根", errors);
        for (int index = 0; index < actions.size(); index++) {
            Map<String, Object> action = actions.get(index);
            String where = "actions[" + index + "]";
            enumOf(action, "priority", SEVERITY, where, errors);
            text(action, "owner", where, errors);
            text(action, "action", where, errors);
            text(action, "cost_impact", where, errors);
            text(action, "expected", where, errors);
        }

        Map<String, Object> cost = childMap(payload, "cost_summary", "根", errors);
        if (cost != null) {
            amount(cost, "current_total", "cost_summary", errors);
            amount(cost, "optimized_total", "cost_summary", errors);
            amount(cost, "saving", "cost_summary", errors);
            text(cost, "note", "cost_summary", errors);
        }
        return errors;
    }

    // ---- 软校验：数字对账 ----

    /** 从任意文本里抽出所有数字（去掉等级、步骤、日期的干扰），用于和事实清单对账。 */
    public static Set<String> numbersOf(String text) {
        Set<String> numbers = new LinkedHashSet<>();
        if (text == null || text.isBlank()) {
            return numbers;
        }
        Matcher matcher = NUMBER.matcher(IGNORED.matcher(text).replaceAll(" "));
        while (matcher.find()) {
            numbers.add(normalize(matcher.group()));
        }
        return numbers;
    }

    /**
     * 把「由事实算出来的值」也算作可核对：占比（3/4 → 75%）、合计、差额、商。
     * 否则模型写「超限率 75%（3/4）」这种正儿八经从数据推出来的百分比，会被当成编造的数字。
     * 事实条数不多（几十条），两两组合的开销可以忽略。
     */
    public static void addDerived(Set<String> allowed) {
        List<Double> base = new ArrayList<>();
        for (String value : allowed) {
            try {
                double parsed = Double.parseDouble(value);
                if (Math.abs(parsed) <= 100000) {
                    base.add(parsed);
                }
            } catch (NumberFormatException ignored) {
                // 不是数字的条目直接跳过
            }
        }
        if (base.size() < 2 || base.size() > 80) {
            return;
        }
        Set<String> derived = new LinkedHashSet<>();
        for (double left : base) {
            for (double right : base) {
                derived.add(normalize(String.valueOf(left + right)));
                derived.add(normalize(String.valueOf(Math.abs(left - right))));
                if (right != 0) {
                    derived.add(normalize(String.valueOf(Math.round(left * 100 / right))));
                    derived.add(normalize(String.valueOf(left / right)));
                }
            }
        }
        allowed.addAll(derived);
    }

    /** 结论里出现、但事实清单里没有的数字（最多 20 条），留给人工复核。 */
    public static List<String> unverifiedNumbers(Map<String, Object> payload, Set<String> allowed) {
        List<String> unverified = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (String text : narrativeTexts(payload)) {
            Matcher matcher = NUMBER.matcher(IGNORED.matcher(text).replaceAll(" "));
            while (matcher.find()) {
                String number = normalize(matcher.group());
                if (allowed.contains(number) || !seen.add(number)) {
                    continue;
                }
                unverified.add(number + " ← " + excerpt(text));
                if (unverified.size() >= 20) {
                    return unverified;
                }
            }
        }
        return unverified;
    }

    private static List<String> narrativeTexts(Map<String, Object> payload) {
        List<String> texts = new ArrayList<>();
        for (String[] path : NARRATIVE) {
            collect(payload, path, 0, texts);
        }
        return texts;
    }

    private static void collect(Object node, String[] path, int index, List<String> texts) {
        if (node == null) {
            return;
        }
        if (index == path.length) {
            if (node instanceof List<?> list) {
                for (Object item : list) {
                    if (item != null) {
                        texts.add(String.valueOf(item));
                    }
                }
                return;
            }
            texts.add(String.valueOf(node));
            return;
        }
        if (node instanceof Map<?, ?> map) {
            collect(map.get(path[index]), path, index + 1, texts);
            return;
        }
        if (node instanceof List<?> list) {
            for (Object item : list) {
                collect(item, path, index, texts);
            }
        }
    }

    private static String excerpt(String text) {
        String value = text == null ? "" : text.trim();
        return value.length() <= 24 ? value : value.substring(0, 24) + "…";
    }

    private static String normalize(String number) {
        try {
            double value = Double.parseDouble(number);
            if (value == Math.rint(value) && Math.abs(value) < 1e15) {
                return String.valueOf((long) value);
            }
            return String.valueOf(value);
        } catch (NumberFormatException ignored) {
            return number;
        }
    }

    // ---- 字段级断言 ----

    private static void text(Map<String, Object> map, String field, String where, List<String> errors) {
        Object value = map.get(field);
        if (value == null || String.valueOf(value).isBlank()) {
            errors.add(where + "." + field + " 缺失或为空");
        }
    }

    private static void strings(Map<String, Object> map, String field, String where, List<String> errors) {
        Object value = map.get(field);
        if (!(value instanceof List<?> list) || list.isEmpty()) {
            errors.add(where + "." + field + " 必须是非空数组");
            return;
        }
        for (Object item : list) {
            if (item == null || String.valueOf(item).isBlank()) {
                errors.add(where + "." + field + " 存在空条目");
                return;
            }
        }
    }

    private static void enumOf(Map<String, Object> map, String field, List<String> allowed, String where,
                               List<String> errors) {
        Object value = map.get(field);
        if (value == null || !allowed.contains(String.valueOf(value))) {
            errors.add(where + "." + field + " 只能是 " + String.join("/", allowed) + "，实际：" + value);
        }
    }

    private static void pattern(Map<String, Object> map, String field, String regex, String where,
                                List<String> errors) {
        Object value = map.get(field);
        if (value == null || !String.valueOf(value).matches(regex)) {
            errors.add(where + "." + field + " 格式不合法：" + value);
        }
    }

    private static void level(Map<String, Object> map, String field, String where, List<String> errors) {
        Object value = map.get(field);
        if (!(value instanceof Number number) || number.intValue() < 1 || number.intValue() > 5) {
            errors.add(where + "." + field + " 必须是 1-5 的整数，实际：" + value);
        }
    }

    private static void positive(Map<String, Object> map, String field, String where, List<String> errors) {
        Object value = map.get(field);
        if (!(value instanceof Number number) || number.intValue() < 1) {
            errors.add(where + "." + field + " 必须是正整数，实际：" + value);
        }
    }

    private static void ratio(Map<String, Object> map, String field, String where, List<String> errors) {
        Object value = map.get(field);
        if (!(value instanceof Number number) || number.doubleValue() < 0 || number.doubleValue() > 1) {
            errors.add(where + "." + field + " 必须是 0-1 之间的小数，实际：" + value);
        }
    }

    private static void amount(Map<String, Object> map, String field, String where, List<String> errors) {
        if (!(map.get(field) instanceof Number)) {
            errors.add(where + "." + field + " 必须是数字，实际：" + map.get(field));
        }
    }

    private static Map<String, Object> childMap(Map<String, Object> map, String field, String where,
                                                List<String> errors) {
        Object value = map.get(field);
        if (!(value instanceof Map<?, ?> raw)) {
            errors.add(where + "." + field + " 必须是对象");
            return null;
        }
        Map<String, Object> child = new LinkedHashMap<>();
        raw.forEach((key, item) -> child.put(String.valueOf(key), item));
        return child;
    }

    private static List<Map<String, Object>> childMaps(Map<String, Object> map, String field, String where,
                                                       List<String> errors) {
        Object value = map.get(field);
        List<Map<String, Object>> result = new ArrayList<>();
        if (!(value instanceof List<?> list) || list.isEmpty()) {
            errors.add(where + "." + field + " 必须是非空数组");
            return result;
        }
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> raw)) {
                errors.add(where + "." + field + " 数组元素必须是对象");
                continue;
            }
            Map<String, Object> child = new LinkedHashMap<>();
            raw.forEach((key, element) -> child.put(String.valueOf(key), element));
            result.add(child);
        }
        return result;
    }
}
