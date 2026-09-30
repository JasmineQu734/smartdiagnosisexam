package com.power.train.support;

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
        if (!client.available()) {
            return new ModelRun(null, OFFLINE_FALLBACK);
        }
        try {
            Map<String, Object> raw = client.completeJson(systemPrompt, userPrompt);
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
