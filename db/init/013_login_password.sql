-- 013 登录口令初始化（2026-10-23）
-- 背景：登录从「选演示身份」升级为「账号 + 口令」。app_user.password_hash 列在 001_schema 里已存在，
-- 此前一直为空串（登录只查账号）。本脚本给全部账号写入初始口令的散列。
-- 口令不以明文落库：存 SHA-256( username + ':' + password ) 的十六进制小写，
-- 与后端 ApiController.login 的校验口径一致（见 api-catalog.md 认证一节）。
-- 2026-10-23 口令统一调整为 123456：按用户要求全部覆盖为同一口令（演示环境，无独立改密入口）。
USE train_system;

-- 初始口令 = 123456（散列仍含 username 前缀，各账号散列值不同）
UPDATE app_user
SET password_hash = SHA2(CONCAT(username, ':', '123456'), 256);
