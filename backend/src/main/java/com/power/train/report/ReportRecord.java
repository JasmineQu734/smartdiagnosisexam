package com.power.train.report;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;

/**
 * 一份已提交的实操检测报告（字段与 task_report 表一一对应；member 为执行组员，reporter 为填报人）。
 *
 * sopStatus / sopDeviation 是填报时给出的结构化答案（FOLLOWED / DEVIATED / NOT_APPLICABLE + 偏差说明），
 * 字段上线前的历史报告为空串 —— 读的时候一律按「未知」处理，不替历史数据猜一个答案。
 */
public record ReportRecord(
    String reportId,
    long taskId,
    String taskTitle,
    String member,
    String reporter,
    String reporterPosition,
    String detectedAt,
    String shift,
    String location,
    String gasType,
    String gasLabel,
    String unit,
    BigDecimal value,
    BigDecimal threshold,
    String direction,
    String phenomenon,
    String measures,
    String sopStatus,
    String sopDeviation,
    String judgment,
    String severity,
    String documentText,
    Instant submittedAt,
    Map<String, Object> analysis) {

    public ReportRecord analyzed(String documentText, Map<String, Object> analysis, String severity) {
        return new ReportRecord(reportId, taskId, taskTitle, member, reporter, reporterPosition, detectedAt, shift, location,
            gasType, gasLabel, unit, value, threshold, direction, phenomenon, measures, sopStatus, sopDeviation, judgment,
            severity, documentText, submittedAt, analysis);
    }
}
