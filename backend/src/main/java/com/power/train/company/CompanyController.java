package com.power.train.company;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.store.DatasetStore;
import com.power.train.store.DiagnosisStore;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 公司上级（老总）与系统管理员视图：
 * /exec/** 仅老总可见（全员总数据 + 公司运行诊断 Agent），/admin/** 仅系统管理员可见（全公司数据）。
 * 驾驶舱口径、技能矩阵、培训看板等展示数据取自 dataset_meta；运行诊断结论落在 diagnosis_result（scope=EXEC）。
 */
@RestController
@RequestMapping("/api/v1")
public class CompanyController {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final DatasetStore datasets;
    private final DiagnosisStore diagnoses;
    private final ExecDiagnosisService diagnosis;

    public CompanyController(DatasetStore datasets, DiagnosisStore diagnoses, ExecDiagnosisService diagnosis) {
        this.datasets = datasets;
        this.diagnoses = diagnoses;
        this.diagnosis = diagnosis;
    }

    // ---- 老总：全公司总数据 ----

    @GetMapping("/exec/company-overview")
    public Map<String, Object> companyOverview() {
        return ok(datasets.meta("exec.company-overview"));
    }

    /** 诊断基线口径：内容取自库，保证「输入」和「结论」同一份说法。 */
    @GetMapping("/exec/diagnosis")
    public Map<String, Object> diagnosis() {
        return ok(datasets.meta("exec.diagnosis"));
    }

    /** 运行诊断：读库取事实 + 大模型出结论（不合契约则回退内置结论），并把本次结论写入 diagnosis_result。 */
    @PostMapping("/exec/agent-diagnose")
    public Map<String, Object> runDiagnosis() {
        ZonedDateTime now = ZonedDateTime.now(ZoneId.of("Asia/Shanghai"));
        String ranAt = now.format(STAMP);
        String diagnosisId = "EXE-DIA-" + now.format(DAY) + "-"
            + String.format("%03d", diagnoses.nextSequence(DiagnosisStore.EXEC));
        Map<String, Object> payload = diagnosis.diagnose(diagnosisId, ranAt);
        diagnoses.save(DiagnosisStore.EXEC, diagnosisId, ranAt, payload);
        return ok(payload);
    }

    /** 读取最近一次诊断报告：老总换页回来不丢结论；没运行过则给出引导。 */
    @GetMapping("/exec/agent-diagnose/latest")
    public Map<String, Object> latestDiagnosis() {
        Map<String, Object> latest = diagnoses.latest(DiagnosisStore.EXEC);
        if (latest == null) {
            return ok(row("has_diagnosis", false,
                "hint", "还没有运行过公司运行诊断：到「运行诊断 Agent」点「点击运行诊断 Agent」，即可实时生成诊断报告"));
        }
        Map<String, Object> payload = new LinkedHashMap<>(latest);
        payload.put("has_diagnosis", true);
        return ok(payload);
    }

    // ---- 老总：全公司技能矩阵与培训看板 ----

    @GetMapping("/exec/skill-matrix")
    public Map<String, Object> skillMatrix() {
        return ok(datasets.meta("exec.skill-matrix"));
    }

    @GetMapping("/exec/training-board")
    public Map<String, Object> trainingBoard() {
        return ok(datasets.meta("exec.training-board"));
    }

    // ---- 系统管理员：全公司数据 ----

    @GetMapping("/admin/overview")
    public Map<String, Object> adminOverview() {
        return ok(datasets.meta("admin.overview"));
    }

    @GetMapping("/admin/employees")
    public Map<String, Object> adminEmployees() {
        return ok(datasets.value("admin.employees"));
    }
}
