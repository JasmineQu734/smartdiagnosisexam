package com.power.train.rbac;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 登录令牌：服务端用 HMAC-SHA256 签发，账号与角色写在令牌里，客户端改不动。
 *
 * 形状 v1.<base64url(payload)>.<签名>，payload 是「账号 + 角色 + 过期时间」。
 * 不引入 jjwt 之类的依赖，够 MVP 用；生产要换成内网统一身份（或 Spring Security + 刷新令牌）时只换本类实现。
 */
@Component
public class AuthToken {

    /** 令牌里携带的身份：账号与角色都来自服务端签发的那一刻，后续不再信任请求头。 */
    public record Principal(String username, String role) {}

    private static final String ALGORITHM = "HmacSHA256";
    private static final String PREFIX = "v1";

    private final byte[] secret;
    private final long ttlSeconds;

    public AuthToken(@Value("${auth.secret:power-train-demo-secret}") String secret,
                     @Value("${auth.ttl-hours:12}") long ttlHours) {
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
        this.ttlSeconds = Math.max(ttlHours, 1) * 3600L;
    }

    /** 签发：账号与角色取自 app_user，过期时间由配置决定（默认 12 小时，够一次演示）。 */
    public String issue(String username, String role) {
        long expiresAt = Instant.now().getEpochSecond() + ttlSeconds;
        String payload = username + "\n" + RoleGuard.normalize(role) + "\n" + expiresAt;
        String encoded = Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes(StandardCharsets.UTF_8));
        return PREFIX + "." + encoded + "." + sign(encoded);
    }

    /** 校验：形状不对、签名不对或已过期一律返回 null，调用方据此回 401。 */
    public Principal verify(String token) {
        if (token == null || token.isBlank()) return null;
        String[] parts = token.trim().split("\\.");
        if (parts.length != 3 || !PREFIX.equals(parts[0])) return null;
        byte[] expected = sign(parts[1]).getBytes(StandardCharsets.UTF_8);
        if (!MessageDigest.isEqual(expected, parts[2].getBytes(StandardCharsets.UTF_8))) return null;
        String payload;
        try {
            payload = new String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException error) {
            return null;
        }
        String[] fields = payload.split("\n");
        if (fields.length != 3) return null;
        long expiresAt;
        try {
            expiresAt = Long.parseLong(fields[2].trim());
        } catch (NumberFormatException error) {
            return null;
        }
        if (expiresAt <= Instant.now().getEpochSecond()) return null;
        return new Principal(fields[0], fields[1]);
    }

    /** 从 Authorization 头取令牌：接受 Bearer 前缀，也接受裸令牌。 */
    public static String fromHeader(String authorization) {
        if (authorization == null || authorization.isBlank()) return null;
        String value = authorization.trim();
        if (value.regionMatches(true, 0, "Bearer ", 0, 7)) value = value.substring(7).trim();
        return value.isEmpty() ? null : value;
    }

    private String sign(String encodedPayload) {
        try {
            Mac mac = Mac.getInstance(ALGORITHM);
            mac.init(new SecretKeySpec(secret, ALGORITHM));
            return HexFormat.of().formatHex(mac.doFinal(encodedPayload.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception error) {
            throw new IllegalStateException("令牌签名失败", error);
        }
    }
}