package com.power.train.store;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 展示数据集：老总 / 管理员 / 班组页面维护的只读清单（驾驶舱口径、台账、口径说明等）。
 * 单条口径存 dataset_meta，多行清单存 dataset_item；两者都以 JSON 存在 MySQL 里，可随时用 SQL 维护。
 */
@Component
public class DatasetStore {

    private final Sql sql;

    public DatasetStore(Sql sql) {
        this.sql = sql;
    }

    /** 单条口径数据（对象）。 */
    public Map<String, Object> meta(String key) {
        Object parsed = value(key);
        if (parsed instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((k, v) -> result.put(String.valueOf(k), v));
            return result;
        }
        return new LinkedHashMap<>();
    }

    /** 原始口径数据：既可能是对象（meta），也可能是清单（如个人差距、公司人才缺口）。 */
    public Object value(String key) {
        Map<String, Object> row = sql.row("SELECT payload FROM dataset_meta WHERE dataset_key = ?", key);
        return sql.parse(sql.rawJson(row, "payload"));
    }

    /** 清单型口径：payload 为数组时按数组返回，否则返回空清单。 */
    public List<Object> values(String key) {
        Object parsed = value(key);
        return parsed instanceof List<?> list ? new ArrayList<>(list) : new ArrayList<>();
    }

    /** 多行清单（每行一个对象，按 sort_no 排序）。 */
    public List<Map<String, Object>> items(String key) {
        List<Map<String, Object>> rows = sql.rows(
            "SELECT payload FROM dataset_item WHERE dataset_key = ? ORDER BY sort_no, item_key", key);
        List<Map<String, Object>> items = new ArrayList<>(rows.size());
        for (Map<String, Object> row : rows) {
            Object parsed = sql.parse(sql.rawJson(row, "payload"));
            if (parsed instanceof Map<?, ?> map) {
                Map<String, Object> item = new LinkedHashMap<>();
                map.forEach((k, v) -> item.put(String.valueOf(k), v));
                items.add(item);
            }
        }
        return items;
    }
}
