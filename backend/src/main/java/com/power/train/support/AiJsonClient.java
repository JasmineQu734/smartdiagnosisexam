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

    /** 调用大模型并解析成 JSON 对象；任何环节失败都抛异常，由调用方决定回退。 */
    @SuppressWarnings("unchecked")
    public Map<String, Object> completeJson(String systemPrompt, String userPrompt) {
        if (!available()) {
            throw new IllegalStateException("未配置大模型（ai.enabled=false 或 ai.api-key 为空）");
        }

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(aiTimeoutSeconds));
        factory.setReadTimeout(Duration.ofSeconds(aiTimeoutSeconds));
        RestClient client = RestClient.builder().requestFactory(factory).build();

        // 两套协议：地址是 Anthropic 形状（如 https://…/apps/anthropic、api.anthropic.com）走 /v1/messages，
        // 其余按 OpenAI 兼容（/chat/completions）。判定只看地址，不新增配置项，换地址即换协议。
        boolean anthropic = anthropic();

        Map<String, Object> body = new LinkedHashMap<>();
        RestClient.RequestBodySpec spec;
        if (anthropic) {
            // Anthropic 没有 response_format，靠提示词约束 + 契约校验 + 兜底保证形状
            body.put("model", aiModel);
            body.put("max_tokens", ANTHROPIC_MAX_TOKENS);
            body.put("temperature", 0.2);
            body.put("system", systemPrompt);
            body.put("messages", List.of(Map.of("role", "user", "content", userPrompt)));
            spec = client.post()
                .uri(aiBaseUrl + "/v1/messages")
                .header("x-api-key", aiApiKey)
                .header("anthropic-version", ANTHROPIC_VERSION)
                .contentType(MediaType.APPLICATION_JSON);
        } else {
            body.put("model", aiModel);
            body.put("temperature", 0.2);
            body.put("response_format", Map.of("type", "json_object"));
            body.put("messages", List.of(
                Map.of("role", "system", "content", systemPrompt),
                Map.of("role", "user", "content", userPrompt)));
            spec = client.post()
                .uri(aiBaseUrl + "/chat/completions")
                .header("Authorization", "Bearer " + aiApiKey)
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

        Object parsed = sql.parse(stripFence(String.valueOf(content)));
        if (!(parsed instanceof Map<?, ?> map)) {
            String preview = raw.length() <= 400 ? raw : raw.substring(raw.length() - 400);
            log.warn("大模型未返回 JSON 对象，响应长度 {}，结尾 400 字：{}", raw.length(), preview);
            throw new IllegalStateException("大模型未返回 JSON 对象");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        map.forEach((key, value) -> result.put(String.valueOf(key), value));
        log.info("大模型 {} 返回 JSON，顶层字段 {} 个", aiModel, result.size());
        return result;
    }

    /** 地址是 Anthropic 形状时走 /v1/messages；其余按 OpenAI 兼容处理。 */
    private boolean anthropic() {
        String base = aiBaseUrl == null ? "" : aiBaseUrl.toLowerCase();
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
}
