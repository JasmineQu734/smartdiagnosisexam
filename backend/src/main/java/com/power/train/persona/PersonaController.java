package com.power.train.persona;

import static com.power.train.support.ApiResponse.ok;
import static com.power.train.support.ApiResponse.row;

import com.power.train.store.DiagnosisStore;
import com.power.train.store.PersonalStore;
import com.power.train.support.Users;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 员工个人模块（技能雷达之外）与组长班组报告模块。
 * 自画像、能力、记忆、成长、建议都从 MySQL 读；个性化诊断结论落在 diagnosis_result（scope=PERSONAL）。
 */
@RestController
@RequestMapping("/api/v1")
public class PersonaController {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final PersonalStore personal;
    private final DiagnosisStore diagnoses;
    private final RuntimeMemoryStore memoryStore;
    private final PersonalDiagnosisService diagnosis;

    public PersonaController(PersonalStore personal, DiagnosisStore diagnoses, RuntimeMemoryStore memoryStore,
                             PersonalDiagnosisService diagnosis) {
        this.personal = personal;
        this.diagnoses = diagnoses;
        this.memoryStore = memoryStore;
        this.diagnosis = diagnosis;
    }

    // ---- 2. 个人自画像：职业发展画像，不涉及心理隐私 ----

    @GetMapping("/personal/self-portrait")
    public Map<String, Object> selfPortrait() {
        return ok(personal.selfPortrait());
    }

    // ---- 3. 个人能力：硬技能（employee_skill）+ 软技能 / 安全 / 实操 / 考试 / 证书 ----

    @GetMapping("/personal/abilities")
    public Map<String, Object> abilities(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.abilities(Users.account(user)));
    }

    // ---- 4. 记忆展示：种子记忆 + Agent / 练习实时写入的记忆（memory_item） ----

    @GetMapping("/personal/memories")
    public Map<String, Object> memories(@RequestHeader(value = "X-User", required = false) String user) {
        return ok(personal.memories(Users.account(user)));
    }

    // ---- 5. 成长轨迹：技能等级、证书、考试、任务、培训、安全、晋升准备度 ----

    @GetMapping("/personal/growth")
    public Map<String, Object> growth() {
        return ok(personal.growth());
    }

    // ---- 6. 差距与建议（个人学习 Agent 基线口径） ----

    @GetMapping("/personal/advice")
    public Map<String, Object> advice() {
        return ok(personal.advice());
    }

    // ---- 7. 个性化 Agent 诊断：读库取事实 + 大模型出结论（不合契约则回退内置结论），结论写库并同步到记忆展示 ----

    @PostMapping("/personal/agent-diagnose")
    public Map<String, Object> runDiagnosis(@RequestHeader(value = "X-User", required = false) String user) {
        String me = Users.account(user);
        ZonedDateTime now = ZonedDateTime.now(ZoneId.of("Asia/Shanghai"));
        String ranAt = now.format(STAMP);
        String diagnosisId = "DIA-" + now.format(DAY) + "-"
            + String.format("%03d", diagnoses.nextSequence(DiagnosisStore.PERSONAL));
        Map<String, Object> payload = diagnosis.diagnose(me, diagnosisId, ranAt);
        diagnoses.save(DiagnosisStore.PERSONAL, diagnosisId, ranAt, payload);
        appendDiagnosisMemory(me, payload, ranAt);
        return ok(payload);
    }

    /** 读取最近一次诊断报告：换页回来不丢结论；没运行过则给出引导。 */
    @GetMapping("/personal/agent-diagnose/latest")
    public Map<String, Object> latestDiagnosis() {
        Map<String, Object> latest = diagnoses.latest(DiagnosisStore.PERSONAL);
        if (latest == null) {
            return ok(row("has_diagnosis", false,
                "hint", "还没有运行过个性化诊断：到“差距与建议”点“运行个性化 Agent 诊断”，即可实时生成并同步到各板块"));
        }
        Map<String, Object> payload = new LinkedHashMap<>(latest);
        payload.put("has_diagnosis", true);
        return ok(payload);
    }

    /** 诊断结果回写记忆库：记忆展示 / 成长轨迹等板块随即可见，体现“实时更新到其他板块”。 */
    private void appendDiagnosisMemory(String username, Map<String, Object> payload, String ranAt) {
        Map<?, ?> verdict = (Map<?, ?>) payload.get("verdict");
        memoryStore.addAdvice(username, "个性化 Agent 诊断：" + verdict.get("headline"),
            String.valueOf(payload.get("summary")), List.of("个性化诊断", "复合型人才", "实时更新"),
            "个人学习 Agent", ranAt);
    }

    // ---- 组长：班组实操报告（每次实操活动都必须上传报告，作为公司运行诊断的依据之一） ----

    @GetMapping("/team/overview")
    public Map<String, Object> teamOverview() {
        List<Map<String, Object>> rows = personal.teamReports();
        long missing = rows.stream().filter(item -> "MISSING".equals(item.get("status"))).count();
        long abnormal = rows.stream().filter(item -> "超限".equals(item.get("judgment"))).count();
        Map<String, Object> profile = personal.teamProfile();
        return ok(row(
            "team_name", profile.getOrDefault("team_name", "变电运维一班"),
            "leader", profile.getOrDefault("leader", ""),
            "members", profile.getOrDefault("members", 0),
            "reports_required", rows.size(), "reports_submitted", rows.size() - missing,
            "reports_missing", missing, "abnormal", abnormal,
            "pending_confirm", profile.getOrDefault("pending_confirm", 0),
            "note", profile.getOrDefault("note", "")));
    }

    @GetMapping("/team/reports")
    public Map<String, Object> teamReportsView() {
        return ok(personal.teamReports());
    }
}
