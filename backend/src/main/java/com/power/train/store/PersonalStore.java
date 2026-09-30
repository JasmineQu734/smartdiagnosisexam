package com.power.train.store;

import com.power.train.support.Texts;
import com.power.train.support.Users;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * 员工个人侧数据：身份、技能雷达、个人能力、学习、资源、证书、任务、班组报告。
 * 全部来自 MySQL（主数据表 + 后台维护的数据集），不再有内存态常量。
 */
@Component
public class PersonalStore {

    private final Sql sql;
    private final DatasetStore datasets;

    public PersonalStore(Sql sql, DatasetStore datasets) {
        this.sql = sql;
        this.datasets = datasets;
    }

    // ---- 身份 ----

    /** 演示账号身份：角色、页面范围与员工档案（app_user）。 */
    public Map<String, Object> identity(String username) {
        Map<String, Object> user = findIdentity(username);
        return user == null ? findIdentity(Users.DEFAULT) : user;
    }

    /** 严格按账号查身份，查不到返回 null（登录接口据此拒绝未知账号，不再静默回落成演示账号）。 */
    public Map<String, Object> findIdentity(String username) {
        if (username == null || username.isBlank()) return null;
        return sql.row(
            "SELECT username, display_name, role_code AS role, role_name, position, team, org, page_scope FROM app_user WHERE username = ?",
            username);
    }

    /** 当前账号的展示名（查不到时回落到账号名本身，避免把操作记到别人名下）。 */
    public String displayName(String username) {
        Map<String, Object> row = sql.row("SELECT display_name FROM app_user WHERE username = ?", username);
        return row == null ? username : String.valueOf(row.get("display_name"));
    }

    /** 当前账号的岗位名称（查不到时返回空串）。 */
    public String positionOf(String username) {
        Map<String, Object> row = sql.row("SELECT position FROM app_user WHERE username = ?", username);
        return row == null ? "" : String.valueOf(row.get("position"));
    }

    // ---- 技能雷达 / 个人能力 ----

    public List<Map<String, Object>> skillRadar(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, level, required_level, future_level, level_label, required_label, future_label, state, priority, radar_note "
                + "FROM employee_skill WHERE username = ? AND in_radar = 1 ORDER BY sort_no", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("skill", row.get("skill"));
            item.put("current", row.get("level"));
            item.put("required", row.get("required_level"));
            item.put("future", row.get("future_level"));
            item.put("level_label", row.get("level_label"));
            item.put("required_label", row.get("required_label"));
            item.put("future_label", row.get("future_label"));
            item.put("state", row.get("state"));
            item.put("priority", row.get("priority"));
            item.put("note", row.get("radar_note"));
            items.add(item);
        }
        return items;
    }

    public Map<String, Object> profile(String username) {
        Map<String, Object> stored = datasets.meta("personal.profile");
        Map<String, Object> user = identity(username);
        Map<String, Object> profile = new LinkedHashMap<>(stored);
        if (user != null) {
            profile.put("name", user.get("display_name"));
            profile.put("position", user.get("position"));
            profile.put("org", user.get("org"));
        }
        return profile;
    }

    /** 个人能力：硬技能取自 employee_skill，其余能力块取自维护数据集。 */
    public Map<String, Object> abilities(String username) {
        List<Map<String, Object>> hardSkills = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, level, required_level, level_label, trend, evidence FROM employee_skill "
                + "WHERE username = ? ORDER BY sort_no", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("name", row.get("skill"));
            item.put("level", row.get("level"));
            item.put("required_level", row.get("required_level"));
            item.put("level_label", row.get("level_label"));
            item.put("trend", row.get("trend"));
            item.put("evidence", row.get("evidence"));
            hardSkills.add(item);
        }
        Map<String, Object> extras = datasets.meta("personal.abilities.extras");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("hard_skills", hardSkills);
        result.put("soft_skills", extras.get("soft_skills"));
        result.put("safety", extras.get("safety"));
        result.put("practice", extras.get("practice"));
        result.put("exams", extras.get("exams"));
        result.put("certificates", certificateDetails(username));
        return result;
    }

    public List<Map<String, Object>> certificates(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT id, name, level, issued_at, status FROM certificate WHERE username = ? ORDER BY sort_no DESC", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("name", row.get("name"));
            item.put("level", row.get("level"));
            item.put("issued_at", row.get("issued_at"));
            item.put("status", row.get("status"));
            items.add(item);
        }
        return items;
    }

    public List<Map<String, Object>> certificateDetails(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT name, level, issued_at, expires_at, review_note FROM certificate WHERE username = ? ORDER BY sort_no DESC",
            username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("name", row.get("name"));
            item.put("level", row.get("level"));
            item.put("issued_at", row.get("issued_at"));
            item.put("expires_at", row.get("expires_at"));
            item.put("review_note", row.get("review_note"));
            items.add(item);
        }
        return items;
    }

    // ---- 学习总版 ----

    public Map<String, Object> learningSummary(String username) {
        Map<String, Object> row = sql.row(
            "SELECT month_hours, target_hours, completion, required_done, required_total, streak_days, last_exam_name, "
                + "last_exam_score, last_exam_pass_score, focus_skill, mentor_sessions FROM learning_summary WHERE username = ?",
            username);
        return row == null ? new LinkedHashMap<>() : row;
    }

    public List<Map<String, Object>> learningPlan(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT course_code, course_name, course_type, hours, progress, required, skill, target_level, due_at "
                + "FROM learning_plan WHERE username = ? ORDER BY sort_no", username)) {
            Map<String, Object> item = new LinkedHashMap<>(row);
            item.put("required", sql.bool(row.get("required")));
            items.add(item);
        }
        return items;
    }

    public List<Map<String, Object>> learningRecords(String username) {
        return sql.rows(
            "SELECT id, course_name, progress, hours, studied_at, status, remark FROM learning_record "
                + "WHERE username = ? ORDER BY sort_no DESC", username);
    }

    public List<Map<String, Object>> resources() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT id, title, item_type, duration, skill, level, origin, site, match_reason, jump_to, url "
                + "FROM resource_item ORDER BY sort_no")) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("title", row.get("title"));
            item.put("type", row.get("item_type"));
            item.put("duration", row.get("duration"));
            item.put("skill", row.get("skill"));
            item.put("level", row.get("level"));
            item.put("origin", row.get("origin"));
            item.put("site", row.get("site"));
            item.put("match_reason", row.get("match_reason"));
            if (row.get("jump_to") != null) {
                item.put("jump", row.get("jump_to"));
            }
            if (row.get("url") != null) {
                item.put("url", row.get("url"));
            }
            items.add(item);
        }
        return items;
    }

    // ---- 外网课程搜索 ----

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    /**
     * 外网课程搜索：外网课程库（external_course）按关键词打分排序，命中的站内资料一并返回，
     * 并给出公开课程平台的实时检索直达链接（external_course_source.search_url 里的 {kw} 换成关键词）。
     * 关键词为空时按当前技能缺口（employee_skill：level < required_level）优先排序，缺口技能的外网课程排前面。
     */
    public Map<String, Object> searchExternalCourses(String username, String keyword, String platform, String skill, String level) {
        long startedAt = System.currentTimeMillis();
        String raw = keyword == null ? "" : keyword.trim();
        List<String> terms = new ArrayList<>();
        for (String token : raw.toLowerCase().split("[\\s,，、]+")) {
            if (!token.isBlank() && !terms.contains(token)) {
                terms.add(token);
            }
        }
        List<String> gapSkills = gapSkills(username);

        // 平台与直达链接：搜了关键词才拼实时检索地址，没搜就给平台首页；http_code 是最近一次核验结果。
        List<Map<String, Object>> platforms = new ArrayList<>();
        Map<String, String> platformNames = new LinkedHashMap<>();
        Map<String, String> platformSites = new LinkedHashMap<>();
        int platformOk = 0;
        String checkedAt = "";
        for (Map<String, Object> row : sql.rows(
            "SELECT code, name, site, category, home_url, search_url, http_code, checked_at, note "
                + "FROM external_course_source ORDER BY sort_no")) {
            String code = String.valueOf(row.get("code"));
            platformNames.put(code, String.valueOf(row.get("name")));
            platformSites.put(code, String.valueOf(row.get("site")));
            checkedAt = String.valueOf(row.get("checked_at"));
            if (longOf(row.get("http_code")) == 200) {
                platformOk++;
            }
            if (!platform.isBlank() && !platform.equalsIgnoreCase(code)) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("code", code);
            item.put("name", row.get("name"));
            item.put("site", row.get("site"));
            item.put("category", row.get("category"));
            item.put("home_url", row.get("home_url"));
            item.put("note", row.get("note"));
            item.put("http_code", row.get("http_code"));
            item.put("checked_at", row.get("checked_at"));
            item.put("url", raw.isEmpty() ? ""
                : String.valueOf(row.get("search_url")).replace("{kw}", URLEncoder.encode(raw, StandardCharsets.UTF_8)));
            platforms.add(item);
        }
        // 外网课程库打分：标题 > 检索词 > 标签 > 技能 > 选题机构 > 匹配理由；没命中关键词的直接不返回。
        List<Map<String, Object>> external = new ArrayList<>();
        int catalogSize = 0;
        for (Map<String, Object> row : sql.rows(
            "SELECT id, title, source_code, course_type, duration, skill, level, org, search_keyword, url, tags, match_reason "
                + "FROM external_course ORDER BY sort_no")) {
            catalogSize++;
            String code = String.valueOf(row.get("source_code"));
            String rowSkill = String.valueOf(row.get("skill"));
            if (!platform.isBlank() && !platform.equalsIgnoreCase(code)) {
                continue;
            }
            if (!skill.isBlank() && !skill.equals(rowSkill)) {
                continue;
            }
            if (!level.isBlank() && !level.equals(String.valueOf(row.get("level")))) {
                continue;
            }
            String title = String.valueOf(row.get("title"));
            String keywordCell = String.valueOf(row.get("search_keyword"));
            String tags = String.valueOf(row.get("tags"));
            String org = String.valueOf(row.get("org"));
            String reason = String.valueOf(row.get("match_reason"));
            int score = 0;
            List<String> hits = new ArrayList<>();
            // 每个检索词只留一条命中说明（按命中位置从强到弱），避免一屏都是同一个词
            for (String term : terms) {
                String hit = null;
                if (title.toLowerCase().contains(term)) {
                    score += 6;
                    hit = "标题命中「" + term + "」";
                }
                if (keywordCell.toLowerCase().contains(term)) {
                    score += 4;
                    if (hit == null) {
                        hit = "检索词命中「" + term + "」";
                    }
                }
                if (tags.toLowerCase().contains(term)) {
                    score += 3;
                    if (hit == null) {
                        hit = "标签命中「" + term + "」";
                    }
                }
                if (rowSkill.toLowerCase().contains(term)) {
                    score += 3;
                    if (hit == null) {
                        hit = "技能命中「" + term + "」";
                    }
                }
                if (org.toLowerCase().contains(term)) {
                    score += 2;
                }
                if (reason.toLowerCase().contains(term)) {
                    score += 1;
                    if (hit == null) {
                        hit = "匹配理由命中「" + term + "」";
                    }
                }
                if (hit != null) {
                    hits.add(hit);
                }
            }
            if (!terms.isEmpty() && score == 0) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("title", title);
            item.put("platform", platformNames.getOrDefault(code, code));
            item.put("platform_code", code);
            item.put("site", platformSites.getOrDefault(code, ""));
            item.put("type", row.get("course_type"));
            item.put("duration", row.get("duration"));
            item.put("skill", rowSkill);
            item.put("level", row.get("level"));
            item.put("org", org);
            item.put("search_keyword", keywordCell);
            item.put("url", row.get("url"));
            item.put("tags", splitTags(tags));
            item.put("match_reason", reason);
            item.put("match_hits", hits);
            item.put("gap_match", gapSkills.contains(rowSkill));
            item.put("score", score);
            external.add(item);
        }
        Comparator<Map<String, Object>> byScore = Comparator.comparingInt(
            item -> intOf(item.get("score")) * 10 + (Boolean.TRUE.equals(item.get("gap_match")) ? 5 : 0));
        external.sort(byScore.reversed());
        int externalTotal = external.size();
        List<Map<String, Object>> topExternal = externalTotal > 12 ? new ArrayList<>(external.subList(0, 12)) : external;
        // 站内命中：推荐资源与课程库里同关键词的资料，点「去对应板块 / 打开外网资料」都能直接落地。
        List<Map<String, Object>> internal = new ArrayList<>();
        if (!terms.isEmpty()) {
            Map<String, Map<String, Object>> seen = new LinkedHashMap<>();
            for (String term : terms) {
                String like = "%" + term + "%";
                for (Map<String, Object> row : sql.rows(
                    "SELECT id, title, item_type, duration, skill, level, origin, site, jump_to, url FROM resource_item "
                        + "WHERE LOWER(title) LIKE ? OR LOWER(match_reason) LIKE ? ORDER BY sort_no LIMIT 6", like, like)) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", "resource-" + row.get("id"));
                    item.put("source", "推荐资源");
                    item.put("title", row.get("title"));
                    item.put("type", row.get("item_type"));
                    item.put("duration", row.get("duration"));
                    item.put("skill", row.get("skill"));
                    item.put("level", row.get("level"));
                    item.put("origin", row.get("origin"));
                    item.put("site", row.get("site"));
                    item.put("jump", row.get("jump_to"));
                    item.put("url", row.get("url"));
                    seen.putIfAbsent(String.valueOf(item.get("id")), item);
                }
                for (Map<String, Object> row : sql.rows(
                    "SELECT code, name, course_type, hours, skill, target_level FROM course "
                        + "WHERE LOWER(name) LIKE ? OR LOWER(skill) LIKE ? ORDER BY sort_no LIMIT 6", like, like)) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", "course-" + row.get("code"));
                    item.put("source", "课程库");
                    item.put("title", row.get("name"));
                    item.put("type", row.get("course_type"));
                    item.put("duration", row.get("hours") + " 小时");
                    item.put("skill", row.get("skill"));
                    item.put("level", "L" + row.get("target_level"));
                    item.put("origin", "站内");
                    item.put("site", "学习总版");
                    item.put("jump", "learning");
                    item.put("url", null);
                    seen.putIfAbsent(String.valueOf(item.get("id")), item);
                }
            }
            internal.addAll(seen.values());
        }
        // 热门检索词先给当前缺口技能，再按课程库顺序补齐，避免推与本人缺口无关的词。
        List<String> hotKeywords = new ArrayList<>();
        List<Map<String, Object>> catalog = sql.rows("SELECT skill, search_keyword FROM external_course ORDER BY sort_no");
        for (Map<String, Object> row : catalog) {
            String word = String.valueOf(row.get("search_keyword"));
            if (gapSkills.contains(String.valueOf(row.get("skill"))) && !hotKeywords.contains(word)) {
                hotKeywords.add(word);
            }
        }
        for (Map<String, Object> row : catalog) {
            if (hotKeywords.size() >= 6) {
                break;
            }
            String word = String.valueOf(row.get("search_keyword"));
            if (!hotKeywords.contains(word)) {
                hotKeywords.add(word);
            }
        }
        if (hotKeywords.size() > 6) {
            hotKeywords = new ArrayList<>(hotKeywords.subList(0, 6));
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("keyword", raw);
        result.put("platform", platform);
        result.put("skill", skill);
        result.put("level", level);
        result.put("searched_at", ZonedDateTime.now().format(STAMP));
        result.put("took_ms", System.currentTimeMillis() - startedAt);
        result.put("catalog_size", catalogSize);
        result.put("external_total", externalTotal);
        result.put("external", topExternal);
        result.put("internal", internal);
        result.put("platforms", platforms);
        result.put("gap_skills", gapSkills);
        result.put("hot_keywords", hotKeywords);
        result.put("checked_at", checkedAt);
        result.put("platform_ok", platformOk);
        result.put("platform_total", platformNames.size());
        result.put("note", "外网课程只收录公开平台的检索入口：每条点开都是该平台按「检索关键词」实时检索的结果页，在新窗口打开；"
            + "平台地址已于 " + checkedAt + " 核验（" + platformOk + "/" + platformNames.size() + " 返回 200）。");
        return result;
    }

    /** 当前技能缺口（level < required_level）：缺得越多排越前，用于外网课程与检索词的优选顺序。 */
    public List<String> gapSkills(String username) {
        List<String> skills = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill FROM employee_skill WHERE username = ? AND level < required_level "
                + "ORDER BY (required_level - level) DESC, sort_no", username)) {
            skills.add(String.valueOf(row.get("skill")));
        }
        return skills;
    }

    private static int intOf(Object value) {
        return value instanceof Number number ? number.intValue() : 0;
    }

    private static long longOf(Object value) {
        return value instanceof Number number ? number.longValue() : 0;
    }

    private static List<String> splitTags(String tags) {
        List<String> values = new ArrayList<>();
        for (String item : tags.split(",")) {
            if (!item.isBlank()) {
                values.add(item.trim());
            }
        }
        return values;
    }

    // ---- 任务 ----

    public List<Map<String, Object>> tasks(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT id, title, skill, planned_hours, actual_hours, status, due_at, requirement FROM task "
                + "WHERE username = ? ORDER BY sort_no", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("id"));
            item.put("title", row.get("title"));
            item.put("skill", row.get("skill"));
            item.put("planned_hours", row.get("planned_hours"));
            item.put("actual_hours", row.get("actual_hours"));
            item.put("status", row.get("status"));
            item.put("due_at", row.get("due_at"));
            item.put("requirement", row.get("requirement"));
            items.add(item);
        }
        return items;
    }

    public String taskTitle(long taskId) {
        Map<String, Object> row = sql.row("SELECT title FROM task WHERE id = ?", taskId);
        return row == null ? "实操任务" : String.valueOf(row.get("title"));
    }

    // ---- 记忆展示 / 成长轨迹 / 差距建议（展示数据集） ----

    /** 记忆展示：种子记忆与 Agent 实时写入的记忆同表，实时记忆（sort_no=0）排在最前。 */
    public Map<String, Object> memories(String username) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT memory_id, type, type_label, occurred_at, title, detail, tags, source, source_label FROM memory_item "
                + "WHERE username = ? ORDER BY sort_no, created_at DESC, memory_id", username)) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("memory_id", row.get("memory_id"));
            item.put("type", row.get("type"));
            item.put("type_label", row.get("type_label"));
            item.put("occurred_at", row.get("occurred_at"));
            item.put("title", row.get("title"));
            item.put("detail", row.get("detail"));
            item.put("tags", sql.parse(row.get("tags")));
            item.put("source", row.get("source"));
            item.put("source_label", row.get("source_label"));
            items.add(item);
        }
        long advice = items.stream().filter(item -> "ADVICE".equals(item.get("type"))).count();
        long exam = count(items, "EXAM");
        long practice = count(items, "PRACTICE");
        long mentor = count(items, "MENTOR");
        long safety = count(items, "SAFETY");
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total", items.size());
        summary.put("exam", exam);
        summary.put("practice", practice);
        summary.put("mentor", mentor);
        summary.put("safety", safety);
        summary.put("advice", advice);
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, Object> owner = identity(username);
        result.put("owner", owner == null ? "" : owner.get("display_name"));
        result.put("summary", summary);
        result.put("insight", datasets.meta("personal.memories.insight"));
        result.put("items", items);
        return result;
    }

    private static long count(List<Map<String, Object>> items, String type) {
        return items.stream().filter(item -> type.equals(item.get("type"))).count();
    }

    public Map<String, Object> selfPortrait() {
        return datasets.meta("personal.self-portrait");
    }

    public Map<String, Object> growth() {
        return datasets.meta("personal.growth");
    }

    public Map<String, Object> advice() {
        return datasets.meta("personal.advice");
    }

    /** 个性化 Agent 诊断的基线口径：结论内容取自库，接口只补诊断编号、时间与实时条数。 */
    public Map<String, Object> diagnosisCore() {
        return datasets.meta("personal.diagnosis.core");
    }

    public Map<String, Object> gaps() {
        return datasets.meta("personal.gaps");
    }

    // ---- 班组 ----

    public Map<String, Object> teamProfile() {
        return datasets.meta("team.profile");
    }

    /**
     * 班组实操报告：库里的种子台账 + 组长实时填报的报告（task_report）。
     * 台账行引用的报告若不在 task_report 中，就不再给出文档地址，避免下载链接指向不存在的报告（404）；
     * 同一报告编号只出现一行，实时报告不会和台账重复。
     */
    public List<Map<String, Object>> teamReports() {
        List<Map<String, Object>> items = new ArrayList<>(datasets.items("team.reports"));
        List<Map<String, Object>> live = sql.rows(
            "SELECT report_id, task_id, task_title, member, reporter, detected_at, judgment, severity, phenomenon, sop_status "
                + "FROM task_report ORDER BY submitted_at DESC");
        Set<String> stored = new LinkedHashSet<>();
        for (Map<String, Object> row : live) stored.add(String.valueOf(row.get("report_id")));
        Set<String> shown = new LinkedHashSet<>();
        for (Map<String, Object> item : items) {
            Object reportId = item.get("report_id");
            if (reportId != null && stored.contains(String.valueOf(reportId))) {
                // 台账行已挂真实报告：判定结论与严重度以报告本体为准，避免台账与下载的 PDF 对不上
                String id = String.valueOf(reportId);
                for (Map<String, Object> row : live) {
                    if (!id.equals(String.valueOf(row.get("report_id")))) continue;
                    item.put("judgment", row.get("judgment"));
                    item.put("severity", row.get("severity"));
                    item.put("sop_status", row.get("sop_status"));
                    break;
                }
                item.put("document_pdf", documentUrl(id));
                shown.add(id);
                continue;
            }
            // 缺报行：同一任务、同一执行组员已补交报告时自动销账，台账直接从“缺报”回到“已提交”
            Map<String, Object> matched = matchMissing(item, live, shown);
            if (matched == null) {
                item.remove("document_pdf");
                continue;
            }
            String id = String.valueOf(matched.get("report_id"));
            item.put("status", "SUBMITTED");
            item.put("report_id", id);
            item.put("judgment", matched.get("judgment"));
            item.put("severity", matched.get("severity"));
            item.put("sop_status", matched.get("sop_status"));
            item.put("summary", matched.get("phenomenon"));
            item.put("document_pdf", documentUrl(id));
            shown.add(id);
        }
        for (Map<String, Object> row : live) {
            String reportId = String.valueOf(row.get("report_id"));
            if (shown.contains(reportId)) continue;
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", "TR-LIVE-" + reportId);
            item.put("member", memberOf(row));
            item.put("reporter", row.get("reporter"));
            item.put("task_id", row.get("task_id"));
            item.put("task_title", row.get("task_title"));
            item.put("detected_at", row.get("detected_at"));
            item.put("status", "SUBMITTED");
            item.put("report_id", reportId);
            item.put("judgment", row.get("judgment"));
            item.put("severity", row.get("severity"));
            item.put("sop_status", row.get("sop_status"));
            item.put("summary", row.get("phenomenon"));
            item.put("document_pdf", documentUrl(reportId));
            items.add(item);
        }
        return items;
    }

    /** 缺报补交销账：按“任务 + 执行组员”找一份尚未挂到台账上的报告。 */
    private static Map<String, Object> matchMissing(Map<String, Object> item,
                                                    List<Map<String, Object>> live, Set<String> shown) {
        if (!"MISSING".equals(String.valueOf(item.get("status")))) {
            return null;
        }
        String member = Texts.text(item.get("member"));
        if (member.isEmpty()) {
            return null;
        }
        for (Map<String, Object> row : live) {
            String reportId = String.valueOf(row.get("report_id"));
            if (shown.contains(reportId)) continue;
            if (Texts.text(item.get("task_id")).equals(Texts.text(row.get("task_id"))) && member.equals(memberOf(row))) {
                return row;
            }
        }
        return null;
    }

    /** 执行组员：报告未单独记录组员时回退为填报人，保证台账不出现空白。 */
    private static String memberOf(Map<String, Object> row) {
        String member = Texts.text(row.get("member"));
        return member.isEmpty() || "null".equals(member) ? Texts.text(row.get("reporter")) : member;
    }

    private static String documentUrl(String reportId) {
        return "/api/v1/reports/" + reportId + "/document?format=pdf";
    }
}
