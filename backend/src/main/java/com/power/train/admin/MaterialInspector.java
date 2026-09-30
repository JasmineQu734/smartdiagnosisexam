package com.power.train.admin;

import static com.power.train.support.ApiResponse.row;

import com.power.train.store.Sql;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * 上传资料的 Agent 检索结果（演示实现）：把上传文件解析成「题目 + 答案 + 解析」或「知识章节」。
 * 知识点池取自 MySQL 的 knowledge_point 表；检索只做整理，管理员在待审核弹窗里逐条核对后点「确认入库」，
 * 才写入课程库 / 题库。
 */
@Component
class MaterialInspector {

    /** 弹窗最多列出的行数，超出部分只给总数提示。 */
    private static final int MAX_LISTED = 10;
    private static final String[] LETTER = {"A", "B", "C", "D"};
    /** 同一知识点在长文档里会出现多道题，用不同问法区分，避免重复条目看起来一样。 */
    private static final String[] STEM_CHOICE = {
        "关于「{p}」，下列说法正确的是？",
        "在「{p}」作业中，下列做法正确的是？",
        "依据规程，「{p}」应当满足下列哪项要求？",
        "现场执行「{p}」时，下列表述正确的是？"};
    private static final String[] STEM_JUDGE = {
        "判断正误：「{p}」的要点是 —— {s}",
        "判断正误（现场口述稿）：「{p}」的要求是 —— {s}",
        "判断：下列关于「{p}」的表述是否正确 —— {s}",
        "判断正误（案例分析）：「{p}」的做法是 —— {s}"};

    private final Sql sql;

    MaterialInspector(Sql sql) {
        this.sql = sql;
    }

    /** 题库资料：Agent 检索出的题目，答案与解析跟题目一一对应。 */
    List<Map<String, Object>> questions(Map<String, Object> material, int total) {
        List<String[]> pool = pool(String.valueOf(material.get("skill")));
        int offset = Math.floorMod(String.valueOf(material.get("file_name")).hashCode(), pool.size());
        int listed = Math.min(Math.max(total, 0), MAX_LISTED);
        String difficulty = difficulty(String.valueOf(material.get("target_level")));
        List<Map<String, Object>> items = new ArrayList<>();
        for (int i = 0; i < listed; i++) {
            int cycle = i / pool.size();
            int base = (i + offset + cycle) % pool.size();
            String[] current = pool.get(base);
            String[] forward = pool.get((base + 1) % pool.size());
            String[] second = pool.get((base + 2) % pool.size());
            String[] third = pool.get((base + 3) % pool.size());
            if (i % 4 == 3) {
                boolean right = (i / 4) % 2 == 0;
                String shown = right ? current[1] : forward[1];
                String answer = right ? "A" : "B";
                String analysis = right
                    ? "「" + current[0] + "」的要点确为：" + current[1] + "。"
                    : "题干把「" + forward[0] + "」的要点写成了「" + current[0] + "」的要求：" + forward[1]
                        + "。本题考点「" + current[0] + "」的正确表述是：" + current[1] + "。";
                items.add(row(
                    "index", i + 1, "type", "判断题", "knowledge", current[0],
                    "question", STEM_JUDGE[cycle % STEM_JUDGE.length].replace("{p}", current[0]).replace("{s}", shown),
                    "options", List.of("A. 正确", "B. 错误"),
                    "answer", answer, "answer_text", answer + ". " + (right ? "正确" : "错误"),
                    "analysis", analysis, "difficulty", difficulty, "source_page", sourcePage(i, material)));
            } else {
                int correct = (i + cycle) % 4;
                String[] distractors = {forward[1], second[1], third[1]};
                List<String> options = new ArrayList<>();
                int cursor = 0;
                for (int slot = 0; slot < 4; slot++) {
                    options.add(LETTER[slot] + ". " + (slot == correct ? current[1] : distractors[cursor++]));
                }
                items.add(row(
                    "index", i + 1, "type", "单选题", "knowledge", current[0],
                    "question", STEM_CHOICE[cycle % STEM_CHOICE.length].replace("{p}", current[0]),
                    "options", options,
                    "answer", LETTER[correct], "answer_text", LETTER[correct] + ". " + current[1],
                    "analysis", "「" + current[0] + "」的正确表述是：" + current[1] + "。其余三个选项分别描述「"
                        + forward[0] + "」「" + second[0] + "」「" + third[0] + "」，与本题考点不符。",
                    "difficulty", difficulty, "source_page", sourcePage(i, material)));
            }
        }
        return items;
    }
    /** 课程资料：Agent 整理出的知识章节。 */
    List<Map<String, Object>> chapters(Map<String, Object> material, int total) {
        List<String[]> pool = pool(String.valueOf(material.get("skill")));
        int offset = Math.floorMod(String.valueOf(material.get("file_name")).hashCode(), pool.size());
        int listed = Math.min(Math.max(total, 0), MAX_LISTED);
        List<Map<String, Object>> items = new ArrayList<>();
        for (int i = 0; i < listed; i++) {
            String[] current = pool.get((i + offset) % pool.size());
            double hours = switch (i % 3) {
                case 0 -> 1.0;
                case 1 -> 1.5;
                default -> 2.0;
            };
            int part = i / pool.size();
            items.add(row(
                "index", i + 1, "chapter", "第" + (i + 1) + "章 " + current[0] + (part == 0 ? "" : "（进阶 " + (part + 1) + "）"),
                "points", current[1], "hours", hours, "source_page", sourcePage(i, material)));
        }
        return items;
    }

    /** 原件正文摘录：管理员用来自查 Agent 是否理解正确，入库后保留原文出处。 */
    List<String> excerpt(Map<String, Object> material) {
        List<String[]> pool = pool(String.valueOf(material.get("skill")));
        int offset = Math.floorMod(String.valueOf(material.get("file_name")).hashCode(), pool.size());
        String[] first = pool.get(offset % pool.size());
        String[] next = pool.get((offset + 1) % pool.size());
        String skill = String.valueOf(material.get("skill"));
        String level = String.valueOf(material.get("target_level"));
        return List.of(
            "适用范围：本资料（" + material.get("file_name") + "）用于「" + skill + "」岗位 " + level
                + " 级培训，原件 " + pages(material) + " 页 / " + sizeKb(material) + " KB，由 "
                + material.get("submitted_by") + " 于 " + material.get("submitted_at") + " 提交。",
            "编制依据：《电力安全工作规程》与本单位《" + skill + "作业指导书》，文档编号 "
                + material.get("skill_code") + "-ZD-" + material.get("version") + "。",
            "第1章摘录 · " + first[0] + "：" + first[1] + "。",
            "第2章摘录 · " + next[0] + "：" + next[1] + "。",
            "修订记录：本版（" + material.get("version") + "）由" + skill
                + "专业组复核，入库前请确认等级 " + level + " 与现行岗位技能要求一致。");
    }

    /** 原件体积（KB，演示值，按文件名稳定生成）。 */
    static int sizeKb(Map<String, Object> material) {
        return 240 + Math.floorMod(String.valueOf(material.get("file_name")).hashCode(), 1800);
    }

    /** 原件页数（演示值，按文件名稳定生成）。 */
    static int pages(Map<String, Object> material) {
        return 6 + Math.floorMod(String.valueOf(material.get("file_name")).hashCode(), 24);
    }

    /** 资料等级 → 练习题等级数字（L1-L3；「合格」等非数字等级按 L2 处理，与抽题口径一致）。 */
    static int levelOf(String level) {
        if (level == null) {
            return 2;
        }
        String digits = level.replaceAll("[^0-9]", "");
        return digits.isEmpty() ? 2 : Math.min(3, Math.max(1, Integer.parseInt(digits)));
    }

    private static String sourcePage(int index, Map<String, Object> material) {
        int page = 2 + Math.floorMod(index * 3, Math.max(pages(material) - 3, 1));
        return "原件第 " + page + " 页 · 第 " + (index % 5 + 1) + " 段";
    }

    private static String difficulty(String level) {
        return switch (level) {
            case "L1" -> "初级";
            case "L3" -> "高级";
            case "合格" -> "准入";
            default -> "中级";
        };
    }
    /** 每项技能的知识点池：[知识点, 要点表述]。内容存放在 MySQL 的 knowledge_point 表，按 sort_no 取用。 */
    private List<String[]> pool(String skill) {
        List<String[]> pool = new ArrayList<>();
        collect(pool, skill);
        if (pool.isEmpty()) {
            collect(pool, "通用");
        }
        return pool;
    }

    private void collect(List<String[]> pool, String skill) {
        for (Map<String, Object> row : sql.rows(
            "SELECT point, statement FROM knowledge_point WHERE skill = ? ORDER BY sort_no, id", skill)) {
            pool.add(new String[] {String.valueOf(row.get("point")), String.valueOf(row.get("statement"))});
        }
    }
}
