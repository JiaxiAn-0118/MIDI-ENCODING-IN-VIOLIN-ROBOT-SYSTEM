import argparse
from pathlib import Path

from .converter import MidiToJsonConverter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert single-line violin MIDI into JSON or binary violin events")
    parser.add_argument("midi", type=Path, help="Input MIDI file path")
    parser.add_argument("output", type=Path, help="Output file path")
    parser.add_argument(
        "--format",
        choices=("auto", "json", "bin"),
        default="auto",
        help="Output format. auto uses .bin for binary files and JSON otherwise.",
    )
    parser.add_argument("--title", type=str, default=None, help="Optional title override")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    converter = MidiToJsonConverter()
    output_format = args.format
    if output_format == "auto":
        output_format = "bin" if args.output.suffix.lower() == ".bin" else "json"

    if output_format == "bin":
        converter.convert_to_binary_file(args.midi, args.output, title=args.title)
    else:
        converter.convert_to_json_file(args.midi, args.output, title=args.title)


if __name__ == "__main__":
    main()
