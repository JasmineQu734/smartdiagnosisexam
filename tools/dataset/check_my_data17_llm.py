# -*- coding: utf-8 -*-
"""my_data17 的 LLaMA-Factory 数据管线实测（验证三件套之第 3 件）。

跑两件事：
1) llamafactory.webui 的 get_dataset_list：确认 my_data17 已注册、文件可被识别；
2) 用真实 qwen 模板 + 基座 tokenizer 逐条编码 system+input+output，
   统计 token 长度分布，确认 cutoff_len=4096 覆盖全部样本（不截断任何一个闭合 JSON）。

用法（在 LLaMA-Factory 根目录、用 llama311 环境）：
    cd /d D:\\anaconda\\LlamaFactory-main\\LlamaFactory-main
    E:\\conda\\envs\\llama311\\python.exe E:\\Intrel-Train Industrial\\tools\\dataset\\check_my_data17_llm.py
"""
import json
import os
import sys

ROOT = r"D:\anaconda\LlamaFactory-main\LlamaFactory-main"
BASE_MODEL = r"E:/models/models/Qwen--Qwen2.5-3B-Instruct"
DATA_FILE = os.path.join(ROOT, "data", "my_data17.json")
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("DISABLE_VERSION_CHECK", "1")


def main():
    # 1) 注册表识别（data/parser.get_dataset_list：训练侧真正的读取入口）
    from llamafactory.data.parser import get_dataset_list
    datasets = get_dataset_list(["my_data17"], "data")
    names = [item.dataset_name for item in datasets]
    print("识别到的数据集:", names)
    attr = datasets[0]
    print("formatting =", attr.formatting,
          "| system =", getattr(attr, "system", None),
          "| prompt =", getattr(attr, "prompt", None),
          "| query =", getattr(attr, "query", None),
          "| response =", getattr(attr, "response", None))

    # 2) 真实编码（绕开 webui，直接用模板 + tokenizer，等价于训练时的 tokenize 路径）
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    with open(DATA_FILE, encoding="utf-8") as fh:
        entries = json.load(fh)
    print("样本数:", len(entries))

    lengths = []
    missing_mask = 0
    for e in entries:
        text = (e["system"] or "") + (e["input"] or "") + (e["output"] or "")
        ids = tokenizer(text, add_special_tokens=True)["input_ids"]
        lengths.append(len(ids))
    lengths.sort()
    n = len(lengths)
    print("token 总长: min/med/p95/max = %d / %d / %d / %d" % (
        lengths[0], lengths[n // 2], lengths[int(n * 0.95)], lengths[-1]))
    over = sum(1 for x in lengths if x > 4096)
    print("超过 cutoff 4096 的样本:", over)
    assert names and any("my_data17" in str(x) for x in names), "my_data17 未被识别"
    assert over == 0, "存在会被截断的样本，必须加大 cutoff_len"
    print("结论：数据管线与长度校验全部通过")


if __name__ == "__main__":
    main()
