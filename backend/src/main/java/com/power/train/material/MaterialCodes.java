package com.power.train.material;

import com.power.train.store.Sql;
import java.util.Map;

/**
 * 课程资料台账的编号口径：管理员上传与组长导入 / SOP 填报两条入口共用同一套生成规则。
 * 这两条入口曾各写一份实现（连序号算法都不一样），编号一旦算岔就出现重号或跳号。
 */
public final class MaterialCodes {

    private MaterialCodes() {
    }

    /** 资料编号 MAT-001、MAT-002…：先按现有条数定起点，再逐号检查，撞号就往后挪。 */
    public static String nextMaterialCode(Sql sql) {
        int sequence = (int) sql.count("SELECT COUNT(*) FROM course_material WHERE code LIKE 'MAT-%'") + 1;
        String code = "MAT-" + String.format("%03d", sequence);
        while (sql.count("SELECT COUNT(*) FROM course_material WHERE code = ?", code) > 0) {
            sequence++;
            code = "MAT-" + String.format("%03d", sequence);
        }
        return code;
    }

    /** 技能名转技能编码；技能表里查不到时回落到通用编码 SK-GEN，不让资料挂空编码。 */
    public static String skillCodeOf(Sql sql, String skill) {
        Map<String, Object> row = sql.row(
            "SELECT code FROM skill WHERE name = ? ORDER BY sort_no, code LIMIT 1", skill.strip());
        return row == null ? "SK-GEN" : String.valueOf(row.get("code"));
    }

    /**
     * 新增台账行排到末尾用的序号：表名走白名单（不拼接调用方给的字符串），
     * 取该列现有最大序号 + 1，删过历史行也不会与已有行撞号。
     */
    public static int nextSortNo(Sql sql, String table) {
        String name = switch (table) {
            case "course", "question_bank", "course_material" -> table;
            default -> throw new IllegalArgumentException("未知表名：" + table);
        };
        return (int) sql.count("SELECT COALESCE(MAX(sort_no), 0) + 1 FROM " + name);
    }
}
