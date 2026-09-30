package com.power.train.material;

import static com.power.train.support.ApiResponse.row;

import com.power.train.practice.QuestionBank;
import com.power.train.store.Sql;
import com.power.train.support.Actor;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

/**
 * 资料导入与审核入库：组长上传文档（或按 SOP 模板填报）→ Agent 读正文并识别候选题 →
 * 写进 course_material 台账与 material_item 待审核清单 → 管理员逐条核对后通过 →
 * 才写入 question（题库）或 course（课程库）并累加题库统计，普通员工抽题随即能抽到。
 * 审核前候选题只存在 material_item 里，不参与抽题，也不会出现在员工端。
 */
@Service
public class MaterialImportService {

    private static final Logger log = LoggerFactory.getLogger(MaterialImportService.class);
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final int EXCERPT_LINES = 6;
    private static final int EXCERPT_CHARS = 160;
    /** 列表接口返回的候选题上限：一次导入最多这么多条，避免审核弹窗无限长。 */
    private static final int MAX_LISTED = 30;
    /** 审计留痕里的来源 IP（与管理员后台保持一致，演示环境固定）。 */
    private static final String AUDIT_IP = "10.12.3.8";

    /** 校验失败：字段级错误与整体提示一起返回，前端按字段回显（与检测报告填报一致）。 */
    public static class MaterialImportException extends RuntimeException {
        private final transient Map<String, String> fieldErrors;

        MaterialImportException(Map<String, String> fieldErrors, String message) {
            super(message);
            this.fieldErrors = fieldErrors;
        }

        public Map<String, String> fieldErrors() {
            return fieldErrors;
        }
    }

    private final Sql sql;
    private final Actor actor;
    private final MaterialTextReader reader;
    private final MaterialAgent agent;
    private final QuestionBank bank;
    private final String materialDir;
    private final int maxMb;

    public MaterialImportService(Sql sql, Actor actor, MaterialTextReader reader, MaterialAgent agent,
                                 QuestionBank bank,
                                 @Value("${material.dir:${java.io.tmpdir}/power-train-materials}") String materialDir,
                                 @Value("${material.max-mb:20}") int maxMb) {
        this.sql = sql;
        this.actor = actor;
        this.reader = reader;
        this.agent = agent;
        this.bank = bank;
        this.materialDir = materialDir;
        this.maxMb = maxMb;
    }

    // ---- 组长侧：上传文档 / SOP 模板填报 ----

    /** 导入文档：读正文 → Agent 识别 → 落台账 → 等待管理员审核。 */
    @Transactional
    public Map<String, Object> uploadDocument(MultipartFile file, String target, String skill, String level,
                                              String version, String title, String note) {
        Map<String, String> errors = new LinkedHashMap<>();
        String fileName = file == null ? "" : String.valueOf(file.getOriginalFilename()).strip();
        String cleanTarget = value(target, "题库");
        if (fileName.isEmpty() || file.getSize() == 0) {
            errors.put("file", "请选择要导入的文档（" + String.join(" / ", MaterialTextReader.READABLE) + "）");
        }
        if (skill == null || skill.isBlank()) {
            errors.put("skill", "请选择资料对应的技能");
        }
        if (level == null || level.isBlank()) {
            errors.put("level", "请选择适用技能等级（L1 / L2 / L3）");
        }
        if (!"题库".equals(cleanTarget) && !"课程库".equals(cleanTarget)) {
            errors.put("target", "入库目标只支持：题库 / 课程库");
        }
        if (!fileName.isEmpty() && !MaterialTextReader.readable(fileName)) {
            errors.put("file", "暂不支持识别该格式：" + MaterialTextReader.extension(fileName)
                + "；可识别 " + String.join(" / ", MaterialTextReader.READABLE));
        }
        long maxBytes = maxMb * 1024L * 1024L;
        if (file != null && file.getSize() > maxBytes) {
            errors.put("file", "文件超过 " + maxMb + "MB，请拆分或压缩后再上传");
        }
        if (!errors.isEmpty()) {
            throw new MaterialImportException(errors, "资料导入校验未通过，请按提示修改后重新提交");
        }

        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (Exception error) {
            throw new MaterialImportException(Map.of("file", "文件读取失败：" + error.getMessage()), "文件读取失败");
        }
        MaterialTextReader.Extracted extracted = reader.read(fileName, bytes);
        if (extracted.empty()) {
            throw new MaterialImportException(Map.of("file", extracted.note().isBlank()
                ? "没有从文档里读到正文，无法识别题目" : extracted.note()), "文档没有可识别的正文");
        }
        int levelValue = parseLevel(level);
        String docTitle = title == null || title.isBlank() ? baseName(fileName) : title.strip();
        String materialType = "题库".equals(cleanTarget) ? "题库资料" : "课程资料";
        List<MaterialAgent.Candidate> candidates = "题库".equals(cleanTarget)
            ? agent.questions(extracted.segments(), levelValue, docTitle)
            : agent.chapters(extracted.segments(), levelValue, docTitle);
        if (candidates.isEmpty()) {
            throw new MaterialImportException(Map.of("file",
                "读到了 " + extracted.charCount() + " 字正文，但没有识别出可用的题目 / 章节（正文可能不是条款式或试题式内容）"),
                "Agent 没有识别出可入库的条目");
        }
        String capHint = candidates.size() >= MaterialAgent.MAX_QUESTIONS
            ? "；文档里的题更多，单次最多识别 " + MaterialAgent.MAX_QUESTIONS + " 条，可拆分文档分次导入" : "";

        String code = MaterialCodes.nextMaterialCode(sql);
        Path stored = store(code, fileName, bytes);
        String at = now();
        String skillCode = MaterialCodes.skillCodeOf(sql, skill);
        insertMaterial(code, docTitle, skill, skillCode, cleanTarget, materialType, fileName,
            MaterialTextReader.extension(fileName), level, value(version, "v1"),
            "课程库".equals(cleanTarget) ? totalHours(candidates) : null, candidates.size(),
            confidence(candidates), "文档导入", at, stored == null ? null : stored.toString(),
            note,
            "规则引擎读原件正文后识别出 " + candidates.size()
                + ("课程库".equals(cleanTarget) ? " 个知识章节" : " 道题（含答案与解析）")
                + "，等待管理员审核" + (extracted.note().isBlank() ? "" : "；" + extracted.note()) + capHint);
        if (stored != null) {
            sql.update("INSERT INTO file_object (owner, object_key, file_name, content_type, size_kb) VALUES (?, ?, ?, ?, ?)",
                actor.name(), stored.toString(), fileName, "application/" + MaterialTextReader.extension(fileName),
                (int) (bytes.length / 1024));
        }
        saveDoc(code, fileName, MaterialTextReader.extension(fileName), extracted, stored, "文档导入");
        saveItems(code, candidates, skill, levelValue);
        audit("上传", "导入文档 " + code + " · " + fileName + "（Agent 识别 " + candidates.size() + " 条，待审核）", "资料台账", "成功");
        log.info("material {} imported from {}: {} candidates", code, fileName, candidates.size());

        Map<String, Object> view = new LinkedHashMap<>();
        view.put("accepted", true);
        view.put("material_code", code);
        view.put("status", "待审核");
        view.put("generated_count", candidates.size());
        view.put("bank_total", bank.size());
        view.put("source", sourceLabel(docTitle, fileName, "文档导入"));
        view.put("agent_mode", "文档导入");
        view.put("file", fileView(fileName, MaterialTextReader.extension(fileName), extracted, stored, at));
        view.put("generated", candidateViews(candidates));
        boolean toBank = "题库".equals(cleanTarget);
        view.put("note", "Agent 已读《" + fileName + "》正文（" + extracted.pages() + " 页 / " + extracted.charCount()
            + " 字），" + (toBank
                ? "识别出 " + candidates.size() + " 道题（含答案与解析）"
                : "整理出 " + candidates.size() + " 个知识章节（含要点与学时）")
            + "并提交管理员审核；审核通过后写入" + cleanTarget
            + (toBank ? "，普通员工抽题时即可抽到" : "，员工在学习与考试里即可看到") + capHint + "。");
        return view;
    }
    /** SOP 模板填报：判定标准 / 考核要点 / 作业步骤 → 候选题 → 等待管理员审核。 */
    @Transactional
    public Map<String, Object> submitSop(String sopName, String skill, String level, String steps, String criteria,
                                         String points, String risks) {
        Map<String, String> errors = new LinkedHashMap<>();
        if (sopName == null || sopName.isBlank()) errors.put("sop_name", "SOP 名称为必填项");
        if (skill == null || skill.isBlank()) errors.put("skill", "对应技能为必填项");
        if (steps == null || steps.isBlank()) errors.put("steps", "作业步骤为必填项，每行一条");
        if (criteria == null || criteria.isBlank()) errors.put("criteria", "判定标准为必填项，每行一条");
        if (points == null || points.isBlank()) errors.put("points", "考核要点为必填项，每行一条");
        if (!errors.isEmpty()) {
            throw new MaterialImportException(errors, "SOP 模板校验失败，请补充必填内容");
        }
        int levelValue = parseLevel(level);
        List<String> stepLines = lines(steps);
        List<String> criteriaLines = lines(criteria);
        List<String> pointLines = lines(points);
        List<String> riskLines = lines(risks);
        List<MaterialAgent.Candidate> candidates = agent.fromSop(new MaterialAgent.SopInput(sopName.strip(), levelValue,
            skill.strip(), stepLines, criteriaLines, pointLines, riskLines));
        if (candidates.isEmpty()) {
            throw new MaterialImportException(Map.of("criteria", "按填写内容没有生成候选题，请把判定标准 / 考核要点写得更具体"),
                "SOP 内容不足以生成练习题");
        }
        String code = MaterialCodes.nextMaterialCode(sql);
        String at = now();
        String fileName = sopName.strip() + "（SOP 模板填报）";
        insertMaterial(code, sopName.strip(), skill.strip(), MaterialCodes.skillCodeOf(sql, skill), "题库", "SOP 资料", fileName, "sopform",
            level, "v1", null, candidates.size(), confidence(candidates), "SOP", at, null,
            null,
            "规则引擎解析 SOP 的判定标准 / 考核要点 / 作业步骤，生成 " + candidates.size() + " 道候选题，等待管理员审核");
        saveSopDoc(code, fileName, criteriaLines, pointLines, stepLines, riskLines);
        saveItems(code, candidates, skill.strip(), levelValue);
        audit("上传", "提交 SOP 练习资料 " + code + " · " + sopName.strip() + "（Agent 识别 " + candidates.size() + " 题，待审核）",
            "资料台账", "成功");

        Map<String, Object> view = new LinkedHashMap<>();
        view.put("accepted", true);
        view.put("material_code", code);
        view.put("status", "待审核");
        view.put("generated_count", candidates.size());
        view.put("bank_total", bank.size());
        view.put("source", sourceLabel(sopName.strip(), fileName, "SOP"));
        view.put("agent_mode", "SOP 模板");
        view.put("file", fileView(fileName, "sopform", null, null, at));
        view.put("generated", candidateViews(candidates));
        view.put("note", "Agent 已解析 SOP 生成 " + candidates.size() + " 道候选题并提交管理员审核；"
            + "审核通过后写入题库，普通员工抽题时即可抽到。");
        return view;
    }

    /** 组长侧：本班组上传的资料与审核状态（含待审核 / 已入库 / 已驳回条数）。 */
    public List<Map<String, Object>> batches() {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : sql.rows(
            "SELECT code, title, skill, skill_code, target, material_type, file_name, file_type, target_level, version, "
                + "hours, recognized_items, agent_confidence, agent_note, status, submitted_by, submitted_at, source, note, "
                + "stored_result, reviewed_by, reviewed_at FROM course_material "
                + "WHERE source LIKE '组长%' ORDER BY code DESC")) {
            Map<String, Object> item = materialView(row);
            String code = String.valueOf(row.get("code"));
            item.put("pending_items", countItems(code, "待审核"));
            item.put("stored_items", countItems(code, "已入库"));
            item.put("rejected_items", countItems(code, "已驳回"));
            items.add(item);
        }
        return items;
    }

    /** 组长侧 / 管理员侧共用：看一批资料的台账、原件摘录与候选题（含每条状态）。 */
    public Map<String, Object> detail(String code) {
        Map<String, Object> material = sql.row("SELECT code, title, skill, skill_code, target, material_type, file_name, "
            + "file_type, target_level, version, hours, recognized_items, agent_confidence, agent_note, status, "
            + "submitted_by, submitted_at, source, note, stored_result, reviewed_by, reviewed_at "
            + "FROM course_material WHERE code = ?", code);
        if (material == null) return null;
        Map<String, Object> doc = sql.row("SELECT file_name, file_type, pages, size_kb, char_count, stored_path, "
            + "extract_note, agent_mode, text_excerpt FROM material_doc WHERE material_code = ?", code);
        List<Map<String, Object>> items = items(code);
        Map<String, Object> extracted = new LinkedHashMap<>();
        String mode = String.valueOf(material.get("target"));
        boolean chapterMode = !items.isEmpty() && "章节".equals(items.get(0).get("kind"));
        extracted.put("mode", mode);
        extracted.put("chapter_mode", chapterMode);
        extracted.put("total", items.size());
        extracted.put("listed", items.size());
        extracted.put("has_more", false);
        extracted.put("summary", items.isEmpty() ? "该资料没有候选题记录"
            : (chapterMode
                ? "Agent 从《" + material.get("file_name") + "》整理出 " + items.size() + " 个知识章节，入库前请核对章节与学时"
                : "Agent 从《" + material.get("file_name") + "》识别出 " + items.size() + " 道题（含答案与解析），入库前请逐条核对题干与答案"));
        extracted.put("items", items);

        Map<String, Object> view = new LinkedHashMap<>();
        view.put("material", materialView(material));
        view.put("file", doc == null
            ? fileView(String.valueOf(material.get("file_name")), String.valueOf(material.get("file_type")), null, null, null)
            : row("file_name", doc.get("file_name"), "file_type", doc.get("file_type"), "pages", doc.get("pages"),
                "size_kb", doc.get("size_kb"), "char_count", doc.get("char_count"), "preview_note", doc.get("extract_note"),
                "url", doc.get("stored_path"), "uploaded_at", material.get("submitted_at"),
                "uploaded_by", material.get("submitted_by"), "agent_mode", doc.get("agent_mode")));
        view.put("doc_excerpt", doc == null ? List.of() : excerpt(doc));
        view.put("extracted", extracted);
        view.put("pending_items", countItems(code, "待审核"));
        view.put("stored_items", countItems(code, "已入库"));
        view.put("already_stored", countItems(code, "待审核") == 0 && countItems(code, "已入库") > 0);
        view.put("stored_result", material.getOrDefault("stored_result", "—"));
        return view;
    }
    // ---- 管理员侧：审核入库 ----

    /**
     * 管理员审核：勾选通过的条目写进题库 / 课程库，驳回的只留台账，没处理的继续留在待审核。
     * generatedFallback 用于兼容管理员「按规定格式上传」的演示批次（没有 material_item 台账，
     * 条目由 MaterialInspector 在审核弹窗里生成），保证这两条路径的入库动作完全一致。
     */
    @Transactional
    public Map<String, Object> review(String code, String action, List<Long> approveIds, List<Long> rejectIds,
                                      List<Map<String, Object>> generatedFallback) {
        Map<String, Object> material = sql.row("SELECT code, title, skill, skill_code, target, target_level, version, "
            + "hours, recognized_items, file_name, material_type, status FROM course_material WHERE code = ?", code);
        if (material == null) {
            return row("reviewed", false, "message", "资料不存在：" + code);
        }
        if (!"approve".equals(action) && !"reject".equals(action)) {
            return row("reviewed", false, "message", "审核动作只支持 approve / reject");
        }
        String at = now();
        List<Map<String, Object>> stored = sql.rows("SELECT id, seq, kind, qtype, skill, level, stem, options, answer, "
            + "explanation, chapter, points, hours, source_ref, confidence, status FROM material_item "
            + "WHERE material_code = ? ORDER BY seq, id", code);
        boolean hasStored = !stored.isEmpty();

        if ("reject".equals(action)) {
            if (hasStored) {
                for (Map<String, Object> row : stored) {
                    if (!"待审核".equals(String.valueOf(row.get("status")))) continue;
                    if (rejectIds != null && !rejectIds.isEmpty()
                        && !rejectIds.contains(((Number) row.get("id")).longValue())) continue;
                    sql.update("UPDATE material_item SET status = '已驳回', reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                        actor.name(), at, row.get("id"));
                }
            }
            String result = hasStored
                ? "已驳回 " + countItems(code, "已驳回") + " 条，未写入题库 / 课程库"
                : "已驳回，未写入课程库 / 题库";
            refreshMaterialStatus(code, at, result);
            audit("审批", "驳回资料 " + code + " · " + material.get("title"), "资料台账", "成功");
            return row("reviewed", true, "code", code, "status", materialStatus(code), "stored", false,
                "stored_result", result, "message", result, "items", items(code),
                "pending_items", countItems(code, "待审核"));
        }

        List<Map<String, Object>> toStore = new ArrayList<>();
        if (hasStored) {
            Set<Long> approved = approveIds == null || approveIds.isEmpty() ? null : new LinkedHashSet<>(approveIds);
            for (Map<String, Object> row : stored) {
                if (!"待审核".equals(String.valueOf(row.get("status")))) continue;
                if (approved != null && !approved.contains(((Number) row.get("id")).longValue())) continue;
                toStore.add(row);
            }
            if (toStore.isEmpty()) {
                return row("reviewed", false, "message", "没有可入库的条目：请先勾选要审核通过的题（或点全部通过）",
                    "items", items(code), "pending_items", countItems(code, "待审核"));
            }
        } else {
            toStore.addAll(generatedFallback == null ? List.<Map<String, Object>>of() : generatedFallback);
            if (toStore.isEmpty()) {
                return row("reviewed", false, "message", "这批资料没有可入库的条目");
            }
        }
        String result = storeItems(material, toStore, at);
        if (hasStored) {
            for (Map<String, Object> row : toStore) {
                sql.update("UPDATE material_item SET status = '已入库', question_id = ?, reviewed_by = ?, reviewed_at = ? "
                    + "WHERE id = ?", row.get("question_code"), actor.name(), at, row.get("id"));
            }
        }
        refreshMaterialStatus(code, at, result);
        audit("审批", "审核通过资料 " + code + " · " + material.get("title") + "（" + result + "）", "资料台账", "成功");
        long pending = countItems(code, "待审核");
        return row("reviewed", true, "code", code, "status", materialStatus(code), "stored", true,
            "stored_count", toStore.size(), "stored_result", result,
            "message", (pending > 0 ? "已通过 " + toStore.size() + " 条，" + result + "；另有 " + pending + " 条仍待审核"
                : "已通过 " + toStore.size() + " 条，" + result),
            "items", items(code), "pending_items", pending);
    }

    // ---- 内部：入库与落库 ----

    /** 真正写库：题库目标逐题写入 question 并累加题库统计，课程库目标合并成一门课程。 */
    private String storeItems(Map<String, Object> material, List<Map<String, Object>> items, String at) {
        String target = String.valueOf(material.get("target"));
        String skill = String.valueOf(material.get("skill"));
        String level = String.valueOf(material.get("target_level"));
        String version = String.valueOf(material.get("version"));
        int levelValue = parseLevel(level);
        String source = sourceLabel(String.valueOf(material.get("title")), String.valueOf(material.get("file_name")),
            String.valueOf(material.get("material_type")));
        if ("课程库".equals(target)) {
            List<Map<String, Object>> chapters = new ArrayList<>();
            for (Map<String, Object> item : items) {
                if ("章节".equals(String.valueOf(item.get("kind"))) || item.get("chapter") != null) chapters.add(item);
            }
            double hours = 0;
            for (Map<String, Object> chapter : chapters) {
                hours += number(chapter.get("hours"), 1.0);
            }
            String courseCode = "C-" + material.get("skill_code") + "-" + version + "-" + material.get("code");
            sql.update("INSERT INTO course (code, name, course_type, hours, skill, target_level, status, materials, "
                    + "source_file, reviewed_by, reviewed_at, sort_no) "
                    + "VALUES (?, ?, '线上', ?, ?, ?, '已上线', ?, ?, ?, ?, ?) "
                    + "ON DUPLICATE KEY UPDATE name = VALUES(name), hours = VALUES(hours), skill = VALUES(skill), "
                    + "target_level = VALUES(target_level), status = '已上线', materials = VALUES(materials), "
                    + "source_file = VALUES(source_file), reviewed_by = VALUES(reviewed_by), reviewed_at = VALUES(reviewed_at)",
                courseCode, material.get("title"), hours, skill, level, Math.max(chapters.size(), 1),
                material.get("file_name"), actor.name(), at, MaterialCodes.nextSortNo(sql, "course"));
            return "课程库新增课程 " + courseCode + "（含 " + Math.max(chapters.size(), 1) + " 个章节 / "
                + trimHours(hours) + " 学时），员工「学习与考试」的课程库随即可见";
        }
        int stored = 0;
        for (Map<String, Object> item : items) {
            if ("章节".equals(String.valueOf(item.get("kind")))) continue;
            String stem = string(item.get("stem"), string(item.get("question"), ""));
            if (stem.isBlank()) continue;
            List<String> options = item.get("options") instanceof List<?> list
                ? stringList(list) : stringList(sql.parseList(item.get("options")));
            String answer = string(item.get("answer"), "A");
            String explanation = string(item.get("explanation"), string(item.get("analysis"), ""));
            QuestionBank.Question question = bank.add(skill, (int) number(item.get("level"), levelValue),
                "判断".equals(String.valueOf(item.get("qtype"))) ? "判断" : "单选", stem, options, answer,
                explanation, source);
            item.put("question_code", question.id());
            stored++;
        }
        refreshBank(skill, String.valueOf(material.get("skill_code")), stored, at);
        return "题库新增 " + stored + " 题（题库共 " + bank.size() + " 题），普通员工抽题即可抽到";
    }

    /** 题库统计表（管理员页面展示的题库台账）跟着累加。 */
    private void refreshBank(String skill, String skillCode, int added, String at) {
        if (added <= 0) return;
        Map<String, Object> bankRow = sql.row("SELECT code, questions FROM question_bank WHERE skill = ? "
            + "ORDER BY sort_no, code LIMIT 1", skill);
        if (bankRow == null) {
            sql.update("INSERT INTO question_bank (code, name, skill, questions, types, difficulty, updated_at, used_by, sort_no) "
                    + "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                "QB-" + skillCode, skill + "题库（资料导入）", skill, added, "单选 / 判断", "中", at.substring(0, 10),
                MaterialCodes.nextSortNo(sql, "question_bank"));
            return;
        }
        int total = (int) number(bankRow.get("questions"), 0) + added;
        sql.update("UPDATE question_bank SET questions = ?, updated_at = ? WHERE code = ?", total, at.substring(0, 10),
            bankRow.get("code"));
    }

    private void insertMaterial(String code, String title, String skill, String skillCode, String target,
                                String materialType, String fileName, String fileType, String level, String version,
                                Double hours, int recognized, double confidence, String agentMode, String at,
                                String fileUrl, String note, String agentNote) {
        sql.update("INSERT INTO course_material (code, title, skill, skill_code, target, material_type, file_name, "
                + "file_type, target_level, version, hours, recognized_items, agent_confidence, agent_note, status, "
                + "submitted_by, submitted_at, file_url, source, note, sort_no) "
                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待审核', ?, ?, ?, ?, ?, ?)",
            code, title, skill, skillCode, target, materialType, fileName, fileType, level, version, hours,
            recognized, confidence, agentNote, actor.name(), at, fileUrl,
            "SOP".equals(agentMode) ? "组长 SOP 生成" : "组长导入文档", note, MaterialCodes.nextSortNo(sql, "course_material"));
    }

    /** 原件留档：读到的正文整篇存进 material_doc，管理员审核时看到的就是 Agent 真正读到的内容。 */
    private void saveDoc(String code, String fileName, String fileType, MaterialTextReader.Extracted extracted,
                         Path stored, String agentMode) {
        sql.update("INSERT INTO material_doc (material_code, file_name, file_type, pages, size_kb, char_count, "
                + "stored_path, extract_note, agent_mode, text_excerpt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            code, fileName, fileType, extracted.pages(), stored == null ? 0 : (int) (fileSize(stored) / 1024),
            extracted.charCount(), stored == null ? null : stored.toString(),
            blank(extracted.note(), "正文已完整读取"), agentMode, extracted.text());
    }

    /** SOP 填报没有上传原件，把填报内容本身当作「原件」留档，管理员看到的就是组长填的东西。 */
    private void saveSopDoc(String code, String fileName, List<String> criteria, List<String> points,
                            List<String> steps, List<String> risks) {
        StringBuilder builder = new StringBuilder();
        builder.append("【判定标准】").append(String.join("；", criteria)).append('\n');
        builder.append("【考核要点】").append(String.join("；", points)).append('\n');
        builder.append("【作业步骤】").append(String.join("；", steps));
        if (!risks.isEmpty()) builder.append('\n').append("【风险点与控制措施】").append(String.join("；", risks));
        sql.update("INSERT INTO material_doc (material_code, file_name, file_type, pages, size_kb, char_count, "
                + "stored_path, extract_note, agent_mode, text_excerpt) VALUES (?, ?, 'sopform', 0, 0, ?, NULL, ?, 'SOP 模板', ?)",
            code, fileName, builder.length(),
            "来源：组长按 SOP 模板逐项填报，没有上传原件；请核对填报内容与生成题目是否一致", builder.toString());
    }

    private void saveItems(String code, List<MaterialAgent.Candidate> candidates, String skill, int level) {
        int seq = 0;
        for (MaterialAgent.Candidate candidate : candidates) {
            seq++;
            sql.update("INSERT INTO material_item (material_code, seq, kind, qtype, skill, level, stem, options, answer, "
                    + "explanation, chapter, points, hours, source_ref, confidence, status) "
                    + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待审核')",
                code, seq, candidate.kind(), candidate.qtype(), skill,
                candidate.level() <= 0 ? level : candidate.level(), candidate.stem(),
                candidate.options() == null ? null : sql.json(candidate.options()), candidate.answer(),
                candidate.explanation(), candidate.chapter(), candidate.points(),
                candidate.hours() <= 0 ? null : candidate.hours(), candidate.sourceRef(), candidate.confidence());
        }
        sql.update("UPDATE course_material SET recognized_items = ? WHERE code = ?", seq, code);
    }

    // ---- 内部：视图与工具 ----

    private List<Map<String, Object>> items(String code) {
        List<Map<String, Object>> views = new ArrayList<>();
        for (Map<String, Object> row : sql.rows("SELECT id, seq, kind, qtype, skill, level, stem, options, answer, "
            + "explanation, chapter, points, hours, source_ref, confidence, status, question_id, reviewed_by, reviewed_at "
            + "FROM material_item WHERE material_code = ? ORDER BY seq, id", code)) {
            views.add(itemView(row, views.size() + 1));
        }
        return views;
    }

    private Map<String, Object> itemView(Map<String, Object> row, int index) {
        boolean chapter = "章节".equals(String.valueOf(row.get("kind")));
        Map<String, Object> view = new LinkedHashMap<>();
        Object id = row.get("id");
        view.put("id", id instanceof Number number ? number.longValue() : id);
        view.put("index", index);
        view.put("kind", row.get("kind"));
        view.put("type", chapter ? "章节" : ("判断".equals(String.valueOf(row.get("qtype"))) ? "判断题" : "单选题"));
        view.put("qtype", row.get("qtype"));
        view.put("skill", row.get("skill"));
        view.put("level", row.get("level"));
        view.put("stem", row.get("stem"));
        view.put("question", row.get("stem"));
        List<String> options = stringList(sql.parseList(row.get("options")));
        view.put("options", options);
        view.put("answer", row.get("answer"));
        view.put("explanation", row.get("explanation"));
        view.put("analysis", row.get("explanation"));
        view.put("chapter", row.get("chapter"));
        view.put("points", row.get("points"));
        view.put("hours", row.get("hours"));
        view.put("source_ref", row.get("source_ref"));
        view.put("source_page", row.get("source_ref"));
        view.put("confidence", row.get("confidence"));
        view.put("status", row.get("status"));
        view.put("question_id", row.get("question_id"));
        view.put("reviewed_by", row.get("reviewed_by"));
        view.put("reviewed_at", row.get("reviewed_at"));
        if (!chapter) {
            String answer = String.valueOf(row.get("answer"));
            String matched = answer;
            for (String option : options) {
                if (option.startsWith(answer + ".")) matched = option;
            }
            view.put("answer_text", matched);
            view.put("knowledge", row.get("chapter") == null ? String.valueOf(row.get("skill")) : row.get("chapter"));
        }
        return view;
    }

    private List<Map<String, Object>> candidateViews(List<MaterialAgent.Candidate> candidates) {
        List<Map<String, Object>> views = new ArrayList<>();
        int index = 0;
        for (MaterialAgent.Candidate candidate : candidates) {
            index++;
            if (index > MAX_LISTED) break;
            Map<String, Object> view = new LinkedHashMap<>();
            view.put("index", index);
            view.put("kind", candidate.kind());
            view.put("type", "章节".equals(candidate.kind()) ? "章节"
                : ("判断".equals(candidate.qtype()) ? "判断题" : "单选题"));
            view.put("level", candidate.level());
            view.put("stem", candidate.stem());
            view.put("question", candidate.stem());
            view.put("options", candidate.options() == null ? List.of() : candidate.options());
            view.put("answer", candidate.answer());
            String answerText = candidate.answer();
            if (candidate.options() != null) {
                for (String option : candidate.options()) {
                    if (option.startsWith(candidate.answer() + ".")) answerText = option;
                }
            }
            view.put("answer_text", answerText);
            view.put("explanation", candidate.explanation());
            view.put("analysis", candidate.explanation());
            view.put("chapter", candidate.chapter());
            view.put("points", candidate.points());
            view.put("hours", candidate.hours());
            view.put("source_ref", candidate.sourceRef());
            view.put("source_page", candidate.sourceRef());
            view.put("confidence", candidate.confidence());
            view.put("status", "待审核");
            views.add(view);
        }
        return views;
    }

    private List<String> excerpt(Map<String, Object> doc) {
        List<String> lines = new ArrayList<>();
        lines.add("原件：" + doc.get("file_name") + "（" + doc.get("file_type") + " · " + doc.get("pages") + " 页 · "
            + doc.get("size_kb") + " KB · 读到 " + doc.get("char_count") + " 字）");
        Object note = doc.get("extract_note");
        if (note != null && !String.valueOf(note).isBlank()) {
            lines.add("读取说明：" + note);
        }
        String text = doc.get("text_excerpt") == null ? "" : String.valueOf(doc.get("text_excerpt"));
        int index = 0;
        for (String raw : text.split("\r\n|\r|\n")) {
            String value = raw.strip();
            if (value.length() < 6) continue;
            if (value.length() > EXCERPT_CHARS) value = value.substring(0, EXCERPT_CHARS) + "…";
            lines.add("正文摘录 " + (++index) + "：" + value);
            if (index >= EXCERPT_LINES) break;
        }
        return lines;
    }

    private Map<String, Object> materialView(Map<String, Object> row) {
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
        item.put("source", row.get("source"));
        if (row.get("note") != null) item.put("note", row.get("note"));
        if (row.get("stored_result") != null) item.put("stored_result", row.get("stored_result"));
        if (row.get("reviewed_by") != null) item.put("reviewed_by", row.get("reviewed_by"));
        if (row.get("reviewed_at") != null) item.put("reviewed_at", row.get("reviewed_at"));
        return item;
    }

    private Map<String, Object> fileView(String fileName, String fileType, MaterialTextReader.Extracted extracted,
                                        Path stored, String at) {
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("file_name", fileName);
        view.put("file_type", fileType);
        view.put("pages", extracted == null ? 0 : extracted.pages());
        view.put("size_kb", stored == null ? 0 : (int) (fileSize(stored) / 1024));
        view.put("char_count", extracted == null ? 0 : extracted.charCount());
        view.put("preview_note", extracted == null ? "SOP 模板填报，没有上传原件" : blank(extracted.note(), "正文已完整读取"));
        view.put("url", stored == null ? null : stored.toString());
        view.put("uploaded_by", actor.name());
        view.put("uploaded_at", at == null ? now() : at);
        return view;
    }

    private void refreshMaterialStatus(String code, String at, String result) {
        long pending = countItems(code, "待审核");
        long storedCount = countItems(code, "已入库");
        String status = pending > 0 ? "待审核" : (storedCount > 0 ? "已审核" : "已驳回");
        sql.update("UPDATE course_material SET status = ?, reviewed_by = ?, reviewed_at = ?, stored_result = ? WHERE code = ?",
            status, actor.name(), at, result, code);
    }

    private String materialStatus(String code) {
        Map<String, Object> row = sql.row("SELECT status FROM course_material WHERE code = ?", code);
        return row == null ? "待审核" : String.valueOf(row.get("status"));
    }

    private long countItems(String code, String status) {
        return sql.count("SELECT COUNT(*) FROM material_item WHERE material_code = ? AND status = ?", code, status);
    }

    private Path store(String code, String fileName, byte[] bytes) {
        try {
            Path dir = Path.of(materialDir);
            Files.createDirectories(dir);
            String safe = fileName.replaceAll("[\\\\/:*?\"<>|]", "_");
            Path target = dir.resolve(code + "_" + safe);
            Files.write(target, bytes);
            return target;
        } catch (Exception error) {
            log.warn("资料原件留档失败（不影响识别与入库）：{}", error.getMessage());
            return null;
        }
    }

    private static long fileSize(Path path) {
        try {
            return Files.exists(path) ? Files.size(path) : 0;
        } catch (Exception error) {
            return 0;
        }
    }

    /** 员工端看到的题目出处：SOP 生成的写 SOP，文档导入的写文件名。 */
    private static String sourceLabel(String title, String fileName, String materialType) {
        return "SOP".equals(materialType) || "SOP 资料".equals(materialType)
            ? "SOP：" + title
            : "文档导入：《" + fileName + "》";
    }

    private static int parseLevel(String level) {
        if (level == null) return 2;
        String digits = level.replaceAll("[^0-9]", "");
        return digits.isEmpty() ? 2 : Math.min(3, Math.max(1, Integer.parseInt(digits)));
    }

    private static List<String> lines(String text) {
        List<String> rows = new ArrayList<>();
        if (text == null) return rows;
        for (String piece : text.split("\n")) {
            String line = piece.strip().replaceAll("^[0-9]+[.、)）]\\s*", "");
            if (line.length() >= 4) rows.add(line);
        }
        return rows;
    }

    private static List<String> stringList(List<?> value) {
        List<String> items = new ArrayList<>();
        for (Object item : value) {
            items.add(String.valueOf(item));
        }
        return items;
    }

    private static double confidence(List<MaterialAgent.Candidate> candidates) {
        if (candidates.isEmpty()) return 0;
        double sum = 0;
        for (MaterialAgent.Candidate candidate : candidates) sum += candidate.confidence();
        return Math.round(sum / candidates.size() * 100) / 100.0;
    }

    private static Double totalHours(List<MaterialAgent.Candidate> candidates) {
        double hours = 0;
        for (MaterialAgent.Candidate candidate : candidates) hours += candidate.hours();
        return Math.round(hours * 10) / 10.0;
    }

    private static String trimHours(double hours) {
        return hours == Math.floor(hours) ? String.valueOf((int) hours) : String.valueOf(hours);
    }

    private static double number(Object value, double fallback) {
        return value instanceof Number number ? number.doubleValue() : fallback;
    }

    private static String string(Object value, String fallback) {
        return value == null || String.valueOf(value).isBlank() ? fallback : String.valueOf(value);
    }

    private static String baseName(String fileName) {
        int dot = fileName.lastIndexOf('.');
        return dot > 0 ? fileName.substring(0, dot) : fileName;
    }

    private static String value(String text, String fallback) {
        return text == null || text.isBlank() ? fallback : text.strip();
    }

    private static String blank(String text, String fallback) {
        return text == null || text.isBlank() ? fallback : text;
    }

    private static String now() {
        return ZonedDateTime.now(ZoneId.of("Asia/Shanghai")).format(STAMP);
    }

    private void audit(String category, String action, String target, String result) {
        long next = sql.count("SELECT COALESCE(MAX(id), 0) + 1 FROM audit_log");
        sql.update("INSERT INTO audit_log (id, occurred_at, actor, actor_role, category, action, target, result, ip) "
            + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            next, now(), actor.name(), actor.roleName(), category, action, target, result, AUDIT_IP);
    }
}
