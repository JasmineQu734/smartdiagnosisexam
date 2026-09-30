package com.power.train.rule;

import com.power.train.support.Texts;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 规则条件的声明式求值。
 *
 * 条件是一棵纯数据结构树（组合器 all / any / not + 叶子 {fact, op, value | other_fact}），
 * 算子走白名单，绝不使用 SpEL / eval / 脚本引擎 —— 规则内容由管理员在库里维护，必须当不可信输入对待。
 * 未知算子、类型不匹配、事实缺失一律判为「不可判定」并给出原因：既不抛异常打挂整次执行，也不当成命中。
 */
public final class RuleCondition {

    /** 求值结论：HIT 命中 / MISS 不满足 / UNDECIDABLE 条件或事实不足，无法判定。 */
    public enum Outcome { HIT, MISS, UNDECIDABLE }

    /** traces 记录判定依据（如 current_level(1) lt required_level(3)），用于写 rule_result 的可解释说明。 */
    public record Result(Outcome outcome, List<String> traces, String reason) {

        static Result hit(List<String> traces) {
            return new Result(Outcome.HIT, traces, null);
        }

        static Result miss(List<String> traces) {
            return new Result(Outcome.MISS, traces, null);
        }

        static Result undecidable(List<String> traces, String reason) {
            return new Result(Outcome.UNDECIDABLE, traces, reason);
        }
    }

    /** 需要右值的算子（右值来自 value，或 other_fact 指定的另一个事实）。 */
    private static final List<String> VALUE_OPS = List.of("eq", "ne", "gt", "gte", "lt", "lte", "between",
        "in", "not_in", "contains", "not_contains", "contains_any", "starts_with", "ends_with");

    /** 只看事实本身的算子，不需要右值。 */
    private static final List<String> FLAG_OPS = List.of("is_true", "is_false", "exists", "missing");

    private RuleCondition() {
    }

    public static Result evaluate(Object node, Map<String, Object> facts) {
        if (!(node instanceof Map<?, ?> map) || map.isEmpty()) {
            return Result.undecidable(List.of(), "条件为空或不是 JSON 对象");
        }
        if (map.containsKey("all")) return evaluateAll(map.get("all"), facts);
        if (map.containsKey("any")) return evaluateAny(map.get("any"), facts);
        if (map.containsKey("not")) return evaluateNot(map.get("not"), facts);
        return evaluateLeaf(map, facts);
    }

    private static Result evaluateAll(Object raw, Map<String, Object> facts) {
        List<?> children = asList(raw);
        if (children == null || children.isEmpty()) {
            return Result.undecidable(List.of(), "all 条件为空");
        }
        List<String> traces = new ArrayList<>();
        Set<String> reasons = new LinkedHashSet<>();
        for (Object child : children) {
            Result result = evaluate(child, facts);
            traces.addAll(result.traces());
            if (result.outcome() == Outcome.MISS) return Result.miss(traces);
            if (result.outcome() == Outcome.UNDECIDABLE) reasons.add(result.reason());
        }
        return reasons.isEmpty() ? Result.hit(traces) : Result.undecidable(traces, String.join("；", reasons));
    }

    private static Result evaluateAny(Object raw, Map<String, Object> facts) {
        List<?> children = asList(raw);
        if (children == null || children.isEmpty()) {
            return Result.undecidable(List.of(), "any 条件为空");
        }
        List<String> traces = new ArrayList<>();
        Set<String> reasons = new LinkedHashSet<>();
        for (Object child : children) {
            Result result = evaluate(child, facts);
            traces.addAll(result.traces());
            if (result.outcome() == Outcome.HIT) return Result.hit(traces);
            if (result.outcome() == Outcome.UNDECIDABLE) reasons.add(result.reason());
        }
        return reasons.isEmpty() ? Result.miss(traces) : Result.undecidable(traces, String.join("；", reasons));
    }

    private static Result evaluateNot(Object raw, Map<String, Object> facts) {
        Result result = evaluate(raw, facts);
        return switch (result.outcome()) {
            case HIT -> Result.miss(result.traces());
            case MISS -> Result.hit(result.traces());
            case UNDECIDABLE -> result;
        };
    }

    private static Result evaluateLeaf(Map<?, ?> leaf, Map<String, Object> facts) {
        String fact = text(leaf.get("fact"));
        String op = text(leaf.get("op"));
        if (fact == null) return Result.undecidable(List.of(), "条件缺少 fact");
        if (op == null) return Result.undecidable(List.of(), "条件缺少 op");
        op = op.toLowerCase();

        if (FLAG_OPS.contains(op)) return evaluateFlag(fact, op, facts);
        if (!VALUE_OPS.contains(op)) return Result.undecidable(List.of(), "不支持的算子 " + op);
        return evaluateValue(fact, op, leaf, facts);
    }

    private static Result evaluateFlag(String fact, String op, Map<String, Object> facts) {
        boolean present = facts.containsKey(fact) && facts.get(fact) != null;
        if ("exists".equals(op) || "missing".equals(op)) {
            String trace = fact + "(" + (present ? "存在" : "缺失") + ") " + op;
            boolean want = "exists".equals(op);
            return present == want ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
        }
        if (!present) {
            return Result.undecidable(List.of(), "facts 缺少 " + fact);
        }
        String trace = fact + "(" + plain(facts.get(fact)) + ") " + op;
        boolean want = "is_true".equals(op);
        return Texts.truthy(facts.get(fact)) == want ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
    }

    private static Result evaluateValue(String fact, String op, Map<?, ?> leaf, Map<String, Object> facts) {
        if (!facts.containsKey(fact) || facts.get(fact) == null) {
            return Result.undecidable(List.of(), "facts 缺少 " + fact);
        }
        Object left = facts.get(fact);

        String otherFact = text(leaf.get("other_fact"));
        Object right;
        if (otherFact != null) {
            if (!facts.containsKey(otherFact) || facts.get(otherFact) == null) {
                return Result.undecidable(List.of(), "facts 缺少 " + otherFact);
            }
            right = facts.get(otherFact);
        } else {
            right = leaf.get("value");
            if (right == null) {
                return Result.undecidable(List.of(), fact + " 的 " + op + " 缺少 value 或 other_fact");
            }
        }
        String trace = trace(fact, left, op, otherFact, right);

        if ("between".equals(op)) {
            List<?> bounds = asList(right);
            if (bounds == null || bounds.size() < 2) {
                return Result.undecidable(List.of(trace), "between 需要 [下界, 上界] 两个值");
            }
            BigDecimal value = Texts.decimal(left);
            BigDecimal low = Texts.decimal(bounds.get(0));
            BigDecimal high = Texts.decimal(bounds.get(1));
            if (value == null || low == null || high == null) {
                return Result.undecidable(List.of(trace), "between 只支持数值比较");
            }
            boolean inside = value.compareTo(low) >= 0 && value.compareTo(high) <= 0;
            return inside ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
        }

        if ("in".equals(op) || "not_in".equals(op)) {
            List<?> options = asList(right);
            if (options == null || options.isEmpty()) {
                return Result.undecidable(List.of(trace), op + " 需要一个非空清单");
            }
            boolean found = false;
            for (Object option : options) {
                if (equals(left, option)) {
                    found = true;
                    break;
                }
            }
            boolean want = "in".equals(op);
            return found == want ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
        }

        if ("eq".equals(op) || "ne".equals(op)) {
            boolean same = equals(left, right);
            boolean want = "eq".equals(op);
            return same == want ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
        }

        if ("contains".equals(op) || "not_contains".equals(op) || "starts_with".equals(op) || "ends_with".equals(op)) {
            String leftText = plain(left);
            String rightText = plain(right);
            boolean found = switch (op) {
                case "starts_with" -> leftText.startsWith(rightText);
                case "ends_with" -> leftText.endsWith(rightText);
                default -> leftText.contains(rightText);
            };
            boolean want = !"not_contains".equals(op);
            return found == want ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
        }

        if ("contains_any".equals(op)) {
            return containsAny(left, right, trace);
        }

        BigDecimal value = Texts.decimal(left);
        BigDecimal target = Texts.decimal(right);
        if (value == null || target == null) {
            return Result.undecidable(List.of(trace), "算子 " + op + " 只支持数值比较，" + fact + " 或右值不是数值");
        }
        int compare = value.compareTo(target);
        boolean ok = switch (op) {
            case "gt" -> compare > 0;
            case "gte" -> compare >= 0;
            case "lt" -> compare < 0;
            case "lte" -> compare <= 0;
            default -> false;
        };
        return ok ? Result.hit(List.of(trace)) : Result.miss(List.of(trace));
    }

    /** 文本命中清单里任意一项即成立（关键词规则用：一个规则挂一组同义关键词）。 */
    private static Result containsAny(Object left, Object right, String trace) {
        if (left == null) {
            return Result.miss(List.of(trace));
        }
        List<?> options = right instanceof List<?> list ? list : List.of(right);
        if (options.isEmpty()) {
            return Result.undecidable(List.of(trace), "contains_any 需要一个非空关键词清单");
        }
        String leftText = plain(left);
        for (Object option : options) {
            if (leftText.contains(plain(option))) {
                return Result.hit(List.of(trace));
            }
        }
        return Result.miss(List.of(trace));
    }

    private static List<?> asList(Object raw) {
        return raw instanceof List<?> list ? list : null;
    }

    private static String text(Object raw) {
        if (raw == null) return null;
        String value = String.valueOf(raw).trim();
        return value.isEmpty() ? null : value;
    }

    /** eq / ne / in 的相等判断：两边都是数值时按数值比（1 与 1.0 相等），否则按文本比。 */
    private static boolean equals(Object left, Object right) {
        BigDecimal leftDecimal = Texts.decimal(left);
        BigDecimal rightDecimal = Texts.decimal(right);
        if (leftDecimal != null && rightDecimal != null) return leftDecimal.compareTo(rightDecimal) == 0;
        return plain(left).equals(plain(right));
    }

    private static String trace(String fact, Object left, String op, String otherFact, Object right) {
        if (otherFact != null) {
            return fact + "(" + plain(left) + ") " + op + " " + otherFact + "(" + plain(right) + ")";
        }
        return fact + "(" + plain(left) + ") " + op + " " + plain(right);
    }

    private static String plain(Object raw) {
        if (raw == null) return "null";
        if (raw instanceof BigDecimal value) return value.stripTrailingZeros().toPlainString();
        if (raw instanceof Number value) {
            BigDecimal decimal = new BigDecimal(value.toString()).stripTrailingZeros();
            return decimal.scale() <= 0 ? decimal.toBigInteger().toString() : decimal.toPlainString();
        }
        if (raw instanceof List<?> list) {
            List<String> items = new ArrayList<>();
            for (Object item : list) items.add(plain(item));
            return "[" + String.join(", ", items) + "]";
        }
        return String.valueOf(raw);
    }
}
