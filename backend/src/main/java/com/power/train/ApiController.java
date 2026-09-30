package com.power.train;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.exam.ExamCenter;
import com.power.train.rbac.AuthToken;
import com.power.train.report.ReportAttributionService;
import com.power.train.report.ReportForm;
import com.power.train.report.ReportRecord;
import com.power.train.report.ReportService;
import com.power.train.report.ReportTemplate;
import com.power.train.rule.RuleSuggestionService;
import com.power.train.store.DatasetStore;
import com.power.train.store.PersonalStore;
import com.power.train.store.Sql;
import com.power.train.support.Users;
import jakarta.validation.Valid;
import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

/**
 * 员工与通用接口：数据全部来自 MySQL —— 身份与档案读 app_user / employee_skill，
 * 展示口径读 dataset_meta / dataset_item，考试读 exam 系列表，报告读 task_report。
 */
@RestController
@RequestMapping("/api/v1")
public class ApiController {

    private final ReportService reportService;
    private final ExamCenter examCenter;
    private final PersonalStore personal;
    private final DatasetStore datasets;
    private final RuleSuggestionService suggestions;
    private final AuthToken authTokens;
    private final Sql sql;

    public ApiController(ReportService reportService, ExamCenter examCenter, PersonalStore personal,
                         DatasetStore datasets, RuleSuggestionService suggestions, AuthToken authTokens, Sql sql) {
        this.reportService = reportService;
        this.examCenter = examCenter;
        this.personal = personal;
        this.datasets = datasets;
        this.suggestions = suggestions;
        this.authTokens = authTokens;
        this.sql = sql;
    }

    /** 检索条件都是可选的：没传就按空串处理，避免把 null 带进打分与筛选逻辑。 */
    private static String filter(String value) {
        return value == null ? "" : value.trim();
    }

    /**
     * 登录：账号存在才签发令牌，令牌里带账号与角色（服务端签发，客户端改不动）。
     * 账号不存在返回 401 —— 不再静默回落到演示账号，否则随便填个名字就能拿到别人的身份。
     */
    @PostMapping("/auth/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody(required = false) Map<String, String> body) {
        String username = body == null ? Users.DEFAULT : Users.account(body.get("username"));
        Map<String, Object> user = personal.findIdentity(username);
        if (user == null) {
            Map<String, Object> denied = new LinkedHashMap<>();
            denied.put("code", 401);
            denied.put("message", "账号不存在：" + username);
            denied.put("data", Map.of());
            denied.put("trace_id", UUID.randomUUID().toString());
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(denied);
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("token", authTokens.issue(String.valueOf(user.get("username")), String.valueOf(user.get("role"))));
        data.put("token_type", "Bearer");
        data.put("user", user);
        return ResponseEntity.ok(ok(data));
    }

    @PostMapping("/auth/logout")
    public Map<String, Object> logout() { return ok(Map.of("logged_out", true)); }

    @GetMapping("/auth/me")
    public Map<String, Object> me(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.identity(Users.account(user)));
    }

    @GetMapping("/personal/profile")
    public Map<String, Object> profile(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.profile(Users.account(user)));
    }

    /** 技能雷达：当前等级 vs 岗位要求 vs 公司未来需求与证据（employee_skill）。 */
    @GetMapping("/personal/skill-radar")
    public Map<String, Object> skillRadar(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.skillRadar(Users.account(user)));
    }

    @GetMapping("/personal/gaps")
    public Map<String, Object> gaps() { return ok(datasets.value("personal.gaps")); }

    @GetMapping("/personal/tasks")
    public Map<String, Object> tasks(@RequestHeader(value = "X-User", required = false) String user) {
        List<Map<String, Object>> rows = personal.tasks(Users.account(user));
        Map<Long, ReportRecord> latest = reportService.latestByTask();
        for (Map<String, Object> task : rows) {
            ReportRecord report = latest.get(((Number) task.get("id")).longValue());
            task.put("report_id", report == null ? null : report.reportId());
            task.put("report_status", report == null ? "NONE" : "SUBMITTED");
            task.put("judgment", report == null ? null : report.judgment());
            task.put("severity", report == null ? null : report.severity());
            task.put("analyzed", report != null && report.analysis() != null);
        }
        return ok(rows);
    }

    // ---- 学习总版：概览、计划、记录、资源（learning_summary / learning_plan / learning_record / resource_item） ----

    @GetMapping("/personal/learning-summary")
    public Map<String, Object> learningSummary(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.learningSummary(Users.account(user)));
    }

    @GetMapping("/personal/learning-plan")
    public Map<String, Object> learningPlan(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.learningPlan(Users.account(user)));
    }

    @GetMapping("/personal/learning-records")
    public Map<String, Object> learningRecords(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.learningRecords(Users.account(user)));
    }

    @GetMapping("/personal/resources")
    public Map<String, Object> resources() {
        return ok(personal.resources());
    }

    /**
     * 外网课程搜索：按关键词在外网课程库（external_course）里打分检索，返回站内命中的资料、
     * 各公开课程平台的实时检索直达链接（新窗口打开）与按当前技能缺口排出的热门检索词。
     */
    @GetMapping("/personal/course-search")
    public Map<String, Object> courseSearch(@RequestHeader(value = "X-User", required = false) String user,
                                            @RequestParam(value = "q", required = false) String keyword,
                                            @RequestParam(value = "platform", required = false) String platform,
                                            @RequestParam(value = "skill", required = false) String skill,
                                            @RequestParam(value = "level", required = false) String level) {
        return ok(personal.searchExternalCourses(Users.account(user), filter(keyword), filter(platform), filter(skill), filter(level)));
    }

    // ---- 考试中心：考试列表取自与管理员共用的 ExamCenter；只有管理员统一开考后员工才能进入答题 ----

    /**
     * 员工视角的一场考试：既有历史成绩（考试记忆）也要反映「管理员是否已统一开考」。
     * status 只表达学习侧结果（PENDING / IN_PROGRESS / PASSED / FAILED）；
     * 能否进入答题由 can_enter 决定，前端按钮以 can_enter 为准，避免出现「可点但进不去」的假按钮。
     */
    private Map<String, Object> examView(Map<String, Object> exam, Map<String, Object> mine) {
        Map<String, Object> view = new LinkedHashMap<>(exam);
        boolean open = "进行中".equals(exam.get("status"));
        boolean everAttempted = mine != null;
        boolean submittedThisRound = everAttempted && "SUBMITTED".equals(mine.get("status"));
        boolean enteredThisRound = everAttempted && "IN_PROGRESS".equals(mine.get("status"));
        String lastResult = everAttempted ? String.valueOf(mine.get("result")) : null;
        Object score = everAttempted ? mine.get("score") : null;
        int passScore = ((Number) exam.get("pass_score")).intValue();
        boolean canEnter = open && !submittedThisRound;
        view.put("open", open);
        view.put("can_enter", canEnter);
        view.put("round_submitted", submittedThisRound);
        view.put("status", submittedThisRound || (!open && everAttempted)
            ? lastResult
            : (open && (canEnter || enteredThisRound) ? "IN_PROGRESS" : "PENDING"));
        view.put("score", score);
        view.put("occurred_at", everAttempted ? mine.getOrDefault("submitted_at", "—") : null);
        view.put("attempts", everAttempted ? 1 : 0);
        view.put("gate_status", !open ? "NOT_OPEN" : (submittedThisRound ? "SUBMITTED" : "IN_PROGRESS"));
        view.put("gate_note", !open
            ? "等待管理员统一开考"
            : (submittedThisRound ? "本场已交卷，等待下一场开考" : "已开考，可进入答题"));
        if (!open) {
            view.put("status_note", everAttempted
                ? "上次成绩 " + score + " 分（合格线 " + passScore + " 分），管理员再次开考后可补考"
                : "管理员尚未开始本场考试，开考后可进入答题");
        } else if (submittedThisRound) {
            view.put("status_note", "本场已交卷：" + score + " 分（合格线 " + passScore + " 分）");
        } else {
            view.put("status_note", "管理员已开考，可进入答题；交卷后立即出分并给出错题解析");
        }
        return view;
    }

    @GetMapping("/personal/exams")
    public Map<String, Object> exams(@RequestHeader(value = "X-User", required = false) String user) {
        String me = Users.account(user);
        List<Map<String, Object>> mine = examCenter.recordsFor(me);
        List<Map<String, Object>> items = examCenter.list().stream().map(exam -> {
            Map<String, Object> record = mine.stream()
                .filter(item -> String.valueOf(item.get("exam_id")).equals(String.valueOf(exam.get("exam_id"))))
                .findFirst().orElse(null);
            return examView(exam, record);
        }).toList();
        long open = items.stream().filter(item -> Boolean.TRUE.equals(item.get("open"))).count();
        return ok(row(
            "summary", row("total", items.size(), "open", open,
                "note", open > 0
                    ? "有 " + open + " 场考试由管理员统一开考中，可进入答题；交卷后立即出分并给出错题解析。"
                    : "当前没有开考的考试，请等待管理员在考试配置中统一开考。"),
            "items", items));
    }

    @GetMapping("/personal/certificates")
    public Map<String, Object> certificates(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.certificates(Users.account(user)));
    }

    /** 员工进入考试：未由管理员开考则拒绝发卷（gate=NOT_OPEN）。 */
    @PostMapping("/exams/{examId}/start")
    public Map<String, Object> startExam(@PathVariable String examId,
                                         @RequestHeader(value = "X-User", required = false) String user) {
        return ok(examCenter.enter(examId, Users.account(user)));
    }

    /** 员工交卷：系统判分，返回成绩与逐题解析，并写入考试记忆。 */
    @PostMapping("/exams/{examId}/submit")
    public Map<String, Object> submitExam(@PathVariable String examId,
                                          @RequestBody(required = false) Map<String, Object> body,
                                          @RequestHeader(value = "X-User", required = false) String user) {
        Map<String, String> answers = new LinkedHashMap<>();
        Object raw = body == null ? null : body.get("answers");
        if (raw instanceof Map<?, ?> map) {
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                answers.put(String.valueOf(entry.getKey()), entry.getValue() == null ? "" : String.valueOf(entry.getValue()));
            }
        }
        return ok(examCenter.submit(examId, Users.account(user), answers));
    }

    // ---- 实操任务报告：模板框格、填报提交、文档生成、AI 归因 ----

    @GetMapping("/tasks/{taskId}/report-template")
    public Map<String, Object> reportTemplate(@PathVariable long taskId) {
        Map<String, Object> template = new LinkedHashMap<>(ReportTemplate.formTemplate());
        template.put("task_id", taskId);
        template.put("task_title", personal.taskTitle(taskId));
        return ok(template);
    }

    @PostMapping("/tasks/{taskId}/submit-report")
    public Map<String, Object> submitReport(@PathVariable long taskId, @RequestBody @Valid ReportForm form,
                                            @RequestHeader(value = "X-User", required = false) String user) {
        // 检测报告只由班组长填报（/tasks/** 已由 RoleInterceptor 限定为 TEAM_LEAD）；
        // 填报人与岗位取当前登录账号在 app_user 里的档案，不再写死具体姓名
        String me = Users.account(user);
        ReportRecord report = reportService.submit(taskId, personal.taskTitle(taskId), form,
            personal.displayName(me), personal.positionOf(me));
        return ok(reportView(report));
    }

    @GetMapping("/reports")
    public Map<String, Object> reports() {
        return ok(reportService.list().stream().map(this::reportView).toList());
    }

    @GetMapping("/reports/{reportId}")
    public Map<String, Object> reportDetail(@PathVariable String reportId) {
        ReportRecord report = reportService.byId(reportId);
        if (report == null) return notFound("报告不存在或已被清理");
        return ok(reportView(report));
    }

    /**
     * 重新执行归因分析。source 是可选参数（rule / model），不传按配置自动选；
     * 路径、请求体与返回结构都没变，前端与老调用方不用改。
     */
    @PostMapping("/reports/{reportId}/analyze")
    public Map<String, Object> analyzeReport(@PathVariable String reportId,
                                             @RequestParam(value = "source", required = false) String source,
                                             @RequestHeader(value = "X-User", required = false) String user) {
        ReportRecord report = reportService.analyze(reportId, source, Users.account(user));
        if (report == null) return notFound("报告不存在或已被清理");
        return ok(reportView(report));
    }

    /**
     * 人工确认归因结论：建议状态流转（采纳 / 驳回 / 修改）并写 decision_log —— 「谁在什么时候确认了什么」从此有据可查。
     *
     * 归因结论只在这里被人工处理；规则引擎与建议都不直接改业务数据，报告本身仍是唯一的业务记录。
     * 驳回与修改必须给理由：没有理由的驳回，过一阵没人知道当时为什么否掉。
     */
    @PostMapping("/tasks/reports/{reportId}/attribution/confirm")
    public Map<String, Object> confirmAttribution(@PathVariable String reportId,
                                                  @RequestBody(required = false) Map<String, Object> body,
                                                  @RequestHeader(value = "X-User", required = false) String user) {
        Object rawDecision = body == null ? null : body.get("decision");
        String decision = rawDecision == null ? "" : String.valueOf(rawDecision).trim();
        if (decision.isEmpty()) {
            Map<String, List<String>> fieldErrors = new LinkedHashMap<>();
            fieldErrors.put("decision", List.of("decision 必填：accept（采纳）/ reject（驳回）/ modify（修改后采纳）"));
            return row("code", 40001, "message", "人工确认参数校验未通过",
                "data", row("field_errors", fieldErrors), "trace_id", UUID.randomUUID().toString());
        }
        Object rawReason = body.get("reason");
        Map<String, Object> decided = suggestions.confirm(ReportAttributionService.AGENT_TYPE, reportId, decision,
            rawReason == null ? null : String.valueOf(rawReason), Users.account(user));
        if (decided == null) return notFound("该报告没有待确认的归因结论，请先执行归因分析");
        return ok(decided);
    }

    /** 下载按模板框格生成的报告文档（PDF / Word）。 */
    @GetMapping("/reports/{reportId}/document")
    public ResponseEntity<?> reportDocument(@PathVariable String reportId,
                                           @RequestParam(defaultValue = "pdf") String format) throws IOException {
        ReportRecord report = reportService.byId(reportId);
        if (report == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).contentType(MediaType.APPLICATION_JSON)
                .body(notFound("报告不存在或已归档，请回到报告列表重新生成文档"));
        }
        boolean word = "docx".equalsIgnoreCase(format) || "word".equalsIgnoreCase(format);
        byte[] bytes = reportService.document(report, word);
        String fileName = reportId + (word ? ".docx" : ".pdf");
        String encoded = URLEncoder.encode(fileName, StandardCharsets.UTF_8).replace("+", "%20");
        MediaType type = word
            ? MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            : MediaType.APPLICATION_PDF;
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=" + encoded + "; filename*=UTF-8''" + encoded)
            .contentType(type)
            .body(bytes);
    }

    private Map<String, Object> reportView(ReportRecord report) {
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("report_id", report.reportId());
        view.put("task_id", report.taskId());
        view.put("task_title", report.taskTitle());
        view.put("member", report.member());
        view.put("reporter", report.reporter());
        view.put("reporter_position", report.reporterPosition());
        view.put("detected_at", report.detectedAt());
        view.put("shift", report.shift());
        view.put("location", report.location());
        view.put("gas_type", report.gasType());
        view.put("gas_label", report.gasLabel());
        view.put("unit", report.unit());
        view.put("gas_value", report.value());
        view.put("threshold", report.threshold());
        view.put("direction", report.direction());
        view.put("judgment", report.judgment());
        view.put("severity", report.severity());
        view.put("phenomenon", report.phenomenon());
        view.put("measures", report.measures());
        view.put("sop_status", report.sopStatus());
        view.put("sop_deviation", report.sopDeviation());
        view.put("submitted_at", report.submittedAt().toString());
        view.put("analysis", report.analysis());
        view.put("document_text", report.documentText());
        view.put("document_pdf", "/api/v1/reports/" + report.reportId() + "/document?format=pdf");
        view.put("document_docx", "/api/v1/reports/" + report.reportId() + "/document?format=docx");
        return view;
    }

    private Map<String, Object> notFound(String message) {
        return row("code", 40004, "message", message, "data", null, "trace_id", UUID.randomUUID().toString());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Map<String, Object> onInvalidForm(MethodArgumentNotValidException error) {
        Map<String, Object> fields = new LinkedHashMap<>();
        for (FieldError fieldError : error.getBindingResult().getFieldErrors()) {
            fields.putIfAbsent(wireName(fieldError.getField()), fieldError.getDefaultMessage());
        }
        return row("code", 40001, "message", "表单校验未通过，请按示例格式修改后重新提交",
            "data", Map.of("field_errors", fields), "trace_id", UUID.randomUUID().toString());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public Map<String, Object> onIllegalArgument(IllegalArgumentException error) {
        return row("code", 40003, "message", error.getMessage() == null ? "请求参数不合法" : error.getMessage(),
            "data", null, "trace_id", UUID.randomUUID().toString());
    }

    private static String wireName(String field) {
        if ("phenomenonHasNumber".equals(field)) return "phenomenon";
        // 「未按 SOP 执行」必须填偏差说明，这条校验的错误要落在偏差输入框上，不是新开一个字段
        if ("sopDeviationPresent".equals(field)) return "sop_deviation";
        return field.replaceAll("([a-z0-9])([A-Z])", "$1_$2").toLowerCase();
    }

    // ---- 管理层看板与 Agent 建议（口径数据读库，建议结果写入 agent_suggestion） ----

    @GetMapping("/management/dashboard")
    public Map<String, Object> dashboard() { return ok(datasets.meta("management.dashboard")); }

    @GetMapping("/management/talent-gap")
    public Map<String, Object> talentGap() { return ok(datasets.value("management.talent-gap")); }

    /**
     * 通用 Agent 建议接口：结果按 agent_type / target_id 存入 agent_suggestion，
     * 人工确认结果可继续写 decision_log，Agent 不直接改业务数据。
     */
    @PostMapping("/agent/{agentType}/{action}")
    public ResponseEntity<Map<String, Object>> agent(@PathVariable String agentType, @PathVariable String action,
                                                     @RequestBody(required = false) Map<String, Object> request) {
        String type = agentType + "/" + action;
        String suggestionId = UUID.randomUUID().toString();
        Object targetId = request == null ? null : request.get("target_id");
        List<String> suggestions = List.of("补充《软压板逻辑》课程", "安排师傅带教 2 次", "安排一次模拟考试");
        String createdAt = Instant.now().toString();
        sql.update("INSERT INTO agent_suggestion (suggestion_id, agent_type, target_id, input_json, output_json, "
                + "confidence, source, need_human_confirm, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            suggestionId, type, targetId == null ? null : String.valueOf(targetId),
            request == null ? null : sql.json(request), sql.json(suggestions),
            new java.math.BigDecimal("0.86"), "rule", 1, "PENDING");
        Map<String, Object> suggestion = new LinkedHashMap<>();
        suggestion.put("suggestion_id", suggestionId);
        suggestion.put("agent_type", type);
        suggestion.put("target_id", targetId);
        suggestion.put("suggestions", suggestions);
        suggestion.put("confidence", 0.86);
        suggestion.put("source", "rule");
        suggestion.put("need_human_confirm", true);
        suggestion.put("status", "PENDING");
        suggestion.put("created_at", createdAt);
        return ResponseEntity.ok(ok(suggestion));
    }

    @GetMapping("/health")
    public Map<String, Object> health() { return ok(Map.of("status", "UP")); }
}
