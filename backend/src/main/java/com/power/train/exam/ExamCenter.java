package com.power.train.exam;

import static com.power.train.support.ApiResponse.row;

import com.power.train.persona.RuntimeMemoryStore;
import com.power.train.practice.QuestionBank;
import com.power.train.store.Sql;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

/**
 * 考试中心：管理员「统一开考」与员工「进入考试 / 交卷判分」共用 MySQL 里的同一份状态
 * （exam 定义 + exam_round 本轮状态 + exam_history 历史成绩），保证只有管理员开考后员工才能答题。
 */
@Service
public class ExamCenter {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final Sql sql;
    private final QuestionBank bank;
    private final RuntimeMemoryStore memoryStore;

    public ExamCenter(Sql sql, QuestionBank bank, RuntimeMemoryStore memoryStore) {
        this.sql = sql;
        this.bank = bank;
        this.memoryStore = memoryStore;
    }

    // ---- 管理员：清单与统一开考 ----

    public List<Map<String, Object>> list() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT * FROM exam ORDER BY sort_no, exam_id")) {
            Map<String, Object> item = view(row);
            String id = String.valueOf(item.get("exam_id"));
            item.put("available_questions", drawPool(String.valueOf(item.get("skill"))).size());
            item.put("entered", enteredCount(id));
            item.put("submitted", submittedCount(id));
            items.add(item);
        }
        return items;
    }

    public Map<String, Object> find(String examId) {
        Map<String, Object> row = sql.row("SELECT * FROM exam WHERE exam_id = ?", examId);
        return row == null ? null : view(row);
    }

    private Map<String, Object> view(Map<String, Object> row) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("exam_id", row.get("exam_id"));
        item.put("name", row.get("name"));
        item.put("exam_type", row.get("exam_type"));
        item.put("skill", row.get("skill"));
        item.put("pass_score", row.get("pass_score"));
        item.put("question_count", row.get("question_count"));
        item.put("duration_minutes", row.get("duration_minutes"));
        item.put("bank", row.get("bank"));
        item.put("scope", row.get("scope"));
        item.put("participants", row.get("participants"));
        item.put("enabled", sql.bool(row.get("enabled")));
        item.put("status", row.get("status"));
        item.put("started_at", row.get("started_at"));
        item.put("started_by", row.get("started_by"));
        if (row.get("ended_at") != null) {
            item.put("ended_at", row.get("ended_at"));
        }
        item.put("paper_batches", row.get("paper_batches"));
        return item;
    }

    /** 统一开考：把该场考试置为「进行中」，员工端随即出现可进入的考试；开考人记当前登录管理员。 */
    public Map<String, Object> start(String examId, String startedBy) {
        Map<String, Object> exam = find(examId);
        if (exam == null) {
            return row("started", false, "message", "考试不存在：" + examId);
        }
        if (!Boolean.TRUE.equals(exam.get("enabled"))) {
            return row("started", false, "message", "考试「" + exam.get("name") + "」未启用，请先在考试配置中启用");
        }
        if ("进行中".equals(exam.get("status"))) {
            return row("started", false, "message", "考试已在进行中（开始时间 " + exam.get("started_at") + "）",
                "exam_id", examId, "status", "进行中", "started_at", exam.get("started_at"));
        }
        String at = ZonedDateTime.now().format(STAMP);
        String operator = startedBy == null || startedBy.isBlank() ? "系统管理员" : startedBy;
        sql.update("DELETE FROM exam_round WHERE exam_id = ?", examId);
        sql.update("UPDATE exam SET status = '进行中', started_at = ?, started_by = ?, ended_at = NULL WHERE exam_id = ?",
            at, operator, examId);
        return row("started", true, "exam_id", examId, "name", exam.get("name"), "status", "进行中", "started_at", at,
            "started_by", operator, "scope", exam.get("scope"), "participants", exam.get("participants"),
            "available_questions",
            drawPool(String.valueOf(exam.get("skill"))).size(),
            "message", "已统一开考，参考人员可进入考试");
    }

    /** 结束本场：置为「已结束」并清空本轮作答记录，员工端随即不再出现「进入考试」。 */
    public Map<String, Object> close(String examId) {
        Map<String, Object> exam = find(examId);
        if (exam == null) {
            return row("closed", false, "message", "考试不存在：" + examId);
        }
        if (!"进行中".equals(exam.get("status"))) {
            return row("closed", false, "exam_id", examId, "name", exam.get("name"), "status", exam.get("status"),
                "message", "考试「" + exam.get("name") + "」当前不是进行中，无需结束");
        }
        int entered = enteredCount(examId);
        int submitted = submittedCount(examId);
        String at = ZonedDateTime.now().format(STAMP);
        sql.update("UPDATE exam SET status = '已结束', ended_at = ? WHERE exam_id = ?", at, examId);
        sql.update("DELETE FROM exam_round WHERE exam_id = ?", examId);
        return row("closed", true, "exam_id", examId, "name", exam.get("name"), "status", "已结束", "ended_at", at,
            "entered", entered, "submitted", submitted,
            "message", "已结束本场考试：进入 " + entered + " 人 · 交卷 " + submitted + " 人；再次开考将开启新一轮并重新发卷");
    }

    public int bumpPaper(String examId) {
        Map<String, Object> row = sql.row("SELECT paper_batches FROM exam WHERE exam_id = ?", examId);
        if (row == null) {
            return 0;
        }
        int next = ((Number) row.getOrDefault("paper_batches", 0)).intValue() + 1;
        sql.update("UPDATE exam SET paper_batches = ? WHERE exam_id = ?", next, examId);
        return next;
    }

    public long ongoingCount() {
        return sql.count("SELECT COUNT(*) FROM exam WHERE status = '进行中'");
    }

    public int enteredCount(String examId) {
        return (int) sql.count("SELECT COUNT(*) FROM exam_round WHERE exam_id = ?", examId);
    }

    public int submittedCount(String examId) {
        return (int) sql.count("SELECT COUNT(*) FROM exam_round WHERE exam_id = ? AND status = 'SUBMITTED'", examId);
    }

    // ---- 员工：进入考试 ----

    /** 员工进入考试：只有管理员开考（进行中）后才发卷；已交卷的本场考试不重复发卷。 */
    public Map<String, Object> enter(String examId, String user) {
        Map<String, Object> exam = find(examId);
        if (exam == null) {
            return row("opened", false, "gate", "NOT_FOUND", "message", "考试不存在：" + examId);
        }
        if (!"进行中".equals(exam.get("status"))) {
            return row("opened", false, "gate", "NOT_OPEN", "exam_id", examId, "name", exam.get("name"),
                "message", "管理员尚未统一开考「" + exam.get("name") + "」，请等待开考通知后再进入。");
        }
        Map<String, Object> mine = sql.row("SELECT * FROM exam_round WHERE username = ? AND exam_id = ?", user, examId);
        if (mine != null && "SUBMITTED".equals(mine.get("status"))) {
            return row("opened", false, "gate", "SUBMITTED", "exam_id", examId, "name", exam.get("name"),
                "record", recordView(mine),
                "message", "本场考试已交卷（" + mine.get("score") + " 分），如需重考请等管理员重新开考。");
        }
        if (mine == null) {
            List<QuestionBank.Question> picked = draw(String.valueOf(exam.get("skill")),
                ((Number) exam.get("question_count")).intValue());
            List<String> ids = new ArrayList<>();
            for (QuestionBank.Question question : picked) {
                ids.add(question.id());
            }
            String sessionId = "EXAM-" + examId + "-" + user + "-" + System.nanoTime() % 100000;
            String startedAt = ZonedDateTime.now().format(STAMP);
            sql.update("INSERT INTO exam_round (username, exam_id, status, question_ids, session_id, started_at, total) "
                    + "VALUES (?, ?, 'IN_PROGRESS', ?, ?, ?, ?)",
                user, examId, sql.json(ids), sessionId, startedAt, picked.size());
            mine = sql.row("SELECT * FROM exam_round WHERE username = ? AND exam_id = ?", user, examId);
        }
        return row(
            "opened", true, "gate", "IN_PROGRESS",
            "exam_id", examId, "name", exam.get("name"), "exam_type", exam.get("exam_type"),
            "pass_score", exam.get("pass_score"), "duration_minutes", exam.get("duration_minutes"),
            "question_count", mine.get("total"), "configured_count", exam.get("question_count"),
            "started_at", mine.get("started_at"), "session_id", mine.get("session_id"),
            "questions", questions(mine),
            "note", "本场由管理员统一开考（开考时间 " + exam.get("started_at") + "）；交卷后立即出分并给出错题解析。");
    }

    // ---- 员工：交卷判分 ----

    public Map<String, Object> submit(String examId, String user, Map<String, String> answers) {
        Map<String, Object> exam = find(examId);
        if (exam == null) {
            return row("submitted", false, "message", "考试不存在：" + examId);
        }
        Map<String, Object> mine = sql.row("SELECT * FROM exam_round WHERE username = ? AND exam_id = ?", user, examId);
        if (mine == null) {
            return row("submitted", false, "message", "尚未进入本场考试，请先点「进入考试」再交卷。");
        }
        if ("SUBMITTED".equals(mine.get("status"))) {
            return row("submitted", true, "already", true, "record", recordView(mine),
                "message", "本场考试已交卷，成绩 " + mine.get("score") + " 分。");
        }
        List<QuestionBank.Question> questions = questionsOf(mine);
        int correct = 0;
        List<Map<String, Object>> details = new ArrayList<>();
        List<String> wrongPoints = new ArrayList<>();
        for (QuestionBank.Question question : questions) {
            String mineAnswer = String.valueOf(answers.getOrDefault(question.id(), "")).trim();
            boolean right = question.answer().equalsIgnoreCase(mineAnswer);
            if (right) {
                correct++;
            } else if (!wrongPoints.contains(question.skill())) {
                wrongPoints.add(question.skill());
            }
            details.add(row("id", question.id(), "skill", question.skill(), "level", question.level(),
                "type", question.type(), "stem", question.stem(), "options", question.options(),
                "my_answer", mineAnswer, "answer", question.answer(), "right", right,
                "explanation", question.explanation(), "source", question.source()));
        }
        int total = questions.isEmpty() ? 1 : questions.size();
        int score = Math.round(correct * 100f / total);
        int passScore = ((Number) exam.get("pass_score")).intValue();
        boolean passed = score >= passScore;
        String at = ZonedDateTime.now().format(STAMP);
        sql.update("UPDATE exam_round SET status = 'SUBMITTED', score = ?, correct = ?, total = ?, result = ?, "
                + "submitted_at = ?, wrong_points = ? WHERE username = ? AND exam_id = ?",
            score, correct, questions.size(), passed ? "PASSED" : "FAILED", at, sql.json(wrongPoints), user, examId);
        sql.update("INSERT INTO exam_history (username, exam_id, exam_name, score, pass_score, result, submitted_at, "
                + "wrong_points) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            user, examId, exam.get("name"), score, passScore, passed ? "PASSED" : "FAILED", at, sql.json(wrongPoints));
        memoryStore.add(user, "EXAM", "考试记忆",
            "「" + exam.get("name") + "」交卷 " + score + " 分（合格线 " + passScore + "）",
            passed
                ? "答对 " + correct + "/" + questions.size() + " 题，已通过；成绩与解析已写入考试中心。"
                : "答对 " + correct + "/" + questions.size() + " 题，未通过；错题集中在「"
                    + String.join("、", wrongPoints) + "」，建议先补课再等下一场开考补考。",
            wrongPoints.isEmpty() ? List.of(String.valueOf(exam.get("exam_type"))) : wrongPoints,
            "考试中心", at);
        return row("submitted", true, "already", false,
            "exam_id", examId, "name", exam.get("name"), "score", score, "pass_score", passScore,
            "passed", passed, "result", passed ? "PASSED" : "FAILED", "correct", correct, "total", questions.size(),
            "wrong_points", wrongPoints, "submitted_at", at, "details", details,
            "message", passed ? "已交卷：得分 " + score + " 分，通过（合格线 " + passScore + "）"
                : "已交卷：得分 " + score + " 分，未达合格线 " + passScore + " 分，错题解析见下");
    }

    /** 员工本人的考试记录（本轮 + 历史），用于考试中心列表。 */
    public List<Map<String, Object>> recordsFor(String user) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> item : sql.rows("SELECT * FROM exam_round WHERE username = ?", user)) {
            rows.add(recordView(item));
        }
        for (Map<String, Object> item : sql.rows(
            "SELECT exam_id, exam_name, score, pass_score, result, submitted_at, wrong_points FROM exam_history "
                + "WHERE username = ? ORDER BY id DESC", user)) {
            Map<String, Object> record = new LinkedHashMap<>();
            record.put("exam_id", item.get("exam_id"));
            record.put("user", user);
            record.put("score", item.get("score"));
            record.put("pass_score", item.get("pass_score"));
            record.put("result", item.get("result"));
            record.put("submitted_at", item.get("submitted_at"));
            record.put("wrong_points", sql.parse(item.get("wrong_points")));
            record.put("exam_name", item.get("exam_name"));
            rows.add(record);
        }
        return rows;
    }

    private Map<String, Object> recordView(Map<String, Object> mine) {
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("exam_id", mine.get("exam_id"));
        view.put("status", mine.get("status"));
        view.put("result", mine.getOrDefault("result", "IN_PROGRESS"));
        view.put("score", mine.get("score"));
        view.put("correct", mine.get("correct"));
        view.put("total", mine.get("total"));
        view.put("submitted_at", mine.get("submitted_at"));
        view.put("wrong_points", sql.parse(mine.get("wrong_points")) == null ? List.of() : sql.parse(mine.get("wrong_points")));
        view.put("started_at", mine.get("started_at"));
        return view;
    }

    private List<Map<String, Object>> questions(Map<String, Object> mine) {
        List<Map<String, Object>> views = new ArrayList<>();
        for (QuestionBank.Question question : questionsOf(mine)) {
            views.add(question.toView(false));
        }
        return views;
    }

    private List<QuestionBank.Question> questionsOf(Map<String, Object> mine) {
        List<QuestionBank.Question> picked = new ArrayList<>();
        for (Object id : sql.parseList(mine.get("question_ids"))) {
            QuestionBank.Question question = bank.byId(String.valueOf(id));
            if (question != null) {
                picked.add(question);
            }
        }
        return picked;
    }

    /** 该场考试题库范围内可抽的全部题目（按等级与题号稳定排序）。 */
    private List<QuestionBank.Question> drawPool(String skill) {
        List<QuestionBank.Question> pool = new ArrayList<>();
        for (QuestionBank.Question question : bank.all()) {
            if (question.skill().equals(skill)) {
                pool.add(question);
            }
        }
        pool.sort(Comparator.comparingInt(QuestionBank.Question::level).thenComparing(QuestionBank.Question::id));
        return pool;
    }

    /** 组卷：按配置题量取题；题库不足时按实际题量发卷并在提示里说明。 */
    private List<QuestionBank.Question> draw(String skill, int configured) {
        List<QuestionBank.Question> pool = drawPool(skill);
        List<QuestionBank.Question> picked = new ArrayList<>();
        for (int i = 0; i < pool.size() && i < configured; i++) {
            picked.add(pool.get(i));
        }
        return picked;
    }
}
