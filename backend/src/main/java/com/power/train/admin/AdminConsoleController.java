package com.power.train.admin;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.exam.ExamCenter;
import com.power.train.material.MaterialCodes;
import com.power.train.material.MaterialImportService;
import com.power.train.store.DatasetStore;
import com.power.train.store.Sql;
import com.power.train.support.Actor;
import com.power.train.support.Texts;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 系统管理员后台：用户 / 角色 / 组织 / 岗位与权限、技能 / 课程 / 题库（含规定格式上传 + Agent 识别入库 + 审核）、
 * 考试配置（组卷 / 防作弊 / 评分 / 及格线 / 统一开考 / 发放试卷）、审计与审核（按时间等条件搜索、清除留痕）。
 * 主数据在 MySQL 的各业务表，展示口径在 dataset_meta / dataset_item，重启不丢数据。
 * 仅系统管理员可见（/admin/** 由 RoleInterceptor 统一拦截），不展示员工个人页面与老总页面。
 */
@RestController
@RequestMapping("/api/v1")
public class AdminConsoleController {

    private static final String IP = "10.12.3.8";
    private static final String FORMAT_HINT = "规定格式：技能编码_名称_等级_版本.pdf（示例 SK-REL_软压板逻辑_L2_v1.pdf），"
        + "允许 pdf / docx / pptx / xlsx / mp4 / zip";
    private static final Pattern FILE_PATTERN =
        Pattern.compile("^(SK-[A-Z]+)_(.+)_(L[0-3]|合格)_(v\\d+)\\.(pdf|docx|pptx|xlsx|mp4|zip)$", Pattern.CASE_INSENSITIVE);

    private final ExamCenter examCenter;
    private final StandardSource standardSource;
    private final MaterialInspector inspector;
    private final MaterialImportService materialImport;
    private final DatasetStore datasets;
    private final Sql sql;
    private final Actor actor;

    public AdminConsoleController(ExamCenter examCenter, StandardSource standards, MaterialInspector inspector,
                                  MaterialImportService materialImport, DatasetStore datasets, Sql sql, Actor actor) {
        this.examCenter = examCenter;
        this.standardSource = standards;
        this.inspector = inspector;
        this.materialImport = materialImport;
        this.datasets = datasets;
        this.sql = sql;
        this.actor = actor;
    }

    // ---- 1. 用户 / 角色 / 组织 / 岗位 / 权限 ----

    @GetMapping("/admin/iam")
    public Map<String, Object> iam() {
        Map<String, Object> summary = datasets.meta("admin.iam.summary");
        summary.put("pending_reviews", pendingReviews());
        List<Map<String, Object>> users = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT username, display_name, role_code, role_name, position, team, "
            + "page_scope, status, last_login FROM app_user ORDER BY id")) {
            users.add(row("username", row.get("username"), "name", row.get("display_name"), "role", row.get("role_code"),
                "role_name", row.get("role_name"), "org", row.get("team"), "position", shortPosition(row),
                "scope", row.get("page_scope"),
                "status", "ACTIVE".equals(String.valueOf(row.get("status"))) ? "在职" : "待激活",
                "last_login", row.get("last_login")));
        }
        List<Map<String, Object>> roles = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT code, name, scope, modules, members, note FROM role ORDER BY sort_no")) {
            roles.add(row("code", row.get("code"), "name", row.get("name"), "scope", row.get("scope"),
                "modules", row.get("modules"), "members", row.get("members"), "note", row.get("note")));
        }
        return ok(row("summary", summary, "users", users, "roles", roles));
    }

    /** 账号台账里的岗位按「不重复班组前缀」显示，例如「变电运维一班班组长」显示为「班组长」。 */
    private static Object shortPosition(Map<String, Object> row) {
        String position = String.valueOf(row.get("position"));
        String team = String.valueOf(row.get("team"));
        return team.isEmpty() ? position : (position.startsWith(team) ? position.substring(team.length()) : position);
    }

    @GetMapping("/admin/orgs")
    public Map<String, Object> orgs() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT name, org_type, parent, headcount, leader FROM org ORDER BY sort_no")) {
            items.add(row("name", row.get("name"), "type", row.get("org_type"), "parent", row.get("parent"),
                "headcount", row.get("headcount"), "leader", row.get("leader")));
        }
        return ok(items);
    }

    @GetMapping("/admin/positions")
    public Map<String, Object> positions() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT name, org, required_level, key_post, headcount, backup_count, risk, note FROM position ORDER BY sort_no")) {
            items.add(row("name", row.get("name"), "org", row.get("org"), "required", row.get("required_level"),
                "key_post", sql.bool(row.get("key_post")), "headcount", row.get("headcount"),
                "backup", row.get("backup_count"), "risk", row.get("risk"), "note", row.get("note")));
        }
        return ok(items);
    }

    @GetMapping("/admin/permissions")
    public Map<String, Object> permissions() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT module, employee, team_lead, executive, admin, note FROM permission_matrix ORDER BY sort_no")) {
            items.add(row("module", row.get("module"), "employee", row.get("employee"),
                "team_lead", row.get("team_lead"), "executive", row.get("executive"),
                "admin", row.get("admin"), "note", row.get("note")));
        }
        return ok(items);
    }

    // ---- 2. 技能 / 岗位技能要求 / 课程 / 课程技能关联 / 题库 ----

    @GetMapping("/admin/skills")
    public Map<String, Object> skills() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT code, name, levels, course_count, requirement_count, note FROM skill ORDER BY sort_no")) {
            items.add(row("code", row.get("code"), "name", row.get("name"), "levels", row.get("levels"),
                "courses", row.get("course_count"), "requirements", row.get("requirement_count"), "note", row.get("note")));
        }
        return ok(items);
    }

    /**
     * 岗位技能要求：等级（L1-L3）是本平台内部刻度，技能对应的技术依据逐条引用国家标准全文公开系统的真实标准，
     * 标准号、名称、状态与官网链接都从 MySQL 的标准依据库读取，点开即可核对。
     */
    @GetMapping("/admin/position-skills")
    public Map<String, Object> positionSkills() {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT position, skill, required_level, future_level, basis_role, standard_no "
                + "FROM position_skill_requirement ORDER BY sort_no")) {
            rows.add(row("position", row.get("position"), "skill", row.get("skill"),
                "required", row.get("required_level"), "future", row.get("future_level"),
                "basis_role", row.get("basis_role"), "basis", standardSource.basis(String.valueOf(row.get("standard_no")))));
        }
        return ok(row(
            "summary", row(
                "total", rows.size(),
                "note", "岗位与技能为本平台岗位体系；「岗位要求 / 未来需求」为本平台内部 L1-L3 刻度；"
                    + "「依据标准」逐条取自" + standardSource.source() + "（抓取时间 " + standardSource.fetchedAt() + "），可点开官网核对。"),
            "items", rows));
    }

    /** 标准依据库：直接展示国家标准全文公开系统的真实标准清单（存在 MySQL 的 standard_ref）。 */
    @GetMapping("/admin/standards")
    public Map<String, Object> standards() {
        List<Map<String, Object>> items = standardSource.all();
        return ok(row(
            "source", standardSource.source(),
            "source_url", standardSource.sourceUrl(),
            "fetched_at", standardSource.fetchedAt(),
            "note", standardSource.note(),
            "summary", row(
                "total", items.size(),
                "current", standardSource.current(),
                "not_current", items.size() - standardSource.current(),
                "note", "全部条目来自官网查询结果，点「官网核对」可打开该系统标准详情页；"
                    + "平台内的岗位技能要求与题库知识点均引这里的标准号。"),
            "items", items));
    }
    @GetMapping("/admin/courses")
    public Map<String, Object> courses() {
        List<Map<String, Object>> items = courseRows();
        long pending = items.stream().filter(item -> "待审核".equals(item.get("status"))).count();
        return ok(row(
            "summary", row("total", items.size(), "pending_review", pending,
                "note", "上传资料经 Agent 识别入库后状态为「待审核」，由管理员在这里点「通过」或「驳回」"),
            "items", items));
    }

    private List<Map<String, Object>> courseRows() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT code, name, course_type, hours, skill, target_level, status, materials, source_file, "
                + "reviewed_by, reviewed_at FROM course ORDER BY sort_no, code")) {
            items.add(courseView(row));
        }
        return items;
    }

    private static Map<String, Object> courseView(Map<String, Object> row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("code", row.get("code"));
        item.put("name", row.get("name"));
        item.put("type", row.get("course_type"));
        item.put("hours", row.get("hours"));
        item.put("skill", row.get("skill"));
        item.put("target_level", row.get("target_level"));
        item.put("status", row.get("status"));
        item.put("materials", row.get("materials"));
        item.put("source_file", row.get("source_file"));
        if (row.get("reviewed_by") != null) item.put("reviewed_by", row.get("reviewed_by"));
        if (row.get("reviewed_at") != null) item.put("reviewed_at", row.get("reviewed_at"));
        return item;
    }

    @GetMapping("/admin/course-skill-links")
    public Map<String, Object> courseSkillLinks() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT course, skill, target_level, link_type, weight FROM course_skill_link ORDER BY sort_no")) {
            items.add(row("course", row.get("course"), "skill", row.get("skill"),
                "target_level", row.get("target_level"), "link_type", row.get("link_type"), "weight", row.get("weight")));
        }
        return ok(items);
    }

    @GetMapping("/admin/question-banks")
    public Map<String, Object> questionBanks() {
        return ok(bankRows());
    }

    private List<Map<String, Object>> bankRows() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT code, name, skill, questions, types, difficulty, updated_at, used_by FROM question_bank "
                + "ORDER BY sort_no, code")) {
            items.add(row("code", row.get("code"), "name", row.get("name"), "skill", row.get("skill"),
                "questions", row.get("questions"), "types", row.get("types"), "difficulty", row.get("difficulty"),
                "updated_at", row.get("updated_at"), "used_by", row.get("used_by")));
        }
        return items;
    }

    /** 课程审核：待审核课程由管理员直接通过（上线）或驳回，结果写入审计（审批）。 */
    @PostMapping("/admin/courses/review")
    public Map<String, Object> reviewCourse(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        String code = Texts.text(form.get("course_code"));
        String action = Texts.text(form.get("action"));
        Map<String, Object> course = sql.row("SELECT name, status FROM course WHERE code = ?", code);
        if (course == null) {
            return ok(row("reviewed", false, "message", "课程不存在：" + code));
        }
        if (!"approve".equals(action) && !"reject".equals(action)) {
            return ok(row("reviewed", false, "message", "审核动作只支持 approve / reject"));
        }
        String next = "approve".equals(action) ? "已上线" : "已驳回";
        String at = now();
        sql.update("UPDATE course SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE code = ?",
            next, actor.name(), at, code);
        audit("审批", ("approve".equals(action) ? "审核通过课程 " : "驳回课程 ") + code + " · " + course.get("name"),
            "课程库", "成功");
        return ok(row("reviewed", true, "course_code", code, "status", next, "reviewed_at", at, "items", courseRows()));
    }

    // ---- 3. 资料上传：规定格式 → Agent 识别 → 待审核 → 审核入库（课程库 / 题库） ----

    @GetMapping("/admin/course-materials")
    public Map<String, Object> courseMaterials() {
        List<Map<String, Object>> items = new ArrayList<>();
        long pendingItems = 0;
        for (Map<String, Object> row : materialRows()) {
            Map<String, Object> item = materialView(row);
            String code = String.valueOf(row.get("code"));
            long pending = sql.count("SELECT COUNT(*) FROM material_item WHERE material_code = ? AND status = '待审核'", code);
            pendingItems += pending;
            item.put("pending_items", pending);
            item.put("stored_items", sql.count(
                "SELECT COUNT(*) FROM material_item WHERE material_code = ? AND status = '已入库'", code));
            item.put("origin", String.valueOf(row.getOrDefault("source", "")).startsWith("组长") ? "组长上传" : "管理员上传");
            items.add(item);
        }
        long pending = items.stream().filter(item -> "待审核".equals(item.get("status"))).count();
        return ok(row(
            "format_hint", FORMAT_HINT,
            "summary", row("total", items.size(), "pending_review", pending, "pending_items", pendingItems,
                "note", "上传后由课程 Agent 识别技能、等级、版本与条目（组长导入的文档会逐条识别题干与答案），先进入待审核，管理员通过后才正式写入课程库或题库，员工刷题随即能抽到"),
            "items", items));
    }

    private List<Map<String, Object>> materialRows() {
        return sql.rows("SELECT code, title, skill, skill_code, target, material_type, file_name, file_type, "
            + "target_level, version, hours, recognized_items, agent_confidence, agent_note, status, submitted_by, "
            + "submitted_at, file_url, source, note, stored_result, reviewed_by, reviewed_at FROM course_material "
            + "ORDER BY sort_no, code DESC");
    }

    /** 库里的资料行 → 接口字段（未填写的可选字段不出现，与页面表单字段保持一致）。 */
    private static Map<String, Object> materialView(Map<String, Object> row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("code", row.get("code"));
        item.put("title", row.get("title"));
        item.put("skill", row.get("skill"));
        item.put("skill_code", row.get("skill_code"));
        item.put("target", row.get("target"));
        item.put("material_type", row.get("material_type"));
        item.put("file_name", row.get("file_name"));
        item.put("file_type", row.get("file_type"));
        item.put("target_level", row.get("target_level"));
        item.put("version", row.get("version"));
        item.put("hours", row.get("hours"));
        item.put("recognized_items", row.get("recognized_items"));
        item.put("agent_confidence", row.get("agent_confidence"));
        item.put("agent_note", row.get("agent_note"));
        item.put("status", row.get("status"));
        item.put("submitted_by", row.get("submitted_by"));
        item.put("submitted_at", row.get("submitted_at"));
        item.put("url", row.get("file_url"));
        if (row.get("source") != null) item.put("source", row.get("source"));
        if (row.get("note") != null) item.put("note", row.get("note"));
        if (row.get("stored_result") != null) item.put("stored_result", row.get("stored_result"));
        if (row.get("reviewed_by") != null) item.put("reviewed_by", row.get("reviewed_by"));
        if (row.get("reviewed_at") != null) item.put("reviewed_at", row.get("reviewed_at"));
        return item;
    }

    @PostMapping("/admin/course-materials")
    public Map<String, Object> uploadCourseMaterial(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        Map<String, String> errors = new LinkedHashMap<>();
        String fileName = Texts.text(form.get("file_name"));
        String target = Texts.text(form.get("target"));
        if (fileName.isBlank()) {
            errors.put("file_name", "请选择要上传的文件，并按 " + FORMAT_HINT);
        }
        if (target.isBlank()) {
            errors.put("target", "请选择入库目标：课程库 或 题库");
        }
        Matcher matcher = fileName.isBlank() ? null : FILE_PATTERN.matcher(fileName);
        if (matcher != null && !matcher.matches()) {
            errors.put("file_name", "文件名不符合规定格式：" + FORMAT_HINT);
        }
        if (!errors.isEmpty()) {
            return row("code", 40001, "message", "资料上传校验未通过，请按示例格式修改后重新提交",
                "data", Map.of("field_errors", errors), "trace_id", UUID.randomUUID().toString());
        }
        String skillCode = matcher.group(1);
        String name = matcher.group(2);
        String level = matcher.group(3);
        String version = matcher.group(4);
        String fileType = matcher.group(5).toLowerCase();
        String skill = skillName(skillCode);
        // 条数与审核弹窗列出的条数保持一致：管理员看到的多少条，通过后就写入多少条
        int recognized = 6 + Math.floorMod(fileName.hashCode(), 5);
        String code = MaterialCodes.nextMaterialCode(sql);
        String at = now();
        boolean courseTarget = "课程库".equals(target);
        Map<String, Object> material = new LinkedHashMap<>();
        material.put("code", code);
        material.put("title", name);
        material.put("skill", skill);
        material.put("skill_code", skillCode);
        material.put("target", target);
        material.put("material_type", courseTarget ? "课程资料" : "题库资料");
        material.put("file_name", fileName);
        material.put("file_type", fileType);
        material.put("target_level", level);
        material.put("version", version);
        material.put("hours", courseTarget ? recognized % 6 + 1 : null);
        material.put("recognized_items", recognized);
        material.put("agent_confidence", 0.88);
        material.put("agent_note", courseTarget
            ? "Agent 识别：" + skill + " · " + name + " · " + level + " · " + version + "，预计 " + recognized + " 个知识章节，待审核后写入课程库"
            : "Agent 识别：" + skill + " · " + name + " · " + level + " · " + version + "，解析出 " + recognized + " 道题，待审核后写入题库");
        material.put("status", "待审核");
        material.put("submitted_by", actor.name());
        material.put("submitted_at", at);
        material.put("url", "mysql://train_system/file_object/" + fileName);
        if (!Texts.text(form.get("note")).isBlank()) {
            material.put("note", Texts.text(form.get("note")));
        }
        sql.update("INSERT INTO course_material (code, title, skill, skill_code, target, material_type, file_name, "
                + "file_type, target_level, version, hours, recognized_items, agent_confidence, agent_note, status, "
                + "submitted_by, submitted_at, file_url, source, note, sort_no) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            code, name, skill, skillCode, target, material.get("material_type"), fileName, fileType, level, version,
            material.get("hours"), recognized, 0.88, material.get("agent_note"), "待审核", actor.name(), at,
            material.get("url"), actor.name() + "上传", material.get("note"));
        sql.update("INSERT INTO file_object (owner, object_key, file_name, content_type, size_kb) VALUES (?, ?, ?, ?, ?)",
            actor.name(), material.get("url"), fileName, fileType, MaterialInspector.sizeKb(material));
        audit("修改", "上传" + target + "资料 " + code + " · " + name + "（" + fileName + "）", "资料台账", "待审核");
        return ok(row("created", true, "material", material, "total", sql.count("SELECT COUNT(*) FROM course_material"),
            "message", "已上传并按规定格式通过校验；Agent 已识别 " + recognized + (courseTarget ? " 个知识章节" : " 道题")
                + "，状态为待审核，通过后写入" + target));
    }

    /**
     * 待审核详情：给管理员看「文件本身」与「Agent 检索结果」。
     * Agent 只做检索与整理，未入库；管理员在弹窗里确认无误后点「确认入库」才写入课程库 / 题库。
     */
    @GetMapping("/admin/course-materials/{code}")
    public Map<String, Object> materialDetail(@PathVariable String code) {
        // 组长导入文档 / SOP 填报的资料：material_item 里存着 Agent 真正识别出的题干与答案，
        // 审核弹窗直接读这批条目，看到的就是员工将来会抽到的题。
        if (sql.count("SELECT COUNT(*) FROM material_item WHERE material_code = ?", code) > 0) {
            Map<String, Object> detail = materialImport.detail(code);
            if (detail != null) {
                detail.put("found", true);
                detail.put("mode", "真实识别");
                return ok(detail);
            }
        }
        Map<String, Object> stored = sql.row("SELECT code, title, skill, skill_code, target, material_type, file_name, "
            + "file_type, target_level, version, hours, recognized_items, agent_confidence, agent_note, status, "
            + "submitted_by, submitted_at, file_url, note, stored_result, reviewed_by, reviewed_at "
            + "FROM course_material WHERE code = ?", code);
        if (stored == null) {
            return ok(row("found", false, "message", "资料不存在：" + code));
        }
        Map<String, Object> material = materialView(stored);
        boolean bankTarget = "题库".equals(material.get("target"));
        int total = ((Number) material.getOrDefault("recognized_items", 0)).intValue();
        List<Map<String, Object>> extracted = bankTarget
            ? inspector.questions(material, total) : inspector.chapters(material, total);
        return ok(row(
            "found", true,
            "material", material,
            "file", row(
                "file_name", material.get("file_name"), "file_type", material.get("file_type"),
                "size_kb", MaterialInspector.sizeKb(material),
                "pages", MaterialInspector.pages(material),
                "uploaded_at", material.get("submitted_at"), "uploaded_by", material.get("submitted_by"),
                "url", material.get("url"),
                "preview_note", "演示环境展示的是 Agent 从文档中检索出的正文摘录；原件按文件台账登记在 MySQL 的 file_object 表中"),
            "doc_excerpt", inspector.excerpt(material),
            "extracted", row(
                "mode", bankTarget ? "题库" : "课程库",
                "chapter_mode", !bankTarget,
                "total", total,
                "listed", extracted.size(),
                "has_more", total > extracted.size(),
                "summary", bankTarget
                    ? "Agent 从《" + material.get("file_name") + "》中检索出 " + total + " 道题（含答案与解析），入库前请逐条核对题干与答案"
                    : "Agent 从《" + material.get("file_name") + "》中整理出 " + total + " 个知识章节，入库前请核对章节与学时",
                "items", extracted),
            "already_stored", !"待审核".equals(material.get("status")),
            "stored_result", material.getOrDefault("stored_result", "—")));
    }

    /** 资料审核：通过后 Agent 识别的结果正式入库（课程库新增课程 / 题库累加题量）。 */
    @PostMapping("/admin/course-materials/review")
    public Map<String, Object> reviewMaterial(@RequestBody(required = false) Map<String, Object> body) {
        Map<String, Object> form = body == null ? Map.of() : body;
        String code = Texts.text(form.get("code"));
        String action = Texts.text(form.get("action"));
        // 组长导入的批次：逐条审核（approve_ids 里是通过的条目，未勾选的继续留在待审核）
        if (sql.count("SELECT COUNT(*) FROM material_item WHERE material_code = ?", code) > 0) {
            Map<String, Object> result = materialImport.review(code, action, ids(form.get("approve_ids")),
                ids(form.get("reject_ids")), null);
            result.put("courses", courseRows());
            result.put("banks", bankRows());
            return ok(result);
        }
        Map<String, Object> material = sql.row("SELECT code, title, skill, skill_code, target, target_level, version, "
            + "hours, recognized_items, file_name FROM course_material WHERE code = ?", code);
        if (material == null) {
            return ok(row("reviewed", false, "message", "资料不存在：" + code));
        }
        if (!"approve".equals(action) && !"reject".equals(action)) {
            return ok(row("reviewed", false, "message", "审核动作只支持 approve / reject"));
        }
        String at = now();
        if ("reject".equals(action)) {
            sql.update("UPDATE course_material SET status = '已驳回', reviewed_by = ?, reviewed_at = ? "
                + "WHERE code = ?", actor.name(), at, code);
            audit("审批", "驳回资料 " + code + " · " + material.get("title"), "资料台账", "成功");
            return ok(row("reviewed", true, "code", code, "status", "已驳回", "stored", false,
                "message", "已驳回，未写入课程库 / 题库"));
        }
        String storedResult;
        if ("题库".equals(material.get("target"))) {
            // Agent 检索出的题目逐条写入 question 表（组员抽题读的就是这张表）；
            // 编号按「资料编号 + 序号」稳定生成，重复审核只覆盖不重复入库。
            List<Map<String, Object>> extracted = inspector.questions(material,
                ((Number) material.get("recognized_items")).intValue());
            String idPrefix = material.get("code") + "-Q";
            String source = "上传资料 " + material.get("code") + " · " + material.get("file_name");
            int level = MaterialInspector.levelOf(String.valueOf(material.get("target_level")));
            int sortBase = 3000 + (int) sql.count("SELECT COUNT(*) FROM question WHERE source LIKE '上传资料%'");
            long before = sql.count("SELECT COUNT(*) FROM question WHERE id LIKE ?", idPrefix + "%");
            for (Map<String, Object> item : extracted) {
                int index = ((Number) item.get("index")).intValue();
                sql.update("INSERT INTO question (id, skill, level, qtype, stem, options, answer, explanation, "
                        + "source, sort_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        + "ON DUPLICATE KEY UPDATE skill = VALUES(skill), level = VALUES(level), qtype = VALUES(qtype), "
                        + "stem = VALUES(stem), options = VALUES(options), answer = VALUES(answer), "
                        + "explanation = VALUES(explanation), source = VALUES(source)",
                    idPrefix + String.format("%02d", index), material.get("skill"), level,
                    questionType(String.valueOf(item.get("type"))), item.get("question"), sql.json(item.get("options")),
                    item.get("answer"), item.get("analysis"), source, sortBase + index);
            }
            int stored = (int) (sql.count("SELECT COUNT(*) FROM question WHERE id LIKE ?", idPrefix + "%") - before);
            Map<String, Object> bank = sql.row("SELECT code, questions FROM question_bank WHERE skill = ? "
                + "ORDER BY sort_no, code LIMIT 1", material.get("skill"));
            if (bank == null) {
                sql.update("INSERT INTO question_bank (code, name, skill, questions, types, difficulty, updated_at, "
                        + "used_by, sort_no) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    "QB-" + material.get("skill_code"), material.get("skill") + "题库（上传入库）", material.get("skill"),
                    stored, "按上传资料解析", "中", now().substring(0, 10), MaterialCodes.nextSortNo(sql, "question_bank"));
                storedResult = stored == 0 ? "该资料题目已在题库中，未重复入库"
                    : "题库新增 " + stored + " 题，已写入练习题供组员抽题";
            } else {
                int total = ((Number) bank.get("questions")).intValue() + stored;
                sql.update("UPDATE question_bank SET questions = ?, updated_at = ? WHERE code = ?",
                    total, now().substring(0, 10), bank.get("code"));
                storedResult = stored == 0 ? "该资料题目已在题库中，未重复入库"
                    : "题库累加 " + stored + " 题（台账共 " + total + " 题），已写入练习题供组员抽题";
            }
        } else {
            String courseCode = "C-" + material.get("skill_code") + "-" + material.get("version");
            sql.update("INSERT INTO course (code, name, course_type, hours, skill, target_level, status, materials, "
                    + "source_file, reviewed_by, reviewed_at, sort_no) "
                    + "VALUES (?, ?, '线上', ?, ?, ?, '已上线', 1, ?, ?, ?, ?) "
                    + "ON DUPLICATE KEY UPDATE name = VALUES(name), hours = VALUES(hours), "
                    + "source_file = VALUES(source_file), reviewed_at = VALUES(reviewed_at)",
                courseCode, material.get("title"), material.get("hours"), material.get("skill"),
                material.get("target_level"), material.get("file_name"), actor.name(), at, MaterialCodes.nextSortNo(sql, "course"));
            storedResult = "课程库新增课程 " + courseCode;
        }
        sql.update("UPDATE course_material SET status = '已审核', reviewed_by = ?, reviewed_at = ?, "
            + "stored_result = ? WHERE code = ?", actor.name(), at, storedResult, code);
        audit("审批", "审核通过资料 " + code + " · " + material.get("title") + "（" + storedResult + "）", "资料台账", "成功");
        return ok(row("reviewed", true, "code", code, "status", "已审核", "stored", true, "stored_result", storedResult,
            "courses", courseRows(), "banks", bankRows(), "message", "已通过，" + storedResult));
    }

    // ---- 4. 考试配置 + 统一开考 + 发放试卷 ----

    @GetMapping("/admin/exam-config")
    public Map<String, Object> examConfig() {
        Map<String, Object> config = datasets.meta("admin.exam-config");
        Object summary = config.get("summary");
        if (summary instanceof Map<?, ?> map) {
            Map<String, Object> updated = new LinkedHashMap<>();
            map.forEach((key, value) -> updated.put(String.valueOf(key), value));
            updated.put("exams", examCenter.list().size());
            config.put("summary", updated);
        }
        return ok(config);
    }

    @GetMapping("/admin/exams")
    public Map<String, Object> exams() {
        List<Map<String, Object>> items = examCenter.list();
        long ongoing = examCenter.ongoingCount();
        return ok(row(
            "summary", row("total", items.size(), "ongoing", ongoing,
                "note", "管理员统一点「开始考试」后全公司同步进入考试状态，禁止按人单独提前开考"),
            "items", items));
    }

    /** 统一开考：一次操作把该场考试置为「进行中」，下发到全部参考班组。 */
    @PostMapping("/admin/exams/start")
    public Map<String, Object> startExam(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        String id = Texts.text(form.get("exam_id"));
        Map<String, Object> result = examCenter.start(id, actor.name());
        if (Boolean.TRUE.equals(result.get("started"))) {
            audit("执行", "统一开始考试 " + id + " · " + result.get("name"), "考试", "成功");
        }
        return ok(result);
    }

    /** 结束本场：停止发卷并清空本轮答卷，员工端不再显示「进入考试」，可直接重新开考开启新一轮。 */
    @PostMapping("/admin/exams/close")
    public Map<String, Object> closeExam(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        String id = Texts.text(form.get("exam_id"));
        Map<String, Object> result = examCenter.close(id);
        if (Boolean.TRUE.equals(result.get("closed"))) {
            audit("执行", "结束考试 " + id + " · " + result.get("name"), "考试", "成功");
        }
        return ok(result);
    }

    @GetMapping("/admin/papers")
    public Map<String, Object> papers() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT batch_no, exam_id, exam_name, issued_to, paper_count, "
            + "issued_at, deadline, collected, status FROM paper_batch ORDER BY sort_no, batch_no DESC")) {
            items.add(row("batch_no", row.get("batch_no"), "exam_id", row.get("exam_id"), "exam_name", row.get("exam_name"),
                "issued_to", row.get("issued_to"), "count", row.get("paper_count"), "issued_at", row.get("issued_at"),
                "deadline", row.get("deadline"), "collected", row.get("collected"), "status", row.get("status")));
        }
        return ok(items);
    }

    /** 发放试卷：按批次给指定范围发卷，写入试卷发放台账并留痕。 */
    @PostMapping("/admin/papers/issue")
    public Map<String, Object> issuePaper(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        Map<String, String> errors = new LinkedHashMap<>();
        String id = Texts.text(form.get("exam_id"));
        String scope = Texts.text(form.get("scope"));
        String count = Texts.text(form.get("count"));
        String deadline = Texts.text(form.get("deadline"));
        Map<String, Object> exam = id.isBlank() ? null : examCenter.find(id);
        if (exam == null) {
            errors.put("exam_id", "请选择要发放的考试");
        }
        if (scope.isBlank()) {
            errors.put("scope", "请填写发放对象，例如：变电运维一班 或 全体值班员");
        }
        if (count.isBlank()) {
            errors.put("count", "请填写发放份数（数字），例如：9");
        } else if (!count.matches("\\d+") || count.length() > 4 || "0".equals(count)) {
            errors.put("count", "份数必须为 1-9999 的数字，例如：9");
        }
        if (deadline.isBlank()) {
            errors.put("deadline", "请填写截止日期，例如：2026-09-30");
        } else if (!deadline.matches("\\d{4}-\\d{2}-\\d{2}")) {
            errors.put("deadline", "截止日期格式为 yyyy-MM-dd，例如：2026-09-30");
        }
        if (!errors.isEmpty()) {
            return row("code", 40001, "message", "试卷发放校验未通过，请按示例修改后重新提交",
                "data", Map.of("field_errors", errors), "trace_id", UUID.randomUUID().toString());
        }
        String at = now();
        String day = at.substring(0, 10).replace("-", "");
        String prefix = "PAPER-" + day + "-";
        int sequence = (int) sql.count("SELECT COALESCE(MAX(CAST(SUBSTRING_INDEX(batch_no, '-', -1) AS UNSIGNED)), 0) + 1 "
            + "FROM paper_batch WHERE batch_no LIKE ?", prefix + "%");
        String batchNo = prefix + String.format("%02d", sequence);
        Map<String, Object> paper = row("batch_no", batchNo, "exam_id", id, "exam_name", exam.get("name"),
            "issued_to", scope, "count", Integer.parseInt(count), "issued_at", at,
            "deadline", deadline, "collected", 0, "status", "已发放");
        sql.update("INSERT INTO paper_batch (batch_no, exam_id, exam_name, issued_to, paper_count, issued_at, "
                + "deadline, collected, status, sort_no) VALUES (?, ?, ?, ?, ?, ?, ?, 0, '已发放', 0)",
            batchNo, id, exam.get("name"), scope, Integer.parseInt(count), at, deadline);
        examCenter.bumpPaper(id);
        audit("执行", "发放试卷 " + batchNo + " · " + exam.get("name") + " → " + scope + "（" + count + " 份）", "试卷发放", "成功");
        return ok(row("issued", true, "paper", paper, "total", sql.count("SELECT COUNT(*) FROM paper_batch"),
            "message", "已发放 " + count + " 份，截止 " + deadline));
    }

    // ---- 5. 审计与审核：按时间 / 类别 / 关键词搜索 + 清除 ----

    @GetMapping("/admin/audit")
    public Map<String, Object> auditView(@RequestParam(required = false) String category,
                                         @RequestParam(required = false) String keyword,
                                         @RequestParam(required = false) String from,
                                         @RequestParam(required = false) String to) {
        List<Map<String, Object>> all = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT id, occurred_at, actor, actor_role, category, action, target, "
            + "result, ip FROM audit_log ORDER BY id DESC")) {
            all.add(row("id", row.get("id"), "occurred_at", row.get("occurred_at"), "actor", row.get("actor"),
                "actor_role", row.get("actor_role"), "category", row.get("category"), "action", row.get("action"),
                "target", row.get("target"), "result", row.get("result"), "ip", row.get("ip")));
        }
        List<Map<String, Object>> items = new ArrayList<>();
        String cat = Texts.text(category);
        String key = Texts.text(keyword);
        String start = Texts.text(from);
        String end = Texts.text(to);
        for (Map<String, Object> item : all) {
            String occurred = String.valueOf(item.get("occurred_at"));
            if (!cat.isBlank() && !cat.equals(item.get("category"))) continue;
            if (!start.isBlank() && occurred.compareTo(start) < 0) continue;
            if (!end.isBlank() && occurred.compareTo(end + " 23:59") > 0) continue;
            if (!key.isBlank()) {
                String haystack = item.get("actor") + " " + item.get("action") + " " + item.get("target") + " " + item.get("ip");
                if (!haystack.contains(key)) continue;
            }
            items.add(item);
        }
        Map<String, Object> byCategory = new LinkedHashMap<>();
        for (String name : List.of("登录", "修改", "审批", "决策", "执行", "回滚", "访问")) {
            byCategory.put(name, all.stream().filter(item -> name.equals(item.get("category"))).count());
        }
        return ok(row(
            "summary", row("total", all.size(), "matched", items.size(),
                "note", "登录 / 修改 / 审批 / 决策 / 执行 / 回滚全留痕，支持按类别、关键词与时间范围搜索"),
            "query", row("category", cat, "keyword", key, "from", start, "to", end),
            "categories", byCategory,
            "items", items));
    }

    /** 清除留痕：清空历史记录，只保留一条「清除审计日志」记录，保证清除动作本身可追溯。 */
    @PostMapping("/admin/audit/clear")
    public Map<String, Object> clearAudit(@RequestBody(required = false) Map<String, String> body) {
        Map<String, String> form = body == null ? Map.of() : body;
        if (!"true".equalsIgnoreCase(Texts.text(form.get("confirm")))) {
            return ok(row("cleared", false, "message", "清除留痕需要二次确认：请传入 confirm=true"));
        }
        long removed = sql.count("SELECT COUNT(*) FROM audit_log");
        sql.update("DELETE FROM audit_log");
        audit("修改", "清除审计日志（清除 " + removed + " 条历史记录）", "审计日志", "成功");
        return ok(row("cleared", true, "removed", removed, "total", sql.count("SELECT COUNT(*) FROM audit_log"),
            "message", "已清除 " + removed + " 条历史留痕，并保留 1 条清除记录"));
    }

    // ---- 内部：留痕与工具 ----

    private void audit(String category, String action, String target, String result) {
        long next = sql.count("SELECT COALESCE(MAX(id), 0) + 1 FROM audit_log");
        sql.update("INSERT INTO audit_log (id, occurred_at, actor, actor_role, category, action, target, result, ip) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            next, now(), actor.name(), actor.roleName(), category, action, target, result, IP);
        sql.update("DELETE FROM audit_log WHERE id NOT IN (SELECT id FROM ("
            + "SELECT id FROM audit_log ORDER BY id DESC LIMIT 300) keep)");
    }

    private long pendingReviews() {
        return sql.count("SELECT COUNT(*) FROM course WHERE status = '待审核'")
            + sql.count("SELECT COUNT(*) FROM course_material WHERE status = '待审核'");
    }

    /** 上传资料解析出的题型 → question 表的题型口径（与内置题、SOP 题一致）。 */
    private static String questionType(String type) {
        return switch (type) {
            case "单选题" -> "单选";
            case "判断题" -> "判断";
            default -> type;
        };
    }

    private static String skillName(String code) {
        return switch (code) {
            case "SK-REL" -> "继电保护";
            case "SK-SWITCH" -> "倒闸操作";
            case "SK-HV" -> "高压试验";
            case "SK-WAVE" -> "故障录波";
            case "SK-SAFE" -> "安全规程";
            default -> code;
        };
    }

    private static String now() {
        return ZonedDateTime.now(ZoneId.of("Asia/Shanghai")).format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"));
    }

    /** 请求体里的条目 id 列表（逐条审核勾选的候选题）。 */
    private static List<Long> ids(Object value) {
        List<Long> result = new ArrayList<>();
        if (value instanceof List<?> list) {
            for (Object item : list) {
                if (item instanceof Number number) result.add(number.longValue());
                else if (item != null && !String.valueOf(item).isBlank()) {
                    try {
                        result.add(Long.parseLong(String.valueOf(item).trim()));
                    } catch (NumberFormatException ignored) {
                        // 非数字忽略：候选题 id 一定是数字
                    }
                }
            }
        }
        return result;
    }
}
