package com.power.train.practice;

import com.power.train.store.Sql;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 岗位练习题题库：数据存放在 MySQL 的 question 表。
 * 内置题目、管理员审核入库的题目与组长用 SOP 生成的题目共用同一张表，普通员工抽题时统一调用。
 */
@Component
public class QuestionBank {

    /** 一道练习题：题干、选项、标准答案与解析一一对应。 */
    public record Question(String id, String skill, int level, String type, String stem,
                           List<String> options, String answer, String explanation, String source, int usedCount) {
        public Map<String, Object> toView(boolean withAnswer) {
            Map<String, Object> view = new LinkedHashMap<>();
            view.put("id", id);
            view.put("skill", skill);
            view.put("level", level);
            view.put("type", type);
            view.put("stem", stem);
            view.put("options", options);
            view.put("source", source);
            if (withAnswer) {
                view.put("answer", answer);
                view.put("explanation", explanation);
            }
            return view;
        }
    }

    private final Sql sql;

    public QuestionBank(Sql sql) {
        this.sql = sql;
    }

    public List<Question> all() {
        List<Question> questions = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT id, skill, level, qtype, stem, options, answer, explanation, source, used_count FROM question "
                + "ORDER BY sort_no, id")) {
            questions.add(toQuestion(row));
        }
        return questions;
    }

    private Question toQuestion(Map<String, Object> row) {
        List<String> options = new ArrayList<>();
        for (Object item : sql.parseList(row.get("options"))) {
            options.add(String.valueOf(item));
        }
        return new Question(
            String.valueOf(row.get("id")),
            String.valueOf(row.get("skill")),
            row.get("level") == null ? 1 : ((Number) row.get("level")).intValue(),
            String.valueOf(row.get("qtype")),
            String.valueOf(row.get("stem")),
            options,
            String.valueOf(row.get("answer")),
            row.get("explanation") == null ? "" : String.valueOf(row.get("explanation")),
            String.valueOf(row.get("source")),
            row.get("used_count") == null ? 0 : ((Number) row.get("used_count")).intValue());
    }

    public int size() {
        return (int) sql.count("SELECT COUNT(*) FROM question");
    }

    public Question byId(String id) {
        Map<String, Object> row = sql.row(
            "SELECT id, skill, level, qtype, stem, options, answer, explanation, source, used_count FROM question "
                + "WHERE id = ?", id);
        return row == null ? null : toQuestion(row);
    }

    public long countBySkill(String skill) {
        return sql.count("SELECT COUNT(*) FROM question WHERE skill = ?", skill);
    }

    /** 题目被抽中的次数：抽题时按「用得少的优先」排，保证题目轮换。 */
    public int usedCount(String id) {
        Map<String, Object> row = sql.row("SELECT used_count FROM question WHERE id = ?", id);
        return row == null || row.get("used_count") == null ? 0 : ((Number) row.get("used_count")).intValue();
    }

    /** 抽中一次就在库里累加使用次数。 */
    public void use(String id) {
        sql.update("UPDATE question SET used_count = used_count + 1 WHERE id = ?", id);
    }

    /** 按技能统计题量，用于前端展示题库规模与配套练习入口。 */
    public List<Map<String, Object>> bySkill() {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT skill, COUNT(*) AS count FROM question GROUP BY skill ORDER BY count DESC, skill")) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("skill", row.get("skill"));
            item.put("count", row.get("count"));
            rows.add(item);
        }
        return rows;
    }

    /** 题目来源分布，便于说明「SOP 生成的题目已入库」。 */
    public List<Map<String, Object>> bySource() {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT source, COUNT(*) AS count FROM question GROUP BY source ORDER BY count DESC, source")) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source", row.get("source"));
            item.put("count", row.get("count"));
            rows.add(item);
        }
        return rows;
    }

    /** 组长用 SOP 生成的题目写入题库，普通员工抽题时即可调用。 */
    public Question add(String skill, int level, String type, String stem, List<String> options,
                        String answer, String explanation, String source) {
        String id = nextId();
        sql.update("INSERT INTO question (id, skill, level, qtype, stem, options, answer, explanation, source, sort_no) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            id, skill, level, type, stem, sql.json(options), answer, explanation, source,
            1000 + (int) sql.count("SELECT COUNT(*) FROM question WHERE source LIKE 'SOP%'"));
        return new Question(id, skill, level, type, stem, options, answer, explanation, source, 0);
    }

    private String nextId() {
        int sequence = 1001 + (int) sql.count("SELECT COUNT(*) FROM question WHERE id LIKE 'QB-%'");
        String id = "QB-" + String.format("%04d", sequence);
        while (sql.count("SELECT COUNT(*) FROM question WHERE id = ?", id) > 0) {
            sequence++;
            id = "QB-" + String.format("%04d", sequence);
        }
        return id;
    }
}
