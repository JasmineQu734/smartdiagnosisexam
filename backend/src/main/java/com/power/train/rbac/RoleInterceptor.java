package com.power.train.rbac;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 按路径前缀统一鉴权，避免每个接口各写一套判断：
 * /personal/** 与 /exams/** 仅员工与组长、/team/** 仅组长（/tasks/** 检测报告填报）、/management/** 与 /exec/** 仅老总、
 * /admin/** 与 /rules/** 仅系统管理员（规则引擎只给管理员测试，前端不直接调用）、
 * /reports/** 仅员工与组长、/agent/** 按 agent_type 分派（personal 员工+组长 / management 老总 / report 组长 / 其他仅管理员）。
 * 注意：这里只做「角色够不够」，身份是否可信由 AuthFilter 前置把关——请求头里的角色是令牌投影出来的，客户端伪造无效。
 */
@Component
public class RoleInterceptor implements HandlerInterceptor {

    private record Scope(List<String> roles, String label) {}

    private final ObjectMapper objectMapper;

    public RoleInterceptor(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) return true;
        String path = request.getRequestURI();
        Scope scope = scopeOf(path);
        if (scope == null) return true;
        String role = request.getHeader("X-Role");
        if (RoleGuard.allows(role, scope.roles().toArray(String[]::new))) return true;
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(objectMapper.writeValueAsString(RoleGuard.forbidden(role, scope.label())));
        return false;
    }

    private Scope scopeOf(String path) {
        if (path.startsWith("/api/v1/personal/")) {
            return new Scope(List.of(RoleGuard.EMPLOYEE, RoleGuard.TEAM_LEAD), "员工本人（含组长）");
        }
        // 进入考试 / 交卷属于员工本人操作，老总与管理员不参与答题
        if (path.startsWith("/api/v1/exams/")) {
            return new Scope(List.of(RoleGuard.EMPLOYEE, RoleGuard.TEAM_LEAD), "员工本人（含组长）");
        }
        if (path.startsWith("/api/v1/team/")) {
            return new Scope(List.of(RoleGuard.TEAM_LEAD), "班组长");
        }
        // 检测报告只由班组长填报；普通员工只看报告，不进入填报通道
        if (path.startsWith("/api/v1/tasks/")) {
            return new Scope(List.of(RoleGuard.TEAM_LEAD), "班组长（检测报告填报）");
        }
        if (path.startsWith("/api/v1/management/") || path.startsWith("/api/v1/exec/")) {
            return new Scope(List.of(RoleGuard.EXECUTIVE), "公司上级（老总）");
        }
        if (path.startsWith("/api/v1/admin/")) {
            return new Scope(List.of(RoleGuard.ADMIN), "系统管理员");
        }
        // 规则引擎只给系统管理员做规则核对与试算，前端不直接调用
        if (path.startsWith("/api/v1/rules")) {
            return new Scope(List.of(RoleGuard.ADMIN), "系统管理员");
        }
        // 检测报告：员工看与本人相关的报告，组长看本班组；填报与下载都在这组前缀下
        if (path.startsWith("/api/v1/reports")) {
            return new Scope(List.of(RoleGuard.EMPLOYEE, RoleGuard.TEAM_LEAD), "员工本人（含组长）");
        }
        // 三个 Agent 桩按 agent_type 分派角色，未知类型只给管理员
        if (path.startsWith("/api/v1/agent/personal/")) {
            return new Scope(List.of(RoleGuard.EMPLOYEE, RoleGuard.TEAM_LEAD), "员工本人（含组长）");
        }
        if (path.startsWith("/api/v1/agent/management/")) {
            return new Scope(List.of(RoleGuard.EXECUTIVE), "公司上级（老总）");
        }
        if (path.startsWith("/api/v1/agent/report/")) {
            return new Scope(List.of(RoleGuard.TEAM_LEAD), "班组长");
        }
        if (path.startsWith("/api/v1/agent/")) {
            return new Scope(List.of(RoleGuard.ADMIN), "系统管理员");
        }
        return null;
    }
}
