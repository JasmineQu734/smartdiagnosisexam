package com.power.train.support;

import java.math.BigDecimal;

/**
 * 文本与数值的展示口径：同一个数字、同一句话在全系统只有这一份转法，
 * 避免「12.00 在 A 页面显示 12、在 B 页面显示 12.00」这类分叉。
 *
 * 只放纯函数，不依赖 Spring，也不需要请求上下文；数据库行里的布尔仍走 Sql.bool，
 * 这里的 {@link #truthy} 给「非数据库行」的值（规则事实、模型返回）用。
 */
public final class Texts {

    private Texts() {
    }

    /** null 当空串、首尾空白去掉：拼提示词、比对字段、拼展示文案全系统只有这一套口径。 */
    public static String text(Object value) {
        return value == null ? "" : String.valueOf(value).strip();
    }

    /** 空文本一律显示为破折号，避免页面上出现空白格。 */
    public static String orDash(Object value) {
        String result = text(value);
        return result.isBlank() ? "—" : result;
    }

    /** 数值展示：去掉多余的零（12.00 → 12、0.350 → 0.35），null 显示为空串。 */
    public static String plain(BigDecimal value) {
        return value == null ? "" : value.stripTrailingZeros().toPlainString();
    }

    /** 把值转成数值：BigDecimal / 数字 / 数字文本都认，其余返回 null（不猜）。 */
    public static BigDecimal decimal(Object raw) {
        if (raw instanceof BigDecimal value) return value;
        if (raw instanceof Number value) return new BigDecimal(value.toString());
        if (raw instanceof String value && !value.isBlank()) {
            try {
                return new BigDecimal(value.trim());
            } catch (NumberFormatException ignored) {
                return null;
            }
        }
        return null;
    }

    /** 小数型取值，取不到或类型不对时用 fallback。 */
    public static double number(Object value, double fallback) {
        return value instanceof Number number ? number.doubleValue() : fallback;
    }

    /** 整数型取值，取不到或类型不对时用 fallback。 */
    public static int number(Object value, int fallback) {
        return value instanceof Number number ? number.intValue() : fallback;
    }

    /** 长整数型取值，取不到或类型不对时用 fallback。 */
    public static long number(Object value, long fallback) {
        return value instanceof Number number ? number.longValue() : fallback;
    }

    /**
     * 布尔口径：Boolean、数字（0 / 1）与文本（"1" / "true" / "Y"）都认。
     * 与 Sql.bool 同一套判定，只是这里不经过数据库行。
     */
    public static boolean truthy(Object raw) {
        if (raw == null) return false;
        if (raw instanceof Boolean value) return value;
        if (raw instanceof Number value) return value.intValue() != 0;
        String value = String.valueOf(raw).trim();
        return "1".equals(value) || "true".equalsIgnoreCase(value) || "Y".equalsIgnoreCase(value);
    }

    /**
     * 摘要：去掉首尾空白，超过 limit 个字符就截断并加省略号。
     * 大模型提示词与归因留痕的 input_excerpt 共用这一套长度口径，避免一处截断、一处全文外发。
     */
    public static String excerpt(String text, int limit) {
        if (text == null) return "";
        String trimmed = text.strip();
        return trimmed.length() <= limit ? trimmed : trimmed.substring(0, limit) + "…";
    }
}
