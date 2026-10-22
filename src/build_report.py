"""Ghép số liệu (JSON từ analyze_social_report.py) vào template.html.

    python src/build_report.py social-report-data.json [--fragment <đường dẫn artifact>]

- Luôn ghi index.html ở gốc repo: trang HTML đầy đủ cho GitHub Pages.
- --fragment: ghi thêm bản không có <!doctype>/<head> (claude.ai Artifact tự bọc khung trang khi publish).
Số liệu lấy từ DB Creative Win (bài Fanpage công khai qua So9), không có thông tin khách hàng.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE_HEAD = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')


def build(data_path: str) -> str:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")   # không đóng <script> sớm
    return (HERE / "template.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", payload, 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--fragment")
    args = ap.parse_args()
    body = build(args.data)
    page = HERE.parent / "index.html"
    page.write_text(PAGE_HEAD + body, encoding="utf-8", newline="\n")
    print(page, page.stat().st_size, "bytes")
    if args.fragment:
        Path(args.fragment).write_text(body, encoding="utf-8", newline="\n")
        print(args.fragment, "written")
