package com.power.train.rbac;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 认证闸门：/api/v1 下除登录、登出、健康检查外，一律要求携带服务端签发的令牌。
 *
 * 身份不再从请求头读——令牌里的账号与角色由服务端签发，客户端改不动。
 * 校验通过后把身份包进 RequestWrapper，下游的 RoleInterceptor / Actor / 各 Controller
 * 继续按原来的 X-User / X-Role 读法取值，不必逐个改方法签名；
 * 而客户端自己塞的 X-User / X-Role 会被丢弃，伪造身份这条路径就此失效。
 */
@Component
public class AuthFilter extends OncePerRequestFilter {

    /** 免鉴权路径：登录、登出与健康检查（容器探活与前端探活都要能匿名调）。 */
    private static final List<String> PUBLIC_PATHS =
        List.of("/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/health");

    private final AuthToken tokens;
    private final ObjectMapper objectMapper;

    public AuthFilter(AuthToken tokens, ObjectMapper objectMapper) {
        this.tokens = tokens;
        this.objectMapper = objectMapper;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
        throws ServletException, IOException {
        String path = request.getRequestURI();
        // 预检请求不带业务语义，放行交给下游按原样处理
        if (!path.startsWith("/api/v1/")
            || PUBLIC_PATHS.contains(path)
            || "OPTIONS".equalsIgnoreCase(request.getMethod())) {
            chain.doFilter(request, response);
            return;
        }

        AuthToken.Principal principal = tokens.verify(AuthToken.fromHeader(request.getHeader("Authorization")));
        if (principal == null) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json;charset=UTF-8");
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("code", 401);
            body.put("message", "未认证或登录已过期，请重新登录");
            body.put("data", Map.of());
            body.put("trace_id", UUID.randomUUID().toString());
            response.getWriter().write(objectMapper.writeValueAsString(body));
            return;
        }

        chain.doFilter(new IdentityRequestWrapper(request, principal), response);
    }

    /** 把令牌里的身份投影成 X-User / X-Role 供下游读取，客户端自带的同名头被忽略。 */
    private static final class IdentityRequestWrapper extends HttpServletRequestWrapper {

        private final AuthToken.Principal principal;

        IdentityRequestWrapper(HttpServletRequest request, AuthToken.Principal principal) {
            super(request);
            this.principal = principal;
        }

        @Override
        public String getHeader(String name) {
            if ("X-User".equalsIgnoreCase(name)) return principal.username();
            if ("X-Role".equalsIgnoreCase(name)) return principal.role();
            return super.getHeader(name);
        }

        @Override
        public Enumeration<String> getHeaders(String name) {
            String value = getHeader(name);
            return value == null ? Collections.emptyEnumeration() : Collections.enumeration(List.of(value));
        }
    }
}