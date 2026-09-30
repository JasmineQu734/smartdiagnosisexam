package com.power.train.report;

import com.power.train.store.Sql;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 报告模板：规定框格定义 + 气体检测规则目录，同时驱动前端表单、后端判定与文档渲染。
 * 内容存放在 MySQL（report_document_meta / report_template_section / report_template_field / gas_rule），
 * 启动时由 ReportTemplateLoader 装载，管理员改库即改模板与阈值。
 */
public final class ReportTemplate {

    /** 单个气体的检测规则：单位、标准阈值、报警方向、运维归因与处置措施。 */
    public record GasRule(String code, String label, String unit, BigDecimal threshold, String direction,
                          String standard, String attribution, List<String> actions) {}

    /** 文档框格：一节标题 + 若干行（label=null 表示整行通栏）。 */
    public record DocSection(String title, List<Row> rows) {}

    public record Row(String label, String value) {}

    private ReportTemplate() {
    }

    public static volatile String DOCUMENT_TITLE = "实操任务检测报告";
    public static volatile String NOTICE = "";
    public static volatile List<String> SIGN_BOXES = List.of();
    public static volatile List<Map<String, Object>> SECTIONS = List.of();
    private static volatile Map<String, GasRule> gasRules = new LinkedHashMap<>();
    private static volatile List<Map<String, Object>> gasRuleViews = List.of();

    public static GasRule gasRule(String code) {
        return gasRules.get(code);
    }

    public static Map<String, GasRule> gasRules() {
        return gasRules;
    }

    /** 按报警方向判断是否超限：HIGH=高于阈值报警，LOW=低于阈值报警。 */
    public static boolean abnormal(String direction, BigDecimal value, BigDecimal threshold) {
        if (value == null || threshold == null) {
            return false;
        }
        return "LOW".equals(direction) ? value.compareTo(threshold) < 0 : value.compareTo(threshold) > 0;
    }

    /** 前端表单与框格说明使用的模板定义。 */
    public static Map<String, Object> formTemplate() {
        Map<String, Object> template = new LinkedHashMap<>();
        template.put("document_title", DOCUMENT_TITLE);
        template.put("notice", NOTICE);
        template.put("sign_boxes", SIGN_BOXES);
        template.put("gas_rules", gasRuleViews);
        template.put("sections", SECTIONS);
        return template;
    }

    /** 从 MySQL 装载模板与气体规则（由 ReportTemplateLoader 在启动时调用）。 */
    public static synchronized void load(Sql sql) {
        Map<String, Object> meta = sql.row("SELECT document_title, notice, sign_boxes FROM report_document_meta WHERE id = 1");
        if (meta != null) {
            DOCUMENT_TITLE = String.valueOf(meta.get("document_title"));
            NOTICE = String.valueOf(meta.get("notice"));
            List<String> boxes = new ArrayList<>();
            for (Object item : sql.parseList(meta.get("sign_boxes"))) {
                boxes.add(String.valueOf(item));
            }
            SIGN_BOXES = boxes;
        }

        Map<String, GasRule> rules = new LinkedHashMap<>();
        List<Map<String, Object>> views = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT code, label, unit, threshold_value, direction, standard, attribution, actions FROM gas_rule "
                + "ORDER BY sort_no")) {
            List<String> actions = new ArrayList<>();
            for (Object item : sql.parseList(row.get("actions"))) {
                actions.add(String.valueOf(item));
            }
            GasRule rule = new GasRule(
                String.valueOf(row.get("code")),
                String.valueOf(row.get("label")),
                String.valueOf(row.get("unit")),
                new BigDecimal(String.valueOf(row.get("threshold_value"))),
                String.valueOf(row.get("direction")),
                String.valueOf(row.get("standard")),
                String.valueOf(row.get("attribution")),
                actions);
            rules.put(rule.code(), rule);
            Map<String, Object> view = new LinkedHashMap<>();
            view.put("code", rule.code());
            view.put("label", rule.label());
            view.put("unit", rule.unit());
            view.put("threshold", row.get("threshold_value"));
            view.put("direction", rule.direction());
            view.put("direction_label", "LOW".equals(rule.direction()) ? "低于阈值报警" : "高于阈值报警");
            view.put("standard", rule.standard());
            view.put("attribution", rule.attribution());
            view.put("actions", rule.actions());
            views.add(view);
        }
        gasRules = rules;
        gasRuleViews = views;

        List<Map<String, Object>> sections = new ArrayList<>();
        for (Map<String, Object> section : sql.rows(
            "SELECT section_key, title FROM report_template_section ORDER BY sort_no")) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("key", section.get("section_key"));
            item.put("title", section.get("title"));
            List<Map<String, Object>> fields = new ArrayList<>();
            for (Map<String, Object> field : sql.rows(
                "SELECT name, label, field_type, required, example, hint FROM report_template_field "
                    + "WHERE section_key = ? ORDER BY sort_no", section.get("section_key"))) {
                Map<String, Object> view = new LinkedHashMap<>();
                view.put("name", field.get("name"));
                view.put("label", field.get("label"));
                view.put("type", field.get("field_type"));
                view.put("required", sql.bool(field.get("required")));
                view.put("example", field.get("example"));
                view.put("hint", field.get("hint"));
                fields.add(view);
            }
            item.put("fields", fields);
            sections.add(item);
        }
        SECTIONS = sections;
    }
}

/** 启动时把模板数据装进 ReportTemplate，保证渲染与表单共用同一份 MySQL 数据。 */
@Component
class ReportTemplateLoader {
    ReportTemplateLoader(Sql sql) {
        ReportTemplate.load(sql);
    }
}
