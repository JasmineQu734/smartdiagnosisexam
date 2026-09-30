package com.power.train.support;

import com.power.train.store.Sql;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

/**
 * 当前请求的操作人：从 X-User 头取账号，再查 app_user 取展示名与角色名。
 * 审计留痕、开考人、审核人等字段据此记录真实操作者，不再写死一个名字。
 */
@Component
public class Actor {

    private static final String DEFAULT_ACTOR = "系统管理员";

    private final Sql sql;

    public Actor(Sql sql) {
        this.sql = sql;
    }

    /** 当前操作人展示名；无请求上下文或账号查不到时回落到默认操作人。 */
    public String name() {
        String username = username();
        if (username == null) {
            return DEFAULT_ACTOR;
        }
        Map<String, Object> row = sql.row("SELECT display_name FROM app_user WHERE username = ?", username);
        return row == null ? DEFAULT_ACTOR : String.valueOf(row.get("display_name"));
    }

    /** 当前操作人的角色名（审计留痕用）。 */
    public String roleName() {
        String username = username();
        if (username == null) {
            return DEFAULT_ACTOR;
        }
        Map<String, Object> row = sql.row("SELECT role_name FROM app_user WHERE username = ?", username);
        return row == null ? DEFAULT_ACTOR : String.valueOf(row.get("role_name"));
    }

    /** 当前请求头里的账号名；没有请求上下文（如启动期）时为 null。 */
    public String username() {
        if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attributes) {
            String header = attributes.getRequest().getHeader("X-User");
            if (header != null && !header.isBlank()) {
                return header.trim();
            }
        }
        return null;
    }
}
