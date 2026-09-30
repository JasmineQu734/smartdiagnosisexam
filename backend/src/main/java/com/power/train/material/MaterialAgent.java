package com.power.train.material;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/**
 * 资料出题 Agent（规则引擎）：读原件正文，识别出「题干 + 选项 + 答案 + 解析」的候选题，或整理出知识章节。
 * 两条识别路径都基于真实读到的正文：
 * 1）文档本身就是试题 / 题库（有题干、选项、答案行）→ 按题面结构逐题提取，答案与解析一一对应；
 * 2）文档是规程 / 作业指导书（条款式正文）→ 按「应 / 必须 / 不得 / 严禁」这类条款句出判断题与单选题，
 *    干扰项取自同一文档的其他条款，解析里写清出处，管理员能逐条对着原文核对。
 * 识别结果只作为候选题提交审核，审核通过才写入题库（见 MaterialImportService）。
 */
@Component
public class MaterialAgent {

    /** 候选题 / 候选章节：kind=题目 时用题干与答案字段，kind=章节 时用 chapter 与 points 字段。 */
    public record Candidate(String kind, String qtype, int level, String stem, List<String> options,
                            String answer, String explanation, String chapter, String points,
                            double hours, String sourceRef, double confidence) {}

    /** 按 SOP 模板填报的内容：判定标准 / 考核要点 → 判断题，作业步骤 → 单选题。 */
    public record SopInput(String sopName, int level, String skill, List<String> steps, List<String> criteria,
                           List<String> points, List<String> risks) {}

    /** 一次导入最多识别多少道题（管理员审核弹窗一次看这么多条，超出的可分次导入或拆分文档）。 */
    public static final int MAX_QUESTIONS = 24;
    private static final int MAX_SOP_QUESTIONS = 12;
    private static final int MAX_CHAPTERS = 12;
    private static final int MIN_CLAUSE = 10;
    private static final int MAX_CLAUSE = 90;
    private static final int OPTION_CHARS = 60;

    private static final Pattern STEM_LINE = Pattern.compile("^(?:题干|问题|题目|试题)\\s*[:：]\\s*(.+)$");
    private static final Pattern NUMBERED_LINE = Pattern.compile("^\\s*(?:第\\s*)?\\d+\\s*[题.、)）]\\s*(.+)$");
    private static final Pattern OPTION_LINE = Pattern.compile("^\\s*[（(]?([A-Ha-h])[）)]?\\s*[.、)）:：]?\\s*(\\S.*)$");
    private static final Pattern ANSWER_LINE = Pattern.compile("^\\s*(?:参考答案|正确答案|标准答案|答案)\\s*[:：]?\\s*(.+)$");
    private static final Pattern ANALYSIS_LINE = Pattern.compile("^\\s*(?:解析|说明|分析)\\s*[:：]?\\s*(.+)$");
    private static final Pattern HEADING_LINE = Pattern.compile(
        "^(第[一二三四五六七八九十百零]+[章节讲课]|[一二三四五六七八九十]+[、.]\\s*\\S|\\d+(?:\\.\\d+)*[、.\\s]\\S|附录[A-Z一二三四五六七八九十])");
    private static final String[] OBLIGATION = {"应", "必须", "不得", "禁止", "严禁", "宜", "需", "确保", "至少"};
    private static final String[] STEM_JUDGE = {
        "按《%s》，判断下列说法是否正确：%s",
        "依据《%s》的规定，判断下面这句话对不对：%s"};
    private static final String[] STEM_CHOICE = {
        "依据《%s》，下列哪一项属于%s规定的要求？",
        "《%s》%s的条款中，表述正确的一项是？",
        "现场执行《%s》%s时，下列哪一项符合规定？"};

    /** 正文里识别候选题：先按试题结构提题，不够再按条款句出题，最多 MAX_QUESTIONS 道。 */
    public List<Candidate> questions(List<MaterialTextReader.Segment> segments, int level, String title) {
        List<Line> lines = lines(segments);
        List<Candidate> found = new ArrayList<>();
        Set<String> taken = new LinkedHashSet<>();
        List<TextAnswer> textAnswers = new ArrayList<>();

        for (int i = 0; i < lines.size(); i++) {
            String stem = stemOf(lines.get(i).text());
            if (stem == null) continue;
            Block block = block(lines, i, stem);
            if (block.answer() == null) continue;
            i = Math.max(i, block.endIndex());
            Candidate candidate = fromBlock(block, level, title, textAnswers, taken);
            if (candidate != null && found.size() < MAX_QUESTIONS) found.add(candidate);
        }

        List<TextAnswer> usable = textAnswers.size() >= 3 ? textAnswers : List.of();
        for (int i = 0; i < usable.size() && found.size() < MAX_QUESTIONS; i++) {
            Candidate candidate = fromTextAnswer(usable, i, level, title, taken);
            if (candidate != null) found.add(candidate);
        }

        List<Clause> clauses = clauses(lines, taken);
        int cursor = 0;
        while (found.size() < MAX_QUESTIONS && cursor < clauses.size()) {
            Candidate candidate = switch (cursor % 3) {
                case 0 -> judgeTrue(clauses.get(cursor), level, title, taken);
                case 1 -> choice(clauses, cursor, level, title, taken);
                default -> judgeFalse(clauses, cursor, level, title, taken);
            };
            if (candidate == null) {
                candidate = judgeTrue(clauses.get(cursor), level, title, taken);
            }
            if (candidate != null) found.add(candidate);
            cursor++;
        }
        return found;
    }

    /** 课程库目标：整理知识章节（有章节标题就按标题分章，没有就按条款分组）。 */
    public List<Candidate> chapters(List<MaterialTextReader.Segment> segments, int level, String title) {
        List<Line> lines = lines(segments);
        List<Candidate> chapters = new ArrayList<>();
        List<Line> buffer = new ArrayList<>();
        String heading = null;

        for (Line line : lines) {
            if (heading(line.text())) {
                flushChapter(chapters, heading, buffer, level);
                heading = headingText(line.text());
                buffer = new ArrayList<>();
                continue;
            }
            if (isClause(line.text()) || line.text().length() >= MIN_CLAUSE) buffer.add(line);
        }
        flushChapter(chapters, heading, buffer, level);

        if (chapters.size() >= 3) {
            return chapters.size() > MAX_CHAPTERS ? chapters.subList(0, MAX_CHAPTERS) : chapters;
        }
        return chunked(lines, level, title);
    }

    /** SOP 模板填报：判定标准 / 考核要点逐条出判断题，作业步骤出单选题。 */
    public List<Candidate> fromSop(SopInput input) {
        List<Candidate> candidates = new ArrayList<>();
        Set<String> taken = new LinkedHashSet<>();
        String title = input.sopName();
        int index = 0;
        for (String line : concat(input.criteria(), input.points())) {
            if (candidates.size() >= MAX_SOP_QUESTIONS) break;
            String text = line.strip();
            if (text.length() < 4 || !taken.add(text)) continue;
            String risk = input.risks().isEmpty() ? "" : "；风险提示：" + input.risks().get(index % input.risks().size());
            index++;
            candidates.add(new Candidate("题目", "判断", input.level(), text, List.of("A. 对", "B. 错"), "A",
                "出自 SOP《" + title + "》的判定标准 / 考核要点" + risk + "。", null, null, 0,
                "判定标准 / 考核要点 第 " + index + " 条", 0.9));
        }
        for (int i = 0; i < input.steps().size() && candidates.size() < MAX_SOP_QUESTIONS; i++) {
            String right = input.steps().get(i).strip();
            if (right.length() < 4) continue;
            List<String> distractors = new ArrayList<>(input.steps());
            distractors.remove(i);
            int rightPosition = i % 3;
            List<String> options = new ArrayList<>();
            int slot = 0;
            for (int position = 0; position < 3; position++) {
                if (position == rightPosition) {
                    options.add(right);
                    continue;
                }
                options.add(distractors.isEmpty() ? (slot++ == 0 ? "跳过该步骤直接执行" : "由非作业人员代为执行")
                    : distractors.remove(0));
            }
            String[] letters = {"A", "B", "C"};
            List<String> labeled = new ArrayList<>();
            for (int position = 0; position < options.size(); position++) {
                labeled.add(letters[position] + ". " + options.get(position));
            }
            candidates.add(new Candidate("题目", "单选", input.level(),
                "按 SOP《" + title + "》，下列哪一项属于规定的作业步骤？", labeled, letters[rightPosition],
                "出自 SOP《" + title + "》的作业步骤。", null, null, 0, "作业步骤 第 " + (i + 1) + " 条", 0.9));
        }
        if (candidates.size() > MAX_SOP_QUESTIONS) {
            return candidates.subList(0, MAX_SOP_QUESTIONS);
        }
        return candidates;
    }

    // ---- 试题结构识别 ----

    private record Line(String text, String ref, String chapter) {}

    private record Clause(String text, String ref, String chapter, String subject, String predicate) {}

    private record TextAnswer(String stem, String answer, String analysis, String ref) {}

    private record Block(String stem, List<String> options, String answer, String analysis, String ref, int endIndex) {}

    private Candidate fromBlock(Block block, int level, String title, List<TextAnswer> pool, Set<String> taken) {
        String answer = block.answer().strip();
        if (!taken.add(normalize(block.stem()))) return null;
        if (block.options().size() >= 2) {
            String letters = answer.toUpperCase().replaceAll("[^A-H]", "");
            if (letters.length() != 1) return null;
            List<String> options = new ArrayList<>();
            for (int i = 0; i < block.options().size(); i++) {
                options.add((char) ('A' + i) + ". " + block.options().get(i));
            }
            String qtype = judgeOptions(options) ? "判断" : "单选";
            String analysis = block.analysis() == null
                ? "出自《" + title + "》" + block.ref() + "的试题，正确答案：" + letters + "。"
                : block.analysis();
            return new Candidate("题目", qtype, level, block.stem(), options, letters, analysis,
                null, null, 0, block.ref(), 0.95);
        }
        if (isJudgeAnswer(answer)) {
            boolean right = answer.startsWith("对") || answer.startsWith("正确") || answer.startsWith("是");
            return new Candidate("题目", "判断", level, block.stem(), List.of("A. 正确", "B. 错误"),
                right ? "A" : "B", block.analysis() == null ? "出自《" + title + "》" + block.ref() + "的试题。" : block.analysis(),
                null, null, 0, block.ref(), 0.9);
        }
        if (answer.length() >= 2 && answer.length() <= 60) {
            pool.add(new TextAnswer(block.stem(), answer, block.analysis(), block.ref()));
        }
        return null;
    }

    private Candidate fromTextAnswer(List<TextAnswer> pool, int index, int level, String title, Set<String> taken) {
        TextAnswer current = pool.get(index);
        if (!taken.add(normalize(current.stem()))) return null;
        List<String> distractors = new ArrayList<>();
        for (int step = 1; step < pool.size() && distractors.size() < 3; step++) {
            String other = pool.get((index + step) % pool.size()).answer();
            if (!other.equals(current.answer()) && !distractors.contains(other)) distractors.add(other);
        }
        if (distractors.isEmpty()) return null;
        int rightPosition = index % (distractors.size() + 1);
        List<String> values = new ArrayList<>();
        int cursor = 0;
        for (int position = 0; position <= distractors.size(); position++) {
            values.add(position == rightPosition ? current.answer() : distractors.get(cursor++));
        }
        List<String> options = new ArrayList<>();
        for (int position = 0; position < values.size(); position++) {
            options.add((char) ('A' + position) + ". " + values.get(position));
        }
        String answer = String.valueOf((char) ('A' + rightPosition));
        String analysis = current.analysis() == null
            ? "出自《" + title + "》" + current.ref() + "，正确答案：" + current.answer() + "。"
            : current.analysis();
        return new Candidate("题目", "单选", level, current.stem(), options, answer, analysis,
            null, null, 0, current.ref(), 0.85);
    }

    private Block block(List<Line> lines, int start, String stem) {
        List<String> options = new ArrayList<>();
        String answer = null;
        String analysis = null;
        int end = start;
        int guard = 0;
        for (int index = start + 1; index < lines.size() && guard < 14; index++) {
            String text = lines.get(index).text();
            if (index > start + 1 && stemOf(text) != null) break;
            Matcher option = OPTION_LINE.matcher(text);
            Matcher answers = ANSWER_LINE.matcher(text);
            Matcher analyses = ANALYSIS_LINE.matcher(text);
            if (answers.matches()) {
                answer = answers.group(1).strip();
            } else if (analyses.matches() && analysis == null) {
                analysis = analyses.group(1).strip();
            } else if (option.matches() && option.group(2).length() >= 1) {
                options.add(option.group(2).strip());
            } else if (analysis != null && !complete(analysis) && !option.matches()) {
                // 原件里的解析常被排版折行切断（上一行没有句末标点），把这半句接回解析里
                analysis = analysis + text.strip();
            } else if (answer == null && options.isEmpty()) {
                // 题号行常常只有「第 1 题 · NEW-001 技能 · L1 · 单选」这类元信息：
                // 题干还没成形时用下一行当题干，已经有内容才接在后面。
                if (stem.length() <= 20) {
                    stem = text.strip();
                } else if (stem.length() < 60) {
                    stem = (stem + " " + text).strip();
                }
            }
            end = index;
            guard++;
        }
        return new Block(stem, options, answer, analysis, lines.get(start).ref(), end);
    }


    /** PDF / 文档排版会把整段解析折成多行：行尾没有句末标点时，下一行属于同一段。 */
    private static boolean complete(String text) {
        String value = text.strip();
        if (value.isEmpty()) return true;
        char last = value.charAt(value.length() - 1);
        return last == '。' || last == '！' || last == '？' || last == '；' || last == '!' || last == ';';
    }

    private static String stemOf(String text) {
        Matcher explicit = STEM_LINE.matcher(text);
        if (explicit.matches()) return stripMeta(explicit.group(1));
        Matcher numbered = NUMBERED_LINE.matcher(text);
        if (numbered.matches() && text.length() <= 200) return stripMeta(numbered.group(1));
        return null;
    }

    /** 去掉题号行里的元信息片段（题号 / 技能 / 等级 / 题型），只留真正的题干文字。 */
    private static String stripMeta(String text) {
        String value = text.strip();
        if (!value.contains("·")) return value;
        List<String> kept = new ArrayList<>();
        for (String piece : value.split("·")) {
            String part = piece.strip();
            if (part.isEmpty() || part.matches("L[0-3]") || part.matches("\\\\d+\\\\s*(题|分)")
                || part.matches("(单选|多选|判断|填空|简答|问答)")) continue;
            kept.add(part);
        }
        return String.join(" ", kept).strip();
    }

    // ---- 条款句识别 ----

    private Candidate judgeTrue(Clause clause, int level, String title, Set<String> taken) {
        String stem = String.format(STEM_JUDGE[clause.text().length() % STEM_JUDGE.length], title, clause.text());
        if (!taken.add(normalize(stem))) return null;
        return new Candidate("题目", "判断", level, stem, List.of("A. 正确", "B. 错误"), "A",
            "出自《" + title + "》" + clause.ref() + "原文：" + clause.text(), null, null, 0, clause.ref(), 0.75);
    }

    private Candidate judgeFalse(List<Clause> clauses, int cursor, int level, String title, Set<String> taken) {
        Clause current = clauses.get(cursor);
        if (current.subject().isEmpty()) return null;
        for (int step = 1; step < clauses.size(); step++) {
            Clause other = clauses.get((cursor + step) % clauses.size());
            if (other == current || other.subject().isEmpty() || other.subject().equals(current.subject())) continue;
            String statement = current.subject() + other.predicate();
            if (statement.length() > MAX_CLAUSE + 20) continue;
            String stem = String.format(STEM_JUDGE[cursor % STEM_JUDGE.length], title, statement);
            if (!taken.add(normalize(stem))) continue;
            return new Candidate("题目", "判断", level, stem, List.of("A. 正确", "B. 错误"), "B",
                "题干把「" + other.subject() + "」的要求安到了「" + current.subject() + "」上。" + other.ref()
                    + "原文：" + other.text() + "；" + current.ref() + "关于「" + current.subject() + "」的规定是：" + current.text(),
                null, null, 0, current.ref(), 0.7);
        }
        return null;
    }

    private Candidate choice(List<Clause> clauses, int cursor, int level, String title, Set<String> taken) {
        Clause current = clauses.get(cursor);
        List<String> distractors = new ArrayList<>();
        for (int step = 1; step < clauses.size() && distractors.size() < 3; step++) {
            Clause other = clauses.get((cursor + step) % clauses.size());
            if (other.text().equals(current.text()) || distractors.contains(shorten(other.text()))) continue;
            distractors.add(shorten(other.text()));
        }
        if (distractors.size() < 2) return null;
        int rightPosition = cursor % (distractors.size() + 1);
        List<String> values = new ArrayList<>();
        int picked = 0;
        for (int position = 0; position <= distractors.size(); position++) {
            values.add(position == rightPosition ? shorten(current.text()) : distractors.get(picked++));
        }
        String chapter = current.chapter().isEmpty() ? "" : current.chapter() + " ";
        String stem = String.format(STEM_CHOICE[cursor % STEM_CHOICE.length], title, chapter);
        if (!taken.add(normalize(stem) + cursor)) return null;
        List<String> options = new ArrayList<>();
        for (int position = 0; position < values.size(); position++) {
            options.add((char) ('A' + position) + ". " + values.get(position));
        }
        return new Candidate("题目", "单选", level, stem.strip(), options, String.valueOf((char) ('A' + rightPosition)),
            "正确项出自《" + title + "》" + current.ref() + "：" + current.text() + "；其余选项取自同一文档的其他条款，不是本题要求。",
            null, null, 0, current.ref(), 0.72);
    }

    private List<Clause> clauses(List<Line> lines, Set<String> taken) {
        List<Clause> clauses = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (Line line : lines) {
            if (taken.contains(normalize(line.text()))) continue;
            for (String piece : split(line.text())) {
                if (!isClause(piece)) continue;
                if (!seen.add(normalize(piece))) continue;
                int at = markerAt(piece);
                String subject = at > 0 ? piece.substring(0, at).strip() : "";
                String predicate = at > 0 ? piece.substring(at).strip() : "";
                if (subject.length() > 30) subject = "";
                clauses.add(new Clause(piece, line.ref(), line.chapter(), subject, predicate));
            }
        }
        return clauses;
    }

    private void flushChapter(List<Candidate> chapters, String heading, List<Line> buffer, int level) {
        if (heading == null || buffer.isEmpty() || chapters.size() >= MAX_CHAPTERS) return;
        List<String> points = new ArrayList<>();
        for (Line line : buffer) {
            if (points.size() >= 3) break;
            for (String piece : split(line.text())) {
                if (piece.length() < MIN_CLAUSE) continue;
                points.add(piece);
                break;
            }
        }
        if (points.isEmpty()) return;
        String joined = shorten(String.join("；", points), 240);
        chapters.add(new Candidate("章节", null, level, null, null, null, null, heading, joined,
            hours(joined.length()), buffer.get(0).ref(), 0.8));
    }

    /** 没有章节标题时：按条款顺序分组，每 4 条一组，组名取第一条条款的要点。 */
    private List<Candidate> chunked(List<Line> lines, int level, String title) {
        List<Clause> clauses = clauses(lines, Set.of());
        List<Candidate> chapters = new ArrayList<>();
        for (int start = 0; start < clauses.size() && chapters.size() < MAX_CHAPTERS; start += 4) {
            List<String> points = new ArrayList<>();
            for (int index = start; index < Math.min(start + 4, clauses.size()); index++) {
                points.add(clauses.get(index).text());
            }
            String joined = shorten(String.join("；", points), 240);
            String name = clauses.get(start).subject().isEmpty()
                ? shorten(clauses.get(start).text(), 16) : clauses.get(start).subject();
            chapters.add(new Candidate("章节", null, level, null, null, null, null,
                "第 " + (chapters.size() + 1) + " 章 " + name, joined, hours(joined.length()),
                clauses.get(start).ref(), 0.65));
        }
        return chapters;
    }

    private static double hours(int chars) {
        if (chars <= 80) return 1.0;
        return chars <= 160 ? 1.5 : 2.0;
    }

    private List<Line> lines(List<MaterialTextReader.Segment> segments) {
        List<Line> lines = new ArrayList<>();
        String chapter = "";
        for (MaterialTextReader.Segment segment : segments) {
            for (String raw : segment.text().split("\r\n|\r|\n")) {
                String text = raw.strip();
                if (text.length() < 2) continue;
                if (heading(text)) chapter = text;
                lines.add(new Line(text, segment.label(), chapter));
            }
        }
        return lines;
    }

    /** Markdown 井号 / 引用 / 项目符号前缀不属于标题正文，先剥掉再判断（.md 资料同样能分出章节）。 */
    private static String headingText(String text) {
        return text.strip().replaceAll("^[#>]+\\s*", "").replaceAll("^[*\\-•·]\\s+", "").strip();
    }

    private static boolean heading(String text) {
        String value = headingText(text);
        if (value.length() > 40) return false;
        if (value.endsWith("。") || value.endsWith("；") || value.endsWith("，")) return false;
        return HEADING_LINE.matcher(value).find();
    }

    private static List<String> split(String text) {
        List<String> pieces = new ArrayList<>();
        for (String piece : text.split("[。；;！!？?\\n]")) {
            String value = piece.strip().replaceAll("^[0-9（）()一二三四五六七八九十]+[.、)）]\\s*", "");
            if (!value.isEmpty()) pieces.add(value);
        }
        return pieces;
    }

    private static boolean isClause(String text) {
        int length = text.length();
        if (length < MIN_CLAUSE || length > MAX_CLAUSE) return false;
        if (text.contains("答案") || text.contains("解析")) return false;
        return markerAt(text) >= 0;
    }

    /** 条款句里第一个要求性字眼的位置（「应 / 必须 / 不得 / 严禁」等），用来切出主语与要求内容。 */
    private static int markerAt(String text) {
        int at = -1;
        for (String marker : OBLIGATION) {
            int index = text.indexOf(marker);
            if (index >= 0 && (at < 0 || index < at)) at = index;
        }
        return at;
    }

    private static boolean isJudgeAnswer(String answer) {
        return answer.startsWith("对") || answer.startsWith("错") || answer.startsWith("正确") || answer.startsWith("错误")
            || answer.startsWith("是") || answer.startsWith("否");
    }

    private static boolean judgeOptions(List<String> options) {
        String first = options.get(0).replaceAll("^[A-H][.、)）]\\s*", "");
        String second = options.size() > 1 ? options.get(1).replaceAll("^[A-H][.、)）]\\s*", "") : "";
        return first.length() <= 3 && (first.startsWith("对") || first.startsWith("正确") || first.startsWith("是"))
            && second.length() <= 3;
    }

    private static String shorten(String text) {
        return shorten(text, OPTION_CHARS);
    }

    private static String shorten(String text, int limit) {
        String value = text.strip();
        return value.length() <= limit ? value : value.substring(0, limit) + "…";
    }

    private static String normalize(String text) {
        return text.replaceAll("\\s+", "").replaceAll("[，。；、,.;:：（）()「」《》]", "");
    }

    private static List<String> concat(List<String> first, List<String> second) {
        List<String> all = new ArrayList<>(first);
        all.addAll(second);
        return all;
    }
}
