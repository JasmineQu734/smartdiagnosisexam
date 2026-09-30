package com.power.train.practice;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.persona.RuntimeMemoryStore;
import com.power.train.store.DatasetStore;
import com.power.train.store.Sql;
import com.power.train.support.Users;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 练习题模块：抽题会话、正确率统计与练习记录都存在 MySQL
 * （practice_session / practice_stat / practice_history），题目在 question 表；
 * 组长用 SOP 模板生成的题目写入同一张表，供普通员工抽题调用。
 */
@RestController
@RequestMapping("/api/v1")
public class PracticeController {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    public record DrawRequest(String skill, Integer count) {}

    public record SubmitRequest(String session_id, Map<String, String> answers) {}

    private final QuestionBank bank;
    private final RuntimeMemoryStore memoryStore;
    private final DatasetStore datasets;
    private final Sql sql;

    public PracticeController(QuestionBank bank, RuntimeMemoryStore memoryStore, DatasetStore datasets, Sql sql) {
        this.bank = bank;
        this.memoryStore = memoryStore;
        this.datasets = datasets;
        this.sql = sql;
    }

    /** 技能缺口权重与说明：取自 dataset_item（practice.gap-rules），抽题策略可在库里调整。 */
    private Map<String, Double> gapWeights() {
        Map<String, Double> weights = new LinkedHashMap<>();
        for (Map<String, Object> rule : datasets.items("practice.gap-rules")) {
            weights.put(String.valueOf(rule.get("skill")), ((Number) rule.getOrDefault("weight", 1.0)).doubleValue());
        }
        return weights;
    }

    private Map<String, String> gapReasons() {
        Map<String, String> reasons = new LinkedHashMap<>();
        for (Map<String, Object> rule : datasets.items("practice.gap-rules")) {
            reasons.put(String.valueOf(rule.get("skill")), String.valueOf(rule.getOrDefault("reason", "按缺口权重抽题")));
        }
        return reasons;
    }

    // ---- 员工：题库概览（含我的正确率与练习记录） ----

    @GetMapping("/personal/practice/overview")
    public Map<String, Object> overview(@RequestHeader(value = "X-User", required = false) String header) {
        String me = Users.account(header);
        return ok(row(
            "bank_total", bank.size(),
            "by_skill", bank.bySkill(),
            "my_accuracy", accuracyRows(me),
            "history", history(me, 5),
            "team_sources", bank.bySource().stream()
                .filter(item -> isTeamSource(String.valueOf(item.get("source")))).toList()));
    }

    // ---- 员工：Agent 按个人能力抽题 ----

    @PostMapping("/personal/practice/draw")
    public Map<String, Object> draw(@RequestBody(required = false) DrawRequest request,
                                    @RequestHeader(value = "X-User", required = false) String header) {
        String me = Users.account(header);
        String onlySkill = request == null ? null : request.skill();
        int count = request == null || request.count() == null ? 5 : Math.max(1, Math.min(15, request.count()));

        Map<String, Double> weights = gapWeights();
        Map<String, String> reasons = gapReasons();
        boolean picking = onlySkill != null && !onlySkill.isBlank();
        String defaultReason = picking ? "专项练习：抽该技能已入库的题目" : "按缺口权重抽题";
        List<String> skills = new ArrayList<>();
        if (picking) {
            // 专项练习：只要该技能在题库里有题就抽，不要求在缺口权重表（practice.gap-rules）里
            if (bank.countBySkill(onlySkill) > 0) skills.add(onlySkill);
        } else {
            for (String skill : weights.keySet()) {
                if (bank.countBySkill(skill) > 0) skills.add(skill);
            }
        }
        if (skills.isEmpty()) {
            return ok(row("questions", List.of(), "agent", row("note", "题库中暂无该技能的题目")));
        }

        Map<String, Double> effort = new LinkedHashMap<>();
        double totalEffort = 0;
        for (String skill : skills) {
            double weight = weights.getOrDefault(skill, 1.0);
            double score = Math.max(0.2, 1.6 - accuracyOf(me, skill));
            effort.put(skill, weight * score);
            totalEffort += weight * score;
        }
        skills.sort(Comparator.comparingDouble((String skill) -> -effort.get(skill)));

        Map<String, Integer> allocation = new LinkedHashMap<>();
        int remaining = count;
        for (int index = 0; index < skills.size() && remaining > 0; index++) {
            String skill = skills.get(index);
            int available = (int) bank.countBySkill(skill);
            int take = index == skills.size() - 1
                ? remaining
                : (int) Math.round(count * effort.get(skill) / totalEffort);
            take = Math.max(1, Math.min(Math.min(take, available), remaining));
            allocation.put(skill, take);
            remaining -= take;
        }

        List<QuestionBank.Question> picked = new ArrayList<>();
        List<Map<String, Object>> plan = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : allocation.entrySet()) {
            String skill = entry.getKey();
            List<QuestionBank.Question> pool = new ArrayList<>(bank.all().stream()
                .filter(item -> item.skill().equals(skill)).toList());
            pool.sort(Comparator.comparingInt(QuestionBank.Question::usedCount)
                .thenComparingInt(QuestionBank.Question::level));
            for (int i = 0; i < entry.getValue() && i < pool.size(); i++) {
                QuestionBank.Question question = pool.get(i);
                picked.add(question);
                bank.use(question.id());
            }
            plan.add(row("skill", skill, "count", entry.getValue(), "reason", reasons.getOrDefault(skill, defaultReason),
                "accuracy", Math.round(accuracyOf(me, skill) * 100) + "%"));
        }

        String sessionId = "PRC-" + String.format("%03d", (int) sql.count("SELECT COUNT(*) FROM practice_session") + 1)
            + "-" + UUID.randomUUID().toString().substring(0, 6);
        sql.update("INSERT INTO practice_session (session_id, username, skill, question_count, question_ids) "
                + "VALUES (?, ?, ?, ?, ?)",
            sessionId, me, onlySkill == null || onlySkill.isBlank() ? null : onlySkill, picked.size(),
            sql.json(picked.stream().map(QuestionBank.Question::id).toList()));

        StringBuilder note = new StringBuilder("本次按“技能缺口优先级 × 历史正确率”抽题 " + picked.size() + " 题（题库 " + bank.size() + " 题）：");
        for (int i = 0; i < plan.size(); i++) {
            Map<String, Object> item = plan.get(i);
            note.append(i > 0 ? "；" : "").append(item.get("skill")).append(" ").append(item.get("count")).append(" 题（")
                .append("当前正确率 ").append(item.get("accuracy")).append("）");
        }
        note.append("。答错的题目会自动写入能力记忆库，供 Agent 下次调整抽题。");

        return ok(row(
            "session_id", sessionId,
            "count", picked.size(),
            "bank_total", bank.size(),
            "agent", row("strategy", "缺口权重 × (1.6 - 历史正确率) 分配题量，逐技能按使用次数与等级取题", "plan", plan,
                "note", note.toString()),
            "questions", picked.stream().map(item -> item.toView(false)).toList()));
    }
    // ---- 员工：提交作答，判分并回写记忆 ----

    @PostMapping("/personal/practice/submit")
    public Map<String, Object> submit(@RequestBody SubmitRequest request) {
        String sessionId = request == null ? null : request.session_id();
        Map<String, Object> session = sessionId == null ? null
            : sql.row("SELECT session_id, username, skill, question_ids FROM practice_session WHERE session_id = ?", sessionId);
        if (session == null) {
            return row("code", 40004, "message", "练习会话不存在或已过期，请重新抽题",
                "data", null, "trace_id", UUID.randomUUID().toString());
        }
        String me = String.valueOf(session.get("username"));
        String sessionSkill = session.get("skill") == null ? "" : String.valueOf(session.get("skill"));
        Map<String, String> answers = request.answers() == null ? Map.of() : request.answers();
        List<Map<String, Object>> items = new ArrayList<>();
        int correct = 0;
        List<String> wrongSkills = new ArrayList<>();
        for (String questionId : sql.parseStrings(session.get("question_ids"))) {
            QuestionBank.Question question = bank.byId(questionId);
            if (question == null) continue;
            String mine = answers.getOrDefault(questionId, "");
            boolean isRight = question.answer().equalsIgnoreCase(mine.trim());
            if (isRight) correct++;
            else if (!wrongSkills.contains(question.skill())) wrongSkills.add(question.skill());
            record(me, question.skill(), isRight);
            items.add(row("id", question.id(), "skill", question.skill(), "level", question.level(), "type", question.type(),
                "stem", question.stem(), "your_answer", mine.isBlank() ? "未作答" : mine,
                "correct_answer", question.answer(), "correct", isRight, "explanation", question.explanation()));
        }
        int score = items.isEmpty() ? 0 : (int) Math.round(correct * 100.0 / items.size());
        String ranAt = ZonedDateTime.now().format(STAMP);
        String memoryTitle;
        if (wrongSkills.isEmpty()) {
            memoryTitle = "练习题全部答对（" + correct + "/" + items.size() + "）";
            memoryStore.addAdvice(me, "练习记录：" + memoryTitle, "本次练习全部正确，Agent 会相应降低该技能的抽题权重。",
                List.of("练习题", "全对"), "学习总版", ranAt);
        } else {
            memoryTitle = "练习题错题：" + String.join("、", wrongSkills);
            memoryStore.add(me, "ERROR", "错误记忆", "练习错题：" + String.join("、", wrongSkills),
                "本次练习 " + items.size() + " 题答对 " + correct + " 题（得分 " + score + "），错题集中在 "
                    + String.join("、", wrongSkills) + "，解析与正确答案已随练习结果返回。",
                List.of("练习题", "错题", String.join("、", wrongSkills)), "学习总版", ranAt);
        }
        String source = sessionSkill.isBlank() ? "全技能抽题" : sessionSkill + " 专项";
        sql.update("INSERT INTO practice_history (username, ran_at, score, correct, total, source) VALUES (?, ?, ?, ?, ?, ?)",
            me, ranAt, score, correct, items.size(), source);

        return ok(row(
            "ran_at", ranAt, "score", score, "correct", correct, "total", items.size(),
            "wrong_skills", wrongSkills,
            "my_accuracy", accuracyRows(me),
            "memory_written", row("type", wrongSkills.isEmpty() ? "ADVICE" : "ERROR", "title", memoryTitle,
                "note", "已写入记忆展示板块，Agent 下次抽题会参考本次结果"),
            "items", items));
    }

    /** 班组上传资料来源：SOP 生成与文档导入的题在员工端标注同一类出处。 */
    private static boolean isTeamSource(String source) {
        return source.startsWith("SOP") || source.startsWith("文档导入");
    }

    /** 判分结果累加到 practice_stat（每人每技能一行）。 */
    private void record(String username, String skill, boolean isRight) {
        sql.update("INSERT INTO practice_stat (username, skill, answered, correct) VALUES (?, ?, 1, ?) "
                + "ON DUPLICATE KEY UPDATE answered = answered + 1, correct = correct + ?",
            username, skill, isRight ? 1 : 0, isRight ? 1 : 0);
    }

    private List<Map<String, Object>> accuracyRows(String username) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, answered, correct FROM practice_stat WHERE username = ? ORDER BY answered DESC, skill",
            username)) {
            long answered = ((Number) row.getOrDefault("answered", 0)).longValue();
            long correct = ((Number) row.getOrDefault("correct", 0)).longValue();
            rows.add(row("skill", row.get("skill"), "answered", answered, "correct", correct,
                "rate", answered == 0 ? 0 : Math.round(correct * 100.0 / answered)));
        }
        return rows;
    }

    private List<Map<String, Object>> history(String username, int limit) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT ran_at, score, correct, total, source FROM practice_history WHERE username = ? "
                + "ORDER BY id DESC LIMIT ?", username, limit)) {
            rows.add(row("ran_at", row.get("ran_at"), "score", row.get("score"), "correct", row.get("correct"),
                "total", row.get("total"), "source", row.get("source")));
        }
        return rows;
    }

    private double accuracyOf(String username, String skill) {
        Map<String, Object> row = sql.row(
            "SELECT answered, correct FROM practice_stat WHERE username = ? AND skill = ?", username, skill);
        if (row == null || ((Number) row.getOrDefault("answered", 0)).intValue() == 0) return 0.7;
        double answered = ((Number) row.get("answered")).doubleValue();
        double correct = ((Number) row.get("correct")).doubleValue();
        return Math.min(1.0, Math.max(0.0, correct / answered));
    }

}
