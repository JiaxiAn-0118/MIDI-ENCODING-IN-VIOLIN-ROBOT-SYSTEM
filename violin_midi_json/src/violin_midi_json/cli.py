"""命令行入口（让这个工具能在终端里直接用，对应 README 里的命令）。

典型用法：

    # 1) 生成给人看的 JSON 调试文件
    python -m violin_midi_json.cli 输入.mid 输出.json --format json --title "小星星"

    # 2) 生成给单片机用的二进制曲谱
    python -m violin_midi_json.cli 输入.mid 输出.bin --format bin --title "小星星"

    # 3) 让工具根据后缀名自动判断格式（.bin→二进制，其它→JSON）
    python -m violin_midi_json.cli 输入.mid 输出.bin --title "小星星"
"""

import argparse
from pathlib import Path

from .converter import MidiToJsonConverter


def build_parser() -> argparse.ArgumentParser:
    """定义命令行参数（--help 时会显示这些说明）。"""
    parser = argparse.ArgumentParser(description="Convert single-line violin MIDI into JSON or binary violin events")
    parser.add_argument("midi", type=Path, help="Input MIDI file path")               # 位置参数：输入 MIDI
    parser.add_argument("output", type=Path, help="Output file path")                 # 位置参数：输出文件
    parser.add_argument(
        "--format",
        choices=("auto", "json", "bin"),  # 只允许这三个值
        default="auto",
        help="Output format. auto uses .bin for binary files and JSON otherwise.",  # 默认 auto
    )
    parser.add_argument("--title", type=str, default=None, help="Optional title override")  # 可选曲名
    return parser


def main() -> None:
    """程序从这里开始执行。"""
    args = build_parser().parse_args()           # 解析命令行参数
    converter = MidiToJsonConverter()            # 建好转换器
    output_format = args.format
    if output_format == "auto":
        # auto 模式：看输出文件后缀——.bin 就走二进制，否则走 JSON。
        output_format = "bin" if args.output.suffix.lower() == ".bin" else "json"

    if output_format == "bin":
        converter.convert_to_binary_file(args.midi, args.output, title=args.title)
    else:
        converter.convert_to_json_file(args.midi, args.output, title=args.title)


if __name__ == "__main__":
    main()
