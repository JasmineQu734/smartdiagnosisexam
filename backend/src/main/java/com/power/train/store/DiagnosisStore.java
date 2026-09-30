package com.power.train.store;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Agent 诊断结论：员工个性化诊断（scope=PERSONAL）与公司运行诊断（scope=EXEC），按 scope 记录最近一次。 */
@Component
public class DiagnosisStore {

    public static final String PERSONAL = "PERSONAL";
    public static final String EXEC = "EXEC";

    private final Sql sql;

    public DiagnosisStore(Sql sql) {
        this.sql = sql;
    }

    public void save(String scope, String diagnosisId, String ranAt, Map<String, Object> payload) {
        sql.update("INSERT INTO diagnosis_result (diagnosis_id, scope, ran_at, payload) VALUES (?, ?, ?, ?)",
            diagnosisId, scope, ranAt, sql.json(payload));
    }

    public Map<String, Object> latest(String scope) {
        Map<String, Object> row = sql.row(
            "SELECT payload FROM diagnosis_result WHERE scope = ? ORDER BY id DESC LIMIT 1", scope);
        Object parsed = sql.parse(sql.rawJson(row, "payload"));
        if (parsed instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((key, value) -> result.put(String.valueOf(key), value));
            return result;
        }
        return null;
    }

    /** 下一次诊断编号的序号（按当天已有条数递增）。 */
    public int nextSequence(String scope) {
        return (int) sql.count("SELECT COUNT(*) FROM diagnosis_result WHERE scope = ?", scope) + 1;
    }
}
