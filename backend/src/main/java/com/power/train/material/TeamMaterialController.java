package com.power.train.material;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.support.Actor;
import com.power.train.store.DatasetStore;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 班组侧资料入口（/team/** 由 RoleInterceptor 限定为班组长）：
 * 1）导入文档：上传 PDF / Word / 文本 / 表格 / 演示文稿，Agent 读正文识别题干与答案；
 * 2）SOP 模板填报：判定标准 / 考核要点 / 作业步骤 → 候选题；
 * 两条路径都只生成「待审核」候选题，管理员审核通过后才写入题库 / 课程库，员工刷题才抽得到。
 */
@RestController
@RequestMapping("/api/v1")
public class TeamMaterialController {

    public record SopRequest(String sop_name, String skill, String level, String steps, String criteria,
                             String points, String risks) {}

    private final MaterialImportService service;
    private final DatasetStore datasets;
    private final Actor actor;

    public TeamMaterialController(MaterialImportService service, DatasetStore datasets, Actor actor) {
        this.service = service;
        this.datasets = datasets;
        this.actor = actor;
    }

    /** 导入说明口径（存在 dataset_meta.team.material.import，可随时在库里维护）。 */
    @GetMapping("/team/materials/template")
    public Map<String, Object> template() {
        return ok(datasets.meta("team.material.import"));
    }

    /** 导入文档：multipart 上传原件 + 入库目标 / 技能 / 等级 / 版本 / 备注。 */
    @PostMapping(value = "/team/materials/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> upload(@RequestParam(value = "file", required = false) MultipartFile file,
                                      @RequestParam(value = "target", required = false) String target,
                                      @RequestParam(value = "skill", required = false) String skill,
                                      @RequestParam(value = "level", required = false) String level,
                                      @RequestParam(value = "version", required = false) String version,
                                      @RequestParam(value = "title", required = false) String title,
                                      @RequestParam(value = "note", required = false) String note) {
        try {
            return ok(service.uploadDocument(file, target, skill, level, version, title, note));
        } catch (MaterialImportService.MaterialImportException error) {
            return row("code", 40001, "message", error.getMessage(),
                "data", row("field_errors", error.fieldErrors()), "trace_id", UUID.randomUUID().toString());
        }
    }

    /** 本班组上传的资料与审核进度。 */
    @GetMapping("/team/materials")
    public Map<String, Object> materials() {
        List<Map<String, Object>> items = service.batches();
        long pending = items.stream().filter(item -> "待审核".equals(item.get("status"))).count();
        long stored = items.stream().mapToLong(item -> ((Number) item.getOrDefault("stored_items", 0)).longValue()).sum();
        return ok(row(
            "summary", row("total", items.size(), "pending_review", pending, "stored_items", stored,
                "note", "导入的资料先由 Agent 识别候选题，再等管理员审核；通过后写入题库 / 课程库，员工刷题即可抽到"),
            "items", items));
    }

    /** 单批资料详情：原件信息、原件摘录、候选题及每条审核状态（含已入库的题号）。 */
    @GetMapping("/team/materials/{code}")
    public Map<String, Object> detail(@PathVariable String code) {
        Map<String, Object> detail = service.detail(code);
        if (detail == null) {
            return ok(row("found", false, "message", "资料不存在：" + code));
        }
        detail.put("found", true);
        return ok(detail);
    }

    /** SOP 模板：字段定义存在 dataset_meta.team.sop.template。 */
    @GetMapping("/team/sop/template")
    public Map<String, Object> sopTemplate() {
        return ok(datasets.meta("team.sop.template"));
    }

    /** SOP 模板填报：校验后由 Agent 生成候选题，提交管理员审核（不再直接写题库）。 */
    @PostMapping("/team/sop/generate")
    public Map<String, Object> generateSop(@RequestBody(required = false) SopRequest request) {
        SopRequest form = request == null ? new SopRequest(null, null, null, null, null, null, null) : request;
        try {
            Map<String, Object> result = service.submitSop(form.sop_name(), form.skill(), form.level(), form.steps(),
                form.criteria(), form.points(), form.risks());
            result.put("submitted_by", actor.name());
            return ok(result);
        } catch (MaterialImportService.MaterialImportException error) {
            return row("code", 40001, "message", error.getMessage(),
                "data", row("field_errors", error.fieldErrors()), "trace_id", UUID.randomUUID().toString());
        }
    }
}