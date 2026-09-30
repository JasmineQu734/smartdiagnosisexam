package com.power.train.rbac;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** 四类身份：员工、组长（本身也是员工）、公司上级（老总）、系统管理员。 */
public final class RoleGuard {

    public static final String EMPLOYEE = "EMPLOYEE";
    public static final String TEAM_LEAD = "TEAM_LEAD";
    public static final String EXECUTIVE = "EXECUTIVE";
    public static final String ADMIN = "ADMIN";

    private RoleGuard() {}

    /** 归一化角色：兼容旧前端的 DEPARTMENT_MANAGER，未识别一律按普通员工处理。 */
    public static String normalize(String role) {
        if (role == null || role.isBlank()) return EMPLOYEE;
        return switch (role.trim().toUpperCase()) {
            case "TEAM_LEAD", "TEAMLEAD", "LEAD", "DEPARTMENT_MANAGER" -> TEAM_LEAD;
            case "EXECUTIVE", "BOSS" -> EXECUTIVE;
            case "ADMIN" -> ADMIN;
            default -> EMPLOYEE;
        };
    }

    public static boolean allows(String role, String... allowed) {
        String normalized = normalize(role);
        for (String item : allowed) {
            if (normalize(item).equals(normalized)) return true;
        }
        return false;
    }

    /** 越权访问统一返回 40301，前端据此提示“当前身份无权限”。 */
    public static Map<String, Object> forbidden(String role, String scopeLabel) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", 40301);
        body.put("message", "当前身份无权访问该数据，仅限" + scopeLabel);
        body.put("data", Map.of("role", normalize(role), "scope", scopeLabel));
        body.put("trace_id", UUID.randomUUID().toString());
        return body;
    }
}
