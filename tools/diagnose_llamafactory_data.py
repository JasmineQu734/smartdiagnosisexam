import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(r"D:\anaconda\LlamaFactory-main\LlamaFactory-main")
DATA_DIR = ROOT / "data"
DATASET_INFO = DATA_DIR / "dataset_info.json"
TARGET_DATASET = "my_data15"
REPORT_PATH = Path(r"C:\Users\admin\Desktop\llamafactory_my_data15_diagnosis.json")


def read_text(path):
    return path.read_text(encoding="utf-8-sig", errors="replace")


def duplicate_key_json_loads(text):
    duplicates = []

    def hook(pairs):
        seen = set()
        obj = {}
        for key, value in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
            obj[key] = value
        return obj

    return json.loads(text, object_pairs_hook=hook), duplicates


def find_dataset_references():
    refs = []
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    suffixes = {".yaml", ".yml", ".json", ".sh", ".bat", ".ps1", ".txt", ".md"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and d not in {"saves", "llamaboard_cache"}]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in suffixes:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if re.search(r"(^|\s)(dataset\s*:|--dataset\b)", line):
                    refs.append(
                        {
                            "file": str(path),
                            "line": line_no,
                            "text": line.strip(),
                        }
                    )
    return refs


def dataset_names_from_refs(refs):
    names = []
    for ref in refs:
        line = ref["text"]
        match = re.search(r"dataset\s*:\s*['\"]?([^'\"\s#]+)", line)
        if match:
            names.append(match.group(1).strip())
        match = re.search(r"--dataset\s+([^\\\s]+)", line)
        if match:
            names.append(match.group(1).strip())
    return names


def encoding_report(path):
    raw = path.read_bytes()
    report = {
        "path": str(path),
        "exists": path.exists(),
        "bytes": len(raw),
        "first_200_bytes_repr": repr(raw[:200]),
        "first_200_hex": raw[:200].hex(" "),
        "utf8_decodable": False,
        "utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
        "utf16_le_bom": raw.startswith(b"\xff\xfe"),
        "utf16_be_bom": raw.startswith(b"\xfe\xff"),
        "contains_ef_bf_bd_bytes": b"\xef\xbf\xbd" in raw,
        "contains_mojibake_markers": {},
    }
    text = None
    try:
        text = raw.decode("utf-8")
        report["utf8_decodable"] = True
    except UnicodeDecodeError as exc:
        report["utf8_error"] = str(exc)
    if text is not None:
        markers = ["�", "魹ｽ", "ﾙｰ", "啊ｬｵ", "����", "���"]
        report["contains_mojibake_markers"] = {marker: marker in text for marker in markers}
    return report


def sample_shape(data):
    if not isinstance(data, list):
        return {"top_level": type(data).__name__}
    rows = []
    role_summary = Counter()
    only_user_messages = 0
    has_assistant_messages = 0
    empty_assistant = 0
    for i, row in enumerate(data[:3]):
        item = {"index": i, "type": type(row).__name__}
        if isinstance(row, dict):
            item["keys"] = list(row.keys())
            if "messages" in row:
                roles = [msg.get("role") for msg in row.get("messages", []) if isinstance(msg, dict)]
                item["message_roles"] = roles
                item["messages_preview"] = row.get("messages", [])[:2]
            else:
                preview = {}
                for key, value in row.items():
                    if isinstance(value, str):
                        preview[key] = value[:300]
                    elif isinstance(value, dict):
                        preview[key] = {"__type__": "dict", "keys": list(value.keys())}
                    elif isinstance(value, list):
                        preview[key] = {"__type__": "list", "len": len(value)}
                    else:
                        preview[key] = value
                item["preview"] = preview
        rows.append(item)
    for row in data:
        if isinstance(row, dict) and "messages" in row:
            roles = [msg.get("role") for msg in row.get("messages", []) if isinstance(msg, dict)]
            if roles and set(roles) == {"user"}:
                only_user_messages += 1
            if "assistant" in roles:
                has_assistant_messages += 1
                for msg in row.get("messages", []):
                    if isinstance(msg, dict) and msg.get("role") == "assistant" and not str(msg.get("content", "")).strip():
                        empty_assistant += 1
        if isinstance(row, dict):
            if {"instruction", "input", "output"}.issubset(row):
                role_summary["alpaca_instruction_input_output"] += 1
            if "messages" in row:
                role_summary["sharegpt_messages"] += 1
            if isinstance(row.get("output"), dict):
                role_summary["output_is_object"] += 1
            if isinstance(row.get("output"), str):
                role_summary["output_is_string"] += 1
    return {
        "top_level": "list",
        "count": len(data),
        "first_3": rows,
        "format_counts": dict(role_summary),
        "messages_only_user_count": only_user_messages,
        "messages_has_assistant_count": has_assistant_messages,
        "messages_empty_assistant_count": empty_assistant,
    }


def extract_source_context(path, pattern, radius=8):
    if not path.exists():
        return {"path": str(path), "exists": False}
    lines = read_text(path).splitlines()
    hits = []
    for i, line in enumerate(lines):
        if pattern in line:
            start = max(0, i - radius)
            end = min(len(lines), i + radius + 1)
            hits.append(
                {
                    "hit_line": i + 1,
                    "context": [
                        {"line": n + 1, "text": lines[n]}
                        for n in range(start, end)
                    ],
                }
            )
    return {"path": str(path), "exists": True, "hits": hits}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    refs = find_dataset_references()
    ref_names = dataset_names_from_refs(refs)

    dataset_info_text = read_text(DATASET_INFO)
    dataset_info, duplicates = duplicate_key_json_loads(dataset_info_text)
    my_data_entries = {
        key: value for key, value in dataset_info.items()
        if key.startswith("my_data") or key == "test_data"
    }
    target_config = dataset_info.get(TARGET_DATASET)
    target_path = DATA_DIR / target_config["file_name"] if target_config else None

    json_parse = {"ok": False}
    data = None
    if target_path and target_path.exists():
        raw_text = target_path.read_text(encoding="utf-8")
        data = json.loads(raw_text.lstrip("\ufeff"))
        json_parse = {
            "ok": True,
            "top_level": type(data).__name__,
            "count": len(data) if isinstance(data, list) else None,
        }

    supervised = ROOT / "src" / "llamafactory" / "data" / "processor" / "supervised.py"
    loader = ROOT / "src" / "llamafactory" / "data" / "loader.py"

    result = {
        "actual_dataset_references": refs,
        "dataset_names_found": ref_names,
        "most_likely_dataset_from_root_my_train_yaml": None,
        "dataset_info_path": str(DATASET_INFO),
        "dataset_info_parse_ok": True,
        "dataset_info_duplicate_keys": duplicates,
        "my_data_entries": my_data_entries,
        "target_dataset_checked": TARGET_DATASET,
        "target_dataset_config": target_config,
        "target_file_full_path": str(target_path) if target_path else None,
        "encoding": encoding_report(target_path) if target_path else None,
        "json_parse": json_parse,
        "sample_shape": sample_shape(data) if data is not None else None,
        "supervised_invalid_example_context": extract_source_context(supervised, "Dropped invalid example"),
        "loader_stop_iteration_context": extract_source_context(loader, "next(iter(dataset))"),
    }

    root_yaml = ROOT / "my_train.yaml"
    if root_yaml.exists():
        for line in read_text(root_yaml).splitlines():
            match = re.search(r"dataset\s*:\s*['\"]?([^'\"\s#]+)", line)
            if match:
                result["most_likely_dataset_from_root_my_train_yaml"] = match.group(1)
                break

    text = json.dumps(result, ensure_ascii=False, indent=2)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
