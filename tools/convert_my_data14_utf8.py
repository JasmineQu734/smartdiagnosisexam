import json
from pathlib import Path


PATH = Path(r"C:\Users\admin\Desktop\my_data14.json")


def main():
    raw = PATH.read_bytes()
    text = None
    source_encoding = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            text = raw.decode(encoding)
            source_encoding = encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("无法识别文件编码")

    data = json.loads(text)
    PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    check = PATH.read_bytes()
    json.loads(check.decode("utf-8"))
    print(
        json.dumps(
            {
                "file": str(PATH),
                "source_encoding": source_encoding,
                "output_encoding": "utf-8",
                "bom": check.startswith(b"\xef\xbb\xbf"),
                "bytes": len(check),
                "top_level": type(data).__name__,
                "count": len(data) if isinstance(data, list) else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
