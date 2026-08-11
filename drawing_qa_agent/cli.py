"""Command-line interface for the drawing QA agent.

    python -m drawing_qa_agent analyze DRAWING.pdf -o checklist.xlsx
    python -m drawing_qa_agent from-json analysis.json -o checklist.xlsx
    python -m drawing_qa_agent demo -o demo_checklist.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .checklist import build_excel_checklist
from .extractor import DrawingExtractor, DrawingExtractorError
from .schema import DrawingAnalysis

_SAMPLE_PATH = Path(__file__).resolve().parent.parent / "tests" / "sample_analysis.json"


def _add_common_output_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("-o", "--output", default="checklist.xlsx", help="輸出的 Excel 檔案路徑")
    sub.add_argument("--inspector", default="", help="檢驗員姓名")
    sub.add_argument("--date", dest="inspection_date", default=None, help="檢驗日期 YYYY-MM-DD，預設今天")


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        extractor = DrawingExtractor(api_key=args.api_key, model=args.model)
        analysis = extractor.analyze(args.drawing)
    except DrawingExtractorError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    if args.save_json:
        Path(args.save_json).write_text(
            json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已儲存判讀結果 JSON：{args.save_json}")

    out = build_excel_checklist(
        analysis, args.output, inspector=args.inspector, inspection_date=_parse_date(args.inspection_date)
    )
    print(f"已產生檢核表：{out}（共 {len(analysis.dimensions)} 項尺寸）")
    for w in analysis.warnings:
        print(f"警示：{w}")
    return 0


def cmd_from_json(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    analysis = DrawingAnalysis.from_dict(data)
    out = build_excel_checklist(
        analysis, args.output, inspector=args.inspector, inspection_date=_parse_date(args.inspection_date)
    )
    print(f"已產生檢核表：{out}（共 {len(analysis.dimensions)} 項尺寸）")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    data = json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))
    analysis = DrawingAnalysis.from_dict(data)
    out = build_excel_checklist(
        analysis, args.output, inspector=args.inspector, inspection_date=_parse_date(args.inspection_date)
    )
    print(f"已使用範例資料產生檢核表：{out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawing_qa_agent", description="工程圖面判讀 AI 代理：讀取尺寸標註/量測要求並產生 Excel 品質檢核表"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="使用 Claude 判讀圖面 (PDF/PNG/JPG) 並產生檢核表")
    p_analyze.add_argument("drawing", help="圖面檔案路徑 (PDF 或圖片)")
    p_analyze.add_argument("--model", default=None, help="Claude 模型，預設環境變數 DRAWING_QA_MODEL 或 claude-sonnet-5")
    p_analyze.add_argument("--api-key", default=None, help="Anthropic API 金鑰，預設讀取 ANTHROPIC_API_KEY")
    p_analyze.add_argument("--save-json", default=None, help="同時將判讀結果存成 JSON 檔")
    _add_common_output_args(p_analyze)
    p_analyze.set_defaults(func=cmd_analyze)

    p_json = sub.add_parser("from-json", help="從既有的判讀結果 JSON 產生檢核表（不呼叫 API）")
    p_json.add_argument("json_path", help="判讀結果 JSON 檔案路徑")
    _add_common_output_args(p_json)
    p_json.set_defaults(func=cmd_from_json)

    p_demo = sub.add_parser("demo", help="使用內建範例資料產生檢核表，方便快速預覽格式")
    _add_common_output_args(p_demo)
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "model", None) is None and args.command == "analyze":
        from .extractor import DEFAULT_MODEL

        args.model = DEFAULT_MODEL
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
