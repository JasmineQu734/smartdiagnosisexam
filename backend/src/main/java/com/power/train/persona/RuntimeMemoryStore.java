package com.power.train.persona;

import com.power.train.store.Sql;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 运行时记忆条目：由 Agent 诊断、练习判分、考试交卷实时写入 MySQL 的 memory_item 表，
 * 记忆展示板块立即可见；重启后依然存在（不再有内存态）。
 */
@Component
public class RuntimeMemoryStore {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final int MAX_KEPT = 8;

    private final Sql sql;

    public RuntimeMemoryStore(Sql sql) {
        this.sql = sql;
    }

    public void add(String username, String type, String typeLabel, String title, String detail, List<String> tags,
                    String sourceLabel, String occurredAt) {
        String at = occurredAt == null ? ZonedDateTime.now().format(STAMP) : occurredAt;
        String memoryId = "MEM-RT-" + System.currentTimeMillis() % 100000000L + "-" + Math.abs(title.hashCode() % 1000);
        sql.update("INSERT INTO memory_item (memory_id, username, type, type_label, occurred_at, title, detail, tags, "
                + "source, source_label, sort_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            memoryId, username, type, typeLabel, at, title, detail, sql.json(tags),
            "个人学习 Agent".equals(sourceLabel) ? "AGENT" : "SYSTEM", sourceLabel, 0);
        trim(username);
    }

    /** 兼容旧签名的简化写法（系统建议类记忆）。 */
    public void addAdvice(String username, String title, String detail, List<String> tags, String sourceLabel,
                          String occurredAt) {
        add(username, "ADVICE", "系统建议", title, detail, tags, sourceLabel, occurredAt);
    }

    /** 只保留最近 MAX_KEPT 条实时记忆，避免记忆展示被刷屏。 */
    private void trim(String username) {
        sql.update("DELETE FROM memory_item WHERE username = ? AND memory_id LIKE 'MEM-RT-%' AND memory_id NOT IN ("
            + "SELECT memory_id FROM (SELECT memory_id FROM memory_item WHERE username = ? AND memory_id LIKE 'MEM-RT-%' "
            + "ORDER BY created_at DESC, memory_id DESC LIMIT ?) keep)", username, username, MAX_KEPT);
    }

    public List<Map<String, Object>> list(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT memory_id, type, type_label, occurred_at, title, detail, tags, source, source_label FROM memory_item "
                + "WHERE username = ? AND memory_id LIKE 'MEM-RT-%' ORDER BY created_at DESC, memory_id DESC", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("memory_id", row.get("memory_id"));
            item.put("type", row.get("type"));
            item.put("type_label", row.get("type_label"));
            item.put("title", row.get("title"));
            item.put("detail", row.get("detail"));
            item.put("tags", sql.parse(row.get("tags")));
            item.put("occurred_at", row.get("occurred_at"));
            item.put("source", row.get("source"));
            item.put("source_label", row.get("source_label"));
            items.add(item);
        }
        return items;
    }
}
