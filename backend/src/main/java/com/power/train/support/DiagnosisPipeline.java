package com.power.train.support;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 诊断 Agent 的公共管道与事实清单口径：查事实 → 提示词 → 大模型出结论 → 契约校验 → 兜底。
 *
 * 个人诊断与公司诊断的差异只有三处：事实从哪来、提示词怎么写、用哪份契约校验；
 * 其余步骤完全一致，所以放在这里，避免两份实现「改一处忘另一处」。
 *
 * 事实清单（facts）的每个条目形如 F3，是结论里所有数字的唯一出处；本类只管清单怎么建、怎么渲染。
 */
public final class DiagnosisPipeline {

    private static final Logger log = LoggerFactory.getLogger(DiagnosisPipeline.class);

    private static final String CONTRACT_FALLBACK = "大模型返回不符合输出契约，已回退内置规则结论：";
    private static final String CALL_FALLBACK = "大模型调用失败，已回退内置规则结论：";
    private static final String OFFLINE_FALLBACK = "未配置大模型（ai.enabled=false 或 ai.api-key 为空），已回退内置规则结论";

    /** 兜底结论的置信度：内置规则是确定的，不给模型那种「可能不太准」的低分。 */
    private static final double CONFIDENCE_FALLBACK = 0.8;
    private static final double CONFIDENCE_MODEL = 0.75;
    /** 结论里查到「没有出处的数字」时的置信度上限：不拦截结论，但明确降低可信度。 */
    private static final double CONFIDENCE_UNVERIFIED = 0.6;

    private DiagnosisPipeline() {
    }

    /** 一次大模型尝试：payload 非空表示结论可用；否则 fallback 写明这次为什么没用上模型。 */
    public record ModelRun(Map<String, Object> payload, String fallback) {

        public boolean usable() {
            return payload != null;
        }
    }

    /**
     * 调大模型并做契约硬校验（字段缺失、类型不对、枚举越界一律判不合格）。
     * label 只用于日志（如「个人诊断」「公司诊断」）。
     * 失败不抛异常：回退内置规则结论是设计内的一条正常路径，不是错误。
     */
    public static ModelRun generate(AiJsonClient client, String label, String systemPrompt, String userPrompt,
                                    Function<Map<String, Object>, List<String>> contract) {
        return generate(client, label, systemPrompt, userPrompt, contract, false);
    }

    /**
     * 同上，exec=true 时走公司运行诊断 Agent 的专属端点（AiJsonClient 里 ai.exec-* 配置），
     * 未配置专属端点时与 exec=false 完全同路。重试、契约校验与兜底语义保持一致。
     */
    public static ModelRun generate(AiJsonClient client, String label, String systemPrompt, String userPrompt,
                                    Function<Map<String, Object>, List<String>> contract, boolean exec) {
        if (!client.available()) {
            return new ModelRun(null, OFFLINE_FALLBACK);
        }
        try {
            Map<String, Object> raw = exec
                ? client.completeJsonExec(systemPrompt, userPrompt)
                : client.completeJson(systemPrompt, userPrompt);
            List<String> errors = contract.apply(raw);
            return errors.isEmpty() ? new ModelRun(raw, null) : new ModelRun(null, CONTRACT_FALLBACK + errors.get(0));
        } catch (Exception error) {
            log.warn("{}大模型调用失败，回退规则结论：{}", label, error.getMessage());
            return new ModelRun(null, CALL_FALLBACK + error.getMessage());
        }
    }

    /**
     * 收尾：模型结论做数字软校验（正文里出现、但事实清单里查不到的数字只留痕并降置信度，不拦截结论）；
     * 走兜底时把 fallback_note 写进结果，前端据此提示「这次没走大模型」。
     *
     * result 里由后端写死的运行时字段（编号、时间、来源、证据条数）不参与校验，也不受影响。
     */
    public static Map<String, Object> finish(Map<String, Object> result, ModelRun run, List<Map<String, Object>> facts) {
        if (!run.usable()) {
            result.put("confidence", Texts.number(result.get("confidence"), CONFIDENCE_FALLBACK));
            result.put("fallback_note", run.fallback());
            return result;
        }

        Set<String> allowed = new LinkedHashSet<>();
        for (Map<String, Object> fact : facts) {
            allowed.addAll(DiagnosisContract.numbersOf(Texts.text(fact.get("label")) + " " + Texts.text(fact.get("value"))));
        }
        DiagnosisContract.addDerived(allowed);

        double confidence = Math.min(1.0, Math.max(0.0, Texts.number(result.get("confidence"), CONFIDENCE_MODEL)));
        List<String> unverified = DiagnosisContract.unverifiedNumbers(result, allowed);
        if (!unverified.isEmpty()) {
            result.put("unverified_numbers", unverified);
            confidence = Math.min(confidence, CONFIDENCE_UNVERIFIED);
        }
        result.put("confidence", confidence);
        return result;
    }

    // ---- 结论事后规范：只处理「模型不擅长、但后端有确定答案」的非事实字段 ----

    /** 计划排期的步进天数：课程 → 带教 → 模拟考 的常规节奏，两周一步。 */
    private static final int PLAN_STEP_DAYS = 14;
    /** plan 各步 reason 的相似度阈值：超过就认为在复读，改写成该步自己的说法。 */
    private static final double REPEAT_REASON = 0.8;
    /** reason 的第二个判据：公共前缀长度。实测常见的是「前半句照抄、后半句换词」，占比能卡在阈值之下逃掉。 */
    private static final int REPEAT_PREFIX = 24;
    /** compound_path.benefit 与 why 的相似度阈值：超过就重写 benefit。 */
    private static final double REPEAT_BENEFIT = 0.5;

    /**
     * 个人诊断结论的事后规范。刻意只碰两类字段：
     *
     * 1. plan[].due_at 是「计划日期」而不是事实数据。模型经常把它排到今天之前，或让几步挤在同一天；
     *    一旦出现「早于今天」或「不严格递增」，就整列按今天起、每步 PLAN_STEP_DAYS 天重排。
     * 2. plan[].reason 与 compound_path.benefit 经常被模型复制成同一句话。检测到复读，就改写成
     *    该条目自身字段能支撑的说法（target_skill / to_level / stages 的里程碑），不引入任何新事实。
     *
     * summary / verdict / gaps 等涉及事实的叙述一律不动。调用点在契约校验「通过之后」，
     * 所以它只会把合格结论说得更像样，绝不会把不合格结论「洗」成合格。
     */
    public static void polishPersonal(Map<String, Object> payload, String today) {
        if (payload == null) {
            return;
        }
        List<Map<String, Object>> plan = copyList(payload.get("plan"));
        if (!plan.isEmpty()) {
            reflowDueAt(plan, today);
            rewriteRepeatedReason(plan);
            payload.put("plan", plan);
        }
        if (payload.get("compound_path") instanceof Map<?, ?> raw) {
            Map<String, Object> compound = copyMap(raw);
            rewriteRepeatedBenefit(compound);
            payload.put("compound_path", compound);
        }
    }

    /** 排期只在不「晚于今天且严格递增」时才接管：模型排对了就不动它。 */
    private static void reflowDueAt(List<Map<String, Object>> plan, String today) {
        LocalDate base = parseDate(today);
        if (base == null) {
            return;
        }
        LocalDate previous = null;
        boolean ordered = true;
        for (Map<String, Object> step : plan) {
            LocalDate due = parseDate(Texts.text(step.get("due_at")));
            // 必须是「晚于今天」：首步落在今天等于「今天就到期」，读起来像已经逾期
            if (due == null || !due.isAfter(base) || (previous != null && !due.isAfter(previous))) {
                ordered = false;
                break;
            }
            previous = due;
        }
        if (ordered) {
            return;
        }
        for (int index = 0; index < plan.size(); index++) {
            plan.get(index).put("due_at", base.plusDays((long) (index + 1) * PLAN_STEP_DAYS).toString());
        }
    }

    /** 复读的 reason 换成该步自己的说法：只用它已有的 title / target_skill / to_level，不编新内容。 */
    private static void rewriteRepeatedReason(List<Map<String, Object>> plan) {
        List<String> seen = new ArrayList<>();
        for (Map<String, Object> step : plan) {
            String reason = Texts.text(step.get("reason"));
            if (reason.isBlank()) {
                continue;
            }
            if (!repeats(seen, reason)) {
                seen.add(reason);
                continue;
            }
            String rewritten = distinctReason(step);
            // 改写后仍与已有文案完全相同（例如两步的 target_skill 与 to_level 一样），退回用这一步的标题兜底
            if (seen.contains(rewritten)) {
                String title = Texts.text(step.get("title"));
                rewritten = title.isBlank()
                    ? "承接上一步，按上一步的结论继续推进。"
                    : "承接上一步，本步以「" + title + "」的形式把上一步的内容落地。";
            }
            step.put("reason", rewritten);
            seen.add(rewritten);
        }
    }

    private static String distinctReason(Map<String, Object> step) {
        String title = Texts.text(step.get("title"));
        String skill = Texts.text(step.get("target_skill"));
        String level = Texts.text(step.get("to_level"));
        if (title.isBlank()) {
            return skill.isBlank() ? "承接上一步，按上一步的结论继续推进。"
                : "承接上一步，聚焦" + skill + "的落地验证。";
        }
        String subject = skill.isBlank() ? "上一步的内容" : skill;
        String target = level.isBlank() ? "" : "推进到 " + level + "，";
        return "承接上一步，把" + subject + target + "落点在「" + title + "」。";
    }

    private static boolean repeats(List<String> seen, String text) {
        for (String previous : seen) {
            if (overlap(previous, text) >= REPEAT_REASON || prefixLength(previous, text) >= REPEAT_PREFIX) {
                return true;
            }
        }
        return false;
    }

    /** 公共前缀长度：中文里前 24 个字一模一样，读起来就是同一句话。 */
    private static int prefixLength(String left, String right) {
        int limit = Math.min(left.length(), right.length());
        int index = 0;
        while (index < limit && left.charAt(index) == right.charAt(index)) {
            index++;
        }
        return index;
    }

    /** benefit 不能是 why 的翻版：与 why 太像时，改用各阶段里程碑来回答「走完能得到什么」。 */
    private static void rewriteRepeatedBenefit(Map<String, Object> compound) {
        String why = Texts.text(compound.get("why"));
        String benefit = Texts.text(compound.get("benefit"));
        if (why.isBlank() || benefit.isBlank() || overlap(why, benefit) < REPEAT_BENEFIT) {
            return;
        }
        List<Map<String, Object>> stages = copyList(compound.get("stages"));
        String milestone = "";
        for (Map<String, Object> stage : stages) {
            String value = Texts.text(stage.get("milestone"));
            if (!value.isBlank()) {
                milestone = value;
            }
        }
        compound.put("benefit", milestone.isBlank()
            ? "按上述阶段逐步推进，让缺口逐项转为岗位要求的达标能力。"
            : "按上述阶段逐步推进，以「" + milestone + "」作为最终验收标志。");
    }

    /** 两段文案的最长公共子串占比 = 识别「换了个说法重复同一句」的复读。 */
    private static double overlap(String left, String right) {
        if (left == null || right == null || left.isBlank() || right.isBlank()) {
            return 0.0;
        }
        int[] previous = new int[right.length() + 1];
        int longest = 0;
        for (int i = 1; i <= left.length(); i++) {
            int[] current = new int[right.length() + 1];
            for (int j = 1; j <= right.length(); j++) {
                if (left.charAt(i - 1) == right.charAt(j - 1)) {
                    current[j] = previous[j - 1] + 1;
                    if (current[j] > longest) {
                        longest = current[j];
                    }
                }
            }
            previous = current;
        }
        return (double) longest / Math.min(left.length(), right.length());
    }

    private static LocalDate parseDate(String value) {
        try {
            return value == null || value.isBlank() ? null : LocalDate.parse(value);
        } catch (DateTimeParseException ignored) {
            return null;
        }
    }

    /** 深拷贝一层：polish 只改顶层键，不碰原始对象，避免影响到别处引用的同一份结论。 */
    private static List<Map<String, Object>> copyList(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Map<?, ?> raw) {
                    result.add(copyMap(raw));
                }
            }
        }
        return result;
    }

    private static Map<String, Object> copyMap(Map<?, ?> raw) {
        Map<String, Object> copy = new LinkedHashMap<>();
        raw.forEach((key, value) -> copy.put(String.valueOf(key), value));
        return copy;
    }

    /** 事实清单里新增一条：编号按清单顺序生成（F1、F2…），结论引用它即证明「数字有出处」。 */
    public static void addFact(List<Map<String, Object>> facts, String source, String label, String value) {
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("id", "F" + (facts.size() + 1));
        fact.put("source", source);
        fact.put("label", label);
        fact.put("value", value);
        facts.add(fact);
    }

    /** 事实清单渲染成提示词里的一段：编号 [来源] 说明；取值。 */
    public static String renderFacts(List<Map<String, Object>> facts) {
        StringBuilder builder = new StringBuilder();
        for (Map<String, Object> fact : facts) {
            line(builder, fact.get("id") + " [" + fact.get("source") + "] " + fact.get("label") + "；" + fact.get("value"));
        }
        return builder.toString();
    }

    /** 提示词按行拼接（不用 String.format：规则文案里的 % 与 {} 会被当成占位符）。 */
    public static void line(StringBuilder builder, String value) {
        builder.append(value).append(System.lineSeparator());
    }
}
