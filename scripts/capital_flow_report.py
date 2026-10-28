"""把公开资金面快照生成为不依赖网络的单文件图表。"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(data):
    if data.get("schema") != "capital-flow-v1":
        raise ValueError("不支持的数据格式")
    template = (ROOT / "assets/capital-flow-report.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # JSON放入script文本上下文，防止来源名称中的闭合标签终止脚本。
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return template.replace("__CAPITAL_FLOW_JSON__", payload)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data), encoding="utf-8")
    print(str(args.output.resolve()))


if __name__ == "__main__":
    main()
