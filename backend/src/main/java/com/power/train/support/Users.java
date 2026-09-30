package com.power.train.support;

/**
 * 请求头 X-User 的账号口径：三个个人侧入口（ApiController / PracticeController / PersonaController）
 * 都要「带上了就用、没带就按演示账号兜底」，默认值只在这里定义一份，避免三处各写一遍。
 */
public final class Users {

    /** 演示账号：请求头没带 X-User 时使用（MVP 尚未接入真实登录态）。 */
    public static final String DEFAULT = "zhangwei";

    private Users() {
    }

    /** 取请求头里的账号名；为空则回落到演示账号。 */
    public static String account(String header) {
        return header == null || header.isBlank() ? DEFAULT : header.trim();
    }
}
