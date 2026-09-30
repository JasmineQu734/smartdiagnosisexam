package com.power.train.report;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

/**
 * 实操报告填报表单。字段的必填与格式限制同时用于前端提示和后端校验，
 * 保证 AI 解析时拿到的文本结构一致（时间 + 位置 + 现象 + 数值 + 已采取措施）。
 */
public record ReportForm(
    @JsonProperty("member") @Size(max = 32, message = "执行组员姓名最长 32 字") String member,
    @JsonProperty("detected_at") @NotBlank(message = "检测时间不能为空") String detectedAt,
    @JsonProperty("shift") @NotBlank(message = "班次不能为空") String shift,
    @JsonProperty("location") @NotBlank(message = "检测地点不能为空")
    @Size(min = 4, max = 120, message = "检测地点需 4-120 字，需写到站所与设备间隔") String location,
    @JsonProperty("gas_type") @NotBlank(message = "气体类型不能为空") String gasType,
    @JsonProperty("gas_value") @NotNull(message = "检测数值不能为空")
    @DecimalMin(value = "0", message = "检测数值不能为负数")
    @DecimalMax(value = "1000000", message = "检测数值超出合理范围") BigDecimal gasValue,
    @JsonProperty("threshold") @NotNull(message = "报警阈值不能为空")
    @DecimalMin(value = "0", message = "报警阈值不能为负数") BigDecimal threshold,
    @JsonProperty("phenomenon") @NotBlank(message = "异常现象描述不能为空")
    @Size(min = 15, max = 300, message = "异常现象描述需 15-300 字，按“时间 + 位置 + 现象 + 数值 + 已采取措施”填写") String phenomenon,
    @JsonProperty("measures") @Size(max = 200, message = "已采取措施不超过 200 字") String measures,
    /**
     * SOP 执行情况：可枚举的三态，归因（人工问题 / 技能问题）与资料校对都靠它拿结构化证据。
     * 必填：这一栏空着，归因就只能退回「未知」，等于报告里最重要的过程证据没记。
     */
    @JsonProperty("sop_status") @NotBlank(message = "SOP 执行情况不能为空：请选择已按 SOP 执行 / 未按 SOP 执行 / 本次无对应 SOP")
    @Pattern(regexp = "FOLLOWED|DEVIATED|NOT_APPLICABLE",
        message = "SOP 执行情况取值必须是 FOLLOWED（已按 SOP）/ DEVIATED（未按 SOP）/ NOT_APPLICABLE（本次无对应 SOP）") String sopStatus,
    @JsonProperty("sop_deviation") @Size(max = 200, message = "SOP 偏差说明不超过 200 字") String sopDeviation) {

    @AssertTrue(message = "异常现象描述需包含具体时间或数值，例如 09:20、0.35MPa、1250ppm")
    public boolean isPhenomenonHasNumber() {
        return phenomenon == null || phenomenon.isBlank() || phenomenon.matches(".*[0-9０-９].*");
    }

    /** 选「未按 SOP 执行」必须写明偏差：没有偏差说明的「未按 SOP」，在归因里就是一句无法核对的话。 */
    @AssertTrue(message = "选「未按 SOP 执行」时必须填写 SOP 偏差说明，写清哪一步没按规程做")
    public boolean isSopDeviationPresent() {
        return !"DEVIATED".equals(sopStatus) || (sopDeviation != null && !sopDeviation.isBlank());
    }
}
