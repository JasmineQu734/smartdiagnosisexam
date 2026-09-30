package com.power.train.store;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * MySQL 访问入口：系统里的数据只有这一个来源。
 * 把 JDBC 返回值转换成与接口一致的 JSON 类型（整数保持整数、小数保持小数、JSON 列解析回对象）。
 */
@Component
public class Sql {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    public Sql(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Map<String, Object>> rows(String sqlText, Object... args) {
        List<Map<String, Object>> raw = jdbc.queryForList(sqlText, args);
        List<Map<String, Object>> rows = new ArrayList<>(raw.size());
        for (Map<String, Object> item : raw) {
            Map<String, Object> converted = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : item.entrySet()) {
                converted.put(entry.getKey(), value(entry.getValue()));
            }
            rows.add(converted);
        }
        return rows;
    }

    public Map<String, Object> row(String sqlText, Object... args) {
        List<Map<String, Object>> rows = rows(sqlText, args);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public long count(String sqlText, Object... args) {
        Long value = jdbc.queryForObject(sqlText, Long.class, args);
        return value == null ? 0 : value;
    }

    public int update(String sqlText, Object... args) {
        return jdbc.update(sqlText, args);
    }

    /** 写库前统一转成 JSON 文本。 */
    public String json(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception error) {
            throw new IllegalStateException("JSON 序列化失败", error);
        }
    }

    /** 读库后把 JSON 列解析回对象（List / Map / 标量）。 */
    public Object parse(Object raw) {
        String text = rawJson(raw);
        if (text == null || text.isBlank()) {
            return null;
        }
        try {
            return mapper.readValue(text, Object.class);
        } catch (Exception error) {
            return null;
        }
    }

    public List<Object> parseList(Object raw) {
        Object parsed = parse(raw);
        return parsed instanceof List<?> list ? new ArrayList<>(list) : new ArrayList<>();
    }

    public List<String> parseStrings(Object raw) {
        List<String> values = new ArrayList<>();
        for (Object item : parseList(raw)) {
            values.add(String.valueOf(item));
        }
        return values;
    }

    /** JSON 列统一取文本（MySQL 驱动可能返回字符串或字节）。 */
    public String rawJson(Object raw) {
        if (raw == null) {
            return null;
        }
        return raw instanceof byte[] bytes ? new String(bytes, StandardCharsets.UTF_8) : String.valueOf(raw);
    }

    public String rawJson(Map<String, Object> row, String column) {
        return row == null ? null : rawJson(row.get(column));
    }

    private Object value(Object raw) {
        if (raw == null) {
            return null;
        }
        if (raw instanceof BigDecimal decimal) {
            BigDecimal trimmed = decimal.stripTrailingZeros();
            if (trimmed.scale() <= 0) {
                try {
                    return trimmed.intValueExact();
                } catch (ArithmeticException ignored) {
                    return trimmed.longValue();
                }
            }
            return trimmed.doubleValue();
        }
        if (raw instanceof Timestamp stamp) {
            return stamp.toLocalDateTime();
        }
        if (raw instanceof java.sql.Date date) {
            return date.toLocalDate().toString();
        }
        if (raw instanceof byte[] bytes) {
            return new String(bytes, StandardCharsets.UTF_8);
        }
        return raw;
    }

    /** TINYINT(1) 列统一转成布尔值（接口里的开关字段是 true / false，不是 1 / 0）。 */
    public boolean bool(Object raw) {
        if (raw == null) {
            return false;
        }
        if (raw instanceof Boolean value) {
            return value;
        }
        if (raw instanceof Number number) {
            return number.intValue() != 0;
        }
        String text = String.valueOf(raw).trim();
        return "1".equals(text) || "true".equalsIgnoreCase(text) || "Y".equalsIgnoreCase(text);
    }
}
