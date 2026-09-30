package com.power.train.support;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** 统一响应体：code / message / data / trace_id，字段顺序稳定，便于前端与日志阅读。 */
public final class ApiResponse {

    private ApiResponse() {}

    public static Map<String, Object> ok(Object data) {
        return row("code", 0, "message", "success", "data", data, "trace_id", UUID.randomUUID().toString());
    }

    /** 构造可含 null 的响应字段，Map.of 不接受 null 且最多 10 组键值。 */
    public static Map<String, Object> row(Object... kv) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) {
            map.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return map;
    }
}