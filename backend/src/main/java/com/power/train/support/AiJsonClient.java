package com.power.train.support;

import com.power.train.store.Sql;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * 大模型 JSON 调用客户端：输入两段提示词，输出一个 JSON 对象，别的什么都不做。
 *
 * 与 ReportAnalysisService 共用同一套 ai.* 配置（application.yml 的 ai.enabled / ai.base-url /
 * ai.model / ai.api-key / ai.timeout-seconds），不新增配置项 —— 全系统只有一份大模型口径。
 * AI 是可选增强：未配置时不发起任何请求，由调用方回退规则结论（source=rule）。
 */
@Component
public class AiJsonClient {

    private static final Logger log = LoggerFactory.getLogger(AiJsonClient.class);

    /**
     * Anthropic 协议要求显式给 max_tokens（不给直接 400）。
     * 思维链模型（deepseek-v4.1-flash / glm / qwen3.8-max）把思考也算进这个预算：
     * 给 4096 时实测出现过「思考把额度吃光、只剩 thinking 块、没有正文」的情况，所以留足余量。
     */
    private static final int ANTHROPIC_MAX_TOKENS = 16000;
    private static final String ANTHROPIC_VERSION = "2023-06-01";

    private final Sql sql;

    @Value("${ai.enabled:false}") private boolean aiEnabled;
    @Value("${ai.base-url:https://api.openai.com/v1}") private String aiBaseUrl;
    @Value("${ai.model:gpt-4o-mini}") private String aiModel;
    @Value("${ai.api-key:}") private String aiApiKey;
    @Value("${ai.timeout-seconds:20}") private int aiTimeoutSeconds;

    /**
     * 公司运行诊断 Agent 的专属大模型配置（可选）：本地为 sft17_exec 专用 adapter，
     * 与个人诊断（sft16_3b）分端口部署。三个值都不配时自动回落到上面那份共用配置，
     * 行为与改造前完全一致 —— 未配置 exec 时不影响任何既有调用方。
     */
    @Value("${ai.exec-base-url:}") private String execBaseUrl;
    @Value("${ai.exec-model:}") private String execModel;
    @Value("${ai.exec-timeout-seconds:300}") private int execTimeoutSeconds;

    public AiJsonClient(Sql sql) {
        this.sql = sql;
    }

    /** 是否已配置可用的大模型（ai.enabled=true 且 api-key 非空）。 */
    public boolean available() {
        return aiEnabled && aiApiKey != null && !aiApiKey.isBlank();
    }

    public String modelName() {
        return aiModel;
    }

    /** 公司诊断用的模型名（未配 exec 专属模型时与主模型相同，只用于日志与界面标注）。 */
    public String execModelName() {
        return execBaseUrl == null || execBaseUrl.isBlank() ? aiModel : execModel;
    }

    /**
     * 公司运行诊断 Agent 的 JSON 调用入口：配置了 ai.exec-base-url 时走专属端点，
     * 否则与 completeJson 完全同路。重试语义与主链路一致（形状不合格重试一次）。
     */
    public Map<String, Object> completeJsonExec(String systemPrompt, String userPrompt) {
        boolean dedicated = execBaseUrl != null && !execBaseUrl.isBlank();
        String baseUrl = dedicated ? execBaseUrl : aiBaseUrl;
        String model = dedicated ? execModel : aiModel;
        int timeout = dedicated ? execTimeoutSeconds : aiTimeoutSeconds;
        try {
            return completeJsonOnce(systemPrompt, userPrompt, baseUrl, model, aiApiKey, timeout);
        } catch (IllegalStateException first) {
            if (!String.valueOf(first.getMessage()).contains("JSON")) {
                throw first;
            }

            log.warn("公司诊断大模型返回形状不合格，重试一次：{}", first.getMessage());
            return completeJsonOnce(systemPrompt, userPrompt, baseUrl, model, aiApiKey, timeout);
        }
    }

    /**
     * 调用大模型并解析成 JSON 对象；任何环节失败都抛异常，由调用方决定回退。
     *
     * 小参数量模型（如 3B）偶发「前置一句解释 / 输出两个 JSON / 尾部闲聊」，整段不是合法 JSON。
     * 这类形状问题只重试一次即可把命中率拉回来（实测 3B 4 次里 1 次不合格）；
     * 网络、鉴权、超时一类错误不重试，直接交给调用方回退，避免把超时翻倍。
     */
    public Map<String, Object> completeJson(String systemPrompt, String userPrompt) {
        try {
            return completeJsonOnce(systemPrompt, userPrompt, aiBaseUrl, aiModel, aiApiKey, aiTimeoutSeconds);
        } catch (IllegalStateException first) {
            if (!String.valueOf(first.getMessage()).contains("JSON")) {
                throw first;
            }

            log.warn("大模型返回形状不合格，重试一次：{}", first.getMessage());
            return completeJsonOnce(systemPrompt, userPrompt, aiBaseUrl, aiModel, aiApiKey, aiTimeoutSeconds);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> completeJsonOnce(String systemPrompt, String userPrompt,
                                                 String baseUrl, String model, String apiKey, int timeoutSeconds) {
        if (!available()) {
            throw new IllegalStateException("未配置大模型（ai.enabled=false 或 ai.api-key 为空）");
        }

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(timeoutSeconds));
        factory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));
        RestClient client = RestClient.builder().requestFactory(factory).build();

        // 两套协议：地址是 Anthropic 形状（如 https://…/apps/anthropic、api.anthropic.com）走 /v1/messages，
        // 其余按 OpenAI 兼容（/chat/completions）。判定只看地址，不新增配置项，换地址即换协议。
        boolean anthropic = anthropic(baseUrl);

        Map<String, Object> body = new LinkedHashMap<>();
        RestClient.RequestBodySpec spec;
        if (anthropic) {
            // Anthropic 没有 response_format，靠提示词约束 + 契约校验 + 兜底保证形状
            body.put("model", model);
            body.put("max_tokens", ANTHROPIC_MAX_TOKENS);
            body.put("temperature", 0.2);
            body.put("system", systemPrompt);
            body.put("messages", List.of(Map.of("role", "user", "content", userPrompt)));
            spec = client.post()
                .uri(baseUrl + "/v1/messages")
                .header("x-api-key", apiKey)
                .header("anthropic-version", ANTHROPIC_VERSION)
                .contentType(MediaType.APPLICATION_JSON);
        } else {
            body.put("model", model);
            body.put("temperature", 0.2);
            body.put("response_format", Map.of("type", "json_object"));
            body.put("messages", List.of(
                Map.of("role", "system", "content", systemPrompt),
                Map.of("role", "user", "content", userPrompt)));
            spec = client.post()
                .uri(baseUrl + "/chat/completions")
                .header("Authorization", "Bearer " + apiKey)
                .contentType(MediaType.APPLICATION_JSON);
        }

        // 不走消息转换器：有的网关把返回标成 application/octet-stream，交给 RestClient 转 Map / String 都会直接失败。
        // 统一读原始字节解成 UTF-8 文本，非 2xx 时把网关的错误正文带出来（401 / 404 模型不存在 / 400 参数不支持）。
        String raw = spec.body(body).exchange((request, response) -> {
            String text = new String(response.getBody().readAllBytes(), StandardCharsets.UTF_8);
            if (response.getStatusCode().isError()) {
                throw new IllegalStateException("大模型返回 " + response.getStatusCode().value()
                    + "：" + excerpt(text));
            }
            return text;
        });
        if (raw == null || raw.isBlank()) {
            throw new IllegalStateException("大模型返回为空");
        }

        // 拿到的是文本，自己解析成 JSON 对象
        Object decoded = sql.parse(raw);
        if (!(decoded instanceof Map<?, ?> decodedMap)) {
            throw new IllegalStateException("大模型返回不是 JSON 对象");
        }
        Map<String, Object> response = new LinkedHashMap<>();
        decodedMap.forEach((key, value) -> response.put(String.valueOf(key), value));

        String content = anthropic ? anthropicText(response) : openAiText(response);

        Map<?, ?> map = parseJsonObject(String.valueOf(content));
        if (map == null) {
            String preview = raw.length() <= 400 ? raw : raw.substring(raw.length() - 400);
            log.warn("大模型未返回 JSON 对象，响应长度 {}，结尾 400 字：{}", raw.length(), preview);
            throw new IllegalStateException("大模型未返回 JSON 对象");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        map.forEach((key, value) -> result.put(String.valueOf(key), value));
        log.info("大模型 {} 返回 JSON，顶层字段 {} 个", model, result.size());
        return result;
    }

    /** 地址是 Anthropic 形状时走 /v1/messages；其余按 OpenAI 兼容处理。 */
    private boolean anthropic(String base0) {
        String base = base0 == null ? "" : base0.toLowerCase();
        return base.endsWith("/anthropic") || base.contains("anthropic.com");
    }

    /** OpenAI 兼容：choices[0].message.content 就是 JSON 文本。 */
    @SuppressWarnings("unchecked")
    private static String openAiText(Map<String, Object> response) {
        List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
        if (choices == null || choices.isEmpty()) {
            throw new IllegalStateException("大模型未返回候选结果");
        }
        Object message = choices.get(0).get("message");
        if (!(message instanceof Map<?, ?> msg)) {
            throw new IllegalStateException("大模型返回结构异常");
        }
        Object content = msg.get("content");
        if (content == null) {
            throw new IllegalStateException("大模型返回内容为空");
        }
        return String.valueOf(content);
    }

    /**
     * Anthropic：content 是块数组，取第一个 type=text 的块。
     * 带思维链的模型（deepseek / glm / qwen3.8-max）会先给 thinking 块，不能直接取第 0 块。
     */
    private static String anthropicText(Map<String, Object> response) {
        Object blocks = response.get("content");
        if (!(blocks instanceof List<?> list) || list.isEmpty()) {
            throw new IllegalStateException("大模型未返回内容块");
        }
        for (Object block : list) {
            if (block instanceof Map<?, ?> item && "text".equals(String.valueOf(item.get("type")))) {
                Object text = item.get("text");
                if (text != null && !String.valueOf(text).isBlank()) {
                    return String.valueOf(text);
                }
            }
        }
        throw new IllegalStateException("大模型只返回了思维链、没有正文文本块（stop_reason="
            + response.getOrDefault("stop_reason", "未知") + "，多半是 max_tokens 被思考用尽）");
    }

    /** 网关错误正文可能很长，截断后再进 fallback_note。 */
    private static String excerpt(String body) {
        String text = body == null ? "" : body.trim().replaceAll("\\s+", " ");
        return text.length() <= 300 ? text : text.substring(0, 300) + "…";
    }

    /** 有的模型会把 JSON 包在 markdown 代码块里，去掉首尾围栏再解析。 */
    private static String stripFence(String content) {
        String text = content == null ? "" : content.trim();
        char newline = (char) 10;
        if (!text.startsWith("```")) {
            return text;
        }
        int firstBreak = text.indexOf(newline);
        int lastFence = text.lastIndexOf("```");
        if (firstBreak < 0 || lastFence <= firstBreak) {
            return text;
        }
        return text.substring(firstBreak + 1, lastFence).trim();
    }

    /**
     * 解析出 JSON 对象：先整段解析；不成就退一步截取第一个配平的 {@code {...}}。
     * 后者专门救「前面多说了一句话」「输出了两个对象」「结尾还有一句话」这三种小模型常见偏差，
     * 不至于因为一句废话就把整个结论降级成规则兜底。
     */
    private Map<?, ?> parseJsonObject(String content) {
        String text = stripFence(content);
        Map<?, ?> direct = tryParseObject(text);
        if (direct != null) {
            return direct;
        }

        String balanced = firstJsonObject(text);
        return balanced == null || balanced.equals(text) ? null : tryParseObject(balanced);
    }

    private Map<?, ?> tryParseObject(String text) {
        try {
            Object parsed = sql.parse(text);
            return parsed instanceof Map<?, ?> map ? map : null;
        } catch (RuntimeException ex) {
            return null;
        }
    }

    /** 扫出第一个左右花括号配平的对象，跳过字符串内部的括号与转义。 */
    private static String firstJsonObject(String text) {
        int start = text.indexOf('{');
        if (start < 0) {
            return null;
        }
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = start; i < text.length(); i++) {
            char c = text.charAt(i);
            if (inString) {
                if (escaped) {
                    escaped = false;
                } else if (c == '\\') {
                    escaped = true;
                } else if (c == '"') {
                    inString = false;
                }
                continue;
            }
            if (c == '"') {
                inString = true;
            } else if (c == '{') {
                depth++;
            } else if (c == '}') {
                depth--;
                if (depth == 0) {
                    return text.substring(start, i + 1);
                }
            }
        }
        return null;
    }
}
