package com.power.train.admin;

import com.power.train.store.Sql;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 标准依据库：条目取自 MySQL 的 standard_ref，来源说明取自 standard_source。
 * 标准号、名称、状态、发布/实施日期与详情页链接由抓取脚本写入库中，页面直接读库，点开官网即可核对。
 */
@Component
class StandardSource {

    private final Sql sql;

    StandardSource(Sql sql) {
        this.sql = sql;
    }

    private Map<String, Object> origin() {
        Map<String, Object> row = sql.row(
            "SELECT source, source_url, fetched_at, note FROM standard_source ORDER BY id LIMIT 1");
        return row == null ? new LinkedHashMap<>() : row;
    }

    String source() {
        return String.valueOf(origin().getOrDefault("source", "国家标准全文公开系统"));
    }

    String sourceUrl() {
        return String.valueOf(origin().getOrDefault("source_url", "https://openstd.samr.gov.cn/bzgk/gb/std_list"));
    }

    String fetchedAt() {
        return String.valueOf(origin().getOrDefault("fetched_at", "—"));
    }

    String note() {
        return String.valueOf(origin().getOrDefault("note", ""));
    }

    /** 全部标准条目（官网原始字段）。 */
    List<Map<String, Object>> all() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT std_no, name, status, published, implemented, detail_url, "
            + "page_standard, http_code, date_note FROM standard_ref ORDER BY sort_no, std_no")) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("standard", row.get("std_no"));
            item.put("name", row.get("name"));
            item.put("status", row.get("status"));
            item.put("published", row.get("published"));
            item.put("implemented", row.get("implemented"));
            item.put("url", row.get("detail_url"));
            item.put("page_standard", row.get("page_standard"));
            item.put("http", row.get("http_code"));
            item.put("date_note", row.get("date_note"));
            item.put("source", source());
            item.put("fetched_at", fetchedAt());
            items.add(item);
        }
        return items;
    }

    /** 现行标准条数。 */
    long current() {
        return sql.count("SELECT COUNT(*) FROM standard_ref WHERE status = '现行'");
    }

    /** 单条标准的依据摘要，供岗位技能要求等页面引用；找不到时返回空表而不是编造内容。 */
    Map<String, Object> basis(String standard) {
        Map<String, Object> row = sql.row(
            "SELECT std_no, name, status, implemented, detail_url FROM standard_ref WHERE std_no = ?", standard);
        if (row == null) {
            return new LinkedHashMap<>();
        }
        Map<String, Object> basis = new LinkedHashMap<>();
        basis.put("standard", row.get("std_no"));
        basis.put("name", row.get("name"));
        basis.put("status", row.get("status"));
        basis.put("implemented", row.get("implemented"));
        basis.put("url", row.get("detail_url"));
        return basis;
    }
}
