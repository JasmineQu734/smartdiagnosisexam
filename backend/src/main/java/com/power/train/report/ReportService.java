package com.power.train.report;

import com.power.train.rule.RuleResultStore;
import com.power.train.rule.RuleSuggestionService;
import com.power.train.store.Sql;
import java.io.IOException;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 实操检测报告：报告正文、归因结论与提交时间都存放在 MySQL 的 task_report 表，
 * 文档（PDF / Word）按模板框格即时渲染，不保留内存态。
 */
@Service
public class ReportService {

    private static final Logger log = LoggerFactory.getLogger(ReportService.class);
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final Sql sql;
    private final ReportDocumentService documents;
    private final ReportAnalysisService analyzer;
    private final RuleResultStore results;
    private final RuleSuggestionService suggestions;

    public ReportService(Sql sql, ReportDocumentService documents, ReportAnalysisService analyzer,
                         RuleResultStore results, RuleSuggestionService suggestions) {
        this.sql = sql;
        this.documents = documents;
        this.analyzer = analyzer;
        this.results = results;
        this.suggestions = suggestions;
    }

    /** 提交报告：校验通过后立即生成文档正文并执行 AI 归因分析，结果写入 MySQL。 */
    public ReportRecord submit(long taskId, String taskTitle, ReportForm form, String reporter, String reporterPosition) {
        ReportTemplate.GasRule gas = ReportTemplate.gasRule(form.gasType());
        if (gas == null) {
            throw new IllegalArgumentException("未知气体类型：" + form.gasType());
        }
        boolean abnormal = ReportTemplate.abnormal(gas.direction(), form.gasValue(), form.threshold());
        // 执行组员：班组长代组员填报时填组员姓名；留空则默认本次执行人就是填报人本人
        String member = form.member() == null || form.member().isBlank() ? reporter : form.member().strip();
        // SOP 执行情况：表单已校验为 FOLLOWED / DEVIATED / NOT_APPLICABLE，这里只做去空格与空值兜底
        String sopStatus = form.sopStatus() == null ? "" : form.sopStatus().strip();
        String sopDeviation = "DEVIATED".equals(sopStatus) && form.sopDeviation() != null
            ? form.sopDeviation().strip() : "";
        ReportRecord draft = new ReportRecord(nextId(), taskId, taskTitle, member, reporter, reporterPosition,
            form.detectedAt(), form.shift(), form.location(), gas.code(), gas.label(), gas.unit(),
            form.gasValue(), form.threshold(), gas.direction(),
            form.phenomenon().strip(), form.measures() == null ? "" : form.measures().strip(),
            sopStatus, sopDeviation,
            abnormal ? "超限" : "正常", abnormal ? "高" : "低", null, Instant.now(), null);
        return analyzeAndStore(draft, null, reporter);
    }

    /**
     * 重新执行归因分析（切换归因来源后可复算），结论覆盖写回同一条报告。
     *
     * @param source rule / model，留空按配置自动选（Controller 与前端路径不变，只是多一个可选参数）
     */
    public ReportRecord analyze(String reportId, String source, String user) {
        ReportRecord report = byId(reportId);
        if (report == null) {
            return null;
        }
        return analyzeAndStore(report, source, user);
    }

    /**
     * 归因结论落到报告上的唯一出口：先算结论，再发布待人工确认的建议，最后写回 task_report。
     * 一次归因 = 一个 run_id：规则执行留痕（rule_result）与待确认建议（agent_suggestion）共用这个编号，
     * 人工确认后再写 decision_log，整条链在库里能一路查回来。
     */
    private ReportRecord analyzeAndStore(ReportRecord draft, String source, String user) {
        ReportRecord report = refreshGasRule(draft);
        // 归因只看报告本体正文：把上一轮结论排除在外（见 ReportDocumentService.extractSourceText）
        String documentText = documents.extractSourceText(report);
        String runId = results.nextRunId();
        Map<String, Object> raw = analyzer.analyze(report, documentText, source, user, runId);

        Map<String, Object> analysis = new LinkedHashMap<>(raw);
        String origin = "model".equals(String.valueOf(raw.get("source"))) ? "model" : "rule";
        analysis.put("source_label", "model".equals(origin)
            ? "AI 大模型（" + raw.get("model") + "）" : ReportAttributionService.MODEL_LABEL);

        Object runIdUsed = analysis.get("run_id") == null ? runId : analysis.get("run_id");
        String suggestionId = suggestions.publish(String.valueOf(runIdUsed), ReportAttributionService.AGENT_TYPE,
            report.reportId(), suggestionInput(report, analysis), analysis, decimal(analysis.get("confidence")), origin);
        analysis.put("suggestion_id", suggestionId);

        Object severityRaw = analysis.get("severity");
        String severity = severityRaw != null ? String.valueOf(severityRaw) : report.severity();
        ReportRecord stored = report.analyzed(documentText, analysis, severity);
        save(stored);
        return stored;
    }

    /** 建议入参快照：人工确认时看得懂的最小集合（完整事实在 rule_result.input_json 里）。 */
    private static Map<String, Object> suggestionInput(ReportRecord report, Map<String, Object> analysis) {
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("report_id", report.reportId());
        input.put("task_id", report.taskId());
        input.put("gas_type", report.gasType());
        input.put("value", report.value());
        input.put("threshold", report.threshold());
        input.put("direction", report.direction());
        input.put("source", analysis.get("source"));
        input.put("run_id", analysis.get("run_id"));
        return input;
    }

    /** 复核前按当前模板刷新气体标签、单位与报警方向，避免报告长期保留模板旧值（含历史乱码值）。 */
    private static ReportRecord refreshGasRule(ReportRecord report) {
        ReportTemplate.GasRule gas = ReportTemplate.gasRule(report.gasType());
        if (gas == null) {
            return report;
        }
        return new ReportRecord(report.reportId(), report.taskId(), report.taskTitle(), report.member(), report.reporter(),
            report.reporterPosition(), report.detectedAt(), report.shift(), report.location(), gas.code(), gas.label(),
            gas.unit(), report.value(), report.threshold(), gas.direction(), report.phenomenon(), report.measures(),
            report.sopStatus(), report.sopDeviation(), report.judgment(), report.severity(), report.documentText(),
            report.submittedAt(), report.analysis());
    }

    public List<ReportRecord> list() {
        List<ReportRecord> reports = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT * FROM task_report ORDER BY submitted_at DESC")) {
            reports.add(toRecord(row));
        }
        reports.sort(Comparator.comparing(ReportRecord::submittedAt).reversed());
        return reports;
    }

    public ReportRecord byId(String reportId) {
        Map<String, Object> row = sql.row("SELECT * FROM task_report WHERE report_id = ?", reportId);
        return row == null ? null : toRecord(row);
    }

    /** 取报告文档字节：按框格即时渲染（PDF / Word 共用同一份库内数据）。 */
    public byte[] document(String reportId, boolean word) throws IOException {
        ReportRecord report = byId(reportId);
        if (report == null) {
            throw new IOException("报告不存在：" + reportId);
        }
        return document(report, word);
    }

    /** 与上同，但直接复用已查到的报告，下载时不再重复查库。 */
    public byte[] document(ReportRecord report, boolean word) throws IOException {
        return word ? documents.renderDocx(report) : documents.renderPdf(report);
    }

    /** 每个任务最近一份报告，用于任务列表展示填报状态。 */
    public Map<Long, ReportRecord> latestByTask() {
        Map<Long, ReportRecord> latest = new LinkedHashMap<>();
        list().forEach(report -> latest.putIfAbsent(report.taskId(), report));
        return latest;
    }

    private void save(ReportRecord report) {
        sql.update("INSERT INTO task_report (report_id, task_id, task_title, member, reporter, reporter_position, detected_at, "
                + "shift, location, gas_type, gas_label, unit, gas_value, threshold_value, direction, judgment, severity, "
                + "phenomenon, measures, sop_status, sop_deviation, document_text, analysis, submitted_at) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                + "ON DUPLICATE KEY UPDATE task_id = VALUES(task_id), task_title = VALUES(task_title), "
                + "member = VALUES(member), reporter = VALUES(reporter), reporter_position = VALUES(reporter_position), "
                + "severity = VALUES(severity), "
                + "gas_label = VALUES(gas_label), unit = VALUES(unit), direction = VALUES(direction), "
                + "judgment = VALUES(judgment), sop_status = VALUES(sop_status), sop_deviation = VALUES(sop_deviation), "
                + "document_text = VALUES(document_text), analysis = VALUES(analysis)",
            report.reportId(), report.taskId(), report.taskTitle(), report.member(), report.reporter(), report.reporterPosition(),
            report.detectedAt(), report.shift(), report.location(), report.gasType(), report.gasLabel(), report.unit(),
            report.value(), report.threshold(), report.direction(), report.judgment(), report.severity(),
            report.phenomenon(), report.measures(), report.sopStatus(), report.sopDeviation(),
            report.documentText(), sql.json(report.analysis()),
            LocalDateTime.ofInstant(report.submittedAt(), ZoneId.systemDefault()).format(STAMP));
    }

    private ReportRecord toRecord(Map<String, Object> row) {
        Map<String, Object> analysis = null;
        Object parsed = sql.parse(row.get("analysis"));
        if (parsed instanceof Map<?, ?> map) {
            Map<String, Object> collected = new LinkedHashMap<>();
            map.forEach((key, value) -> collected.put(String.valueOf(key), value));
            analysis = collected;
        }
        Instant submittedAt = Instant.now();
        if (row.get("submitted_at") instanceof LocalDateTime local) {
            submittedAt = local.atZone(ZoneId.systemDefault()).toInstant();
        }
        return new ReportRecord(
            String.valueOf(row.get("report_id")),
            ((Number) row.get("task_id")).longValue(),
            String.valueOf(row.get("task_title")),
            memberOf(row),
            String.valueOf(row.get("reporter")),
            String.valueOf(row.get("reporter_position")),
            String.valueOf(row.get("detected_at")),
            String.valueOf(row.get("shift")),
            String.valueOf(row.get("location")),
            String.valueOf(row.get("gas_type")),
            String.valueOf(row.get("gas_label")),
            String.valueOf(row.get("unit")),
            decimal(row.get("gas_value")),
            decimal(row.get("threshold_value")),
            String.valueOf(row.get("direction")),
            String.valueOf(row.get("phenomenon")),
            row.get("measures") == null ? "" : String.valueOf(row.get("measures")),
            text(row, "sop_status"), text(row, "sop_deviation"),
            String.valueOf(row.get("judgment")),
            String.valueOf(row.get("severity")),
            row.get("document_text") == null ? null : String.valueOf(row.get("document_text")),
            submittedAt,
            analysis);
    }

    /** 读可能为空的文本列：空串与 NULL 都当「没填」，不把 null 变成字符串 "null"。 */
    private static String text(Map<String, Object> row, String column) {
        Object value = row.get(column);
        return value == null ? "" : String.valueOf(value);
    }

    /** 执行组员：报告未单独记录组员（历史数据）时回退为填报人，避免台账出现空白。 */
    private static String memberOf(Map<String, Object> row) {
        Object value = row.get("member");
        String member = value == null ? "" : String.valueOf(value).strip();
        if (member.isEmpty() || "null".equals(member)) {
            Object reporter = row.get("reporter");
            return reporter == null ? "" : String.valueOf(reporter);
        }
        return member;
    }

    private static BigDecimal decimal(Object value) {
        return value == null ? null : new BigDecimal(String.valueOf(value));
    }

    private String nextId() {
        String day = LocalDate.now(ZoneId.systemDefault()).format(DAY);
        int sequence = (int) sql.count("SELECT COUNT(*) FROM task_report WHERE report_id LIKE ?", "RPT-" + day + "-%") + 1;
        String id = "RPT-" + day + "-" + String.format("%04d", sequence);
        while (sql.count("SELECT COUNT(*) FROM task_report WHERE report_id = ?", id) > 0) {
            sequence++;
            id = "RPT-" + day + "-" + String.format("%04d", sequence);
        }
        log.debug("new report id {}", id);
        return id;
    }
}
