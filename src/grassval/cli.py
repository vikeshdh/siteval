"""Command-line entry point for the grassval package.

Wires the `download` and `validate` subcommands into a single console script.
After ``pip install``, this is invoked as ``grassval <subcommand> ...``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .downloader import WaybackDownloader
from .validator import ImageValidator


def _add_download_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "download",
        help="Download Esri Wayback imagery for points in a CSV.",
        description="Download visually unique Esri Wayback imagery for "
                    "points listed in a CSV (columns: id, lat, lon, target_year).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--csv", "-c", required=True,
                   help="Path to input CSV file.")
    p.add_argument("--output", "-o", required=True,
                   help="Output directory (one subfolder per point id).")
    p.add_argument("--logs", "-l", default="logs",
                   help="Logs directory (default: logs)")
    p.add_argument("--zoom", "-z", type=int, default=18, choices=[17, 18, 19],
                   help="Zoom level (17-19, default: 18)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable verbose output")


def _add_validate_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "validate",
        help="Open the binary Accept/Reject GUI for downloaded imagery.",
        description="Step through downloaded Wayback imagery and record "
                    "binary Accept/Reject decisions to a CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keyboard shortcuts:
    A             - Mark as Accept
    R             - Mark as Reject
    Left / Right  - Previous / Next point
    Enter         - Save notes and go to next
    Ctrl+S        - Save notes and go to next
""",
    )
    p.add_argument("--csv", "-c", required=True,
                   help="Original input CSV (id, lat, lon, target_year).")
    p.add_argument("--imagery", "-i", required=True,
                   help="Directory containing imagery (one subfolder per id).")
    p.add_argument("--output", "-o", required=True,
                   help="Output directory for the validated CSV.")
    p.add_argument("--filename", default="validated_points.csv",
                   help="Output filename (default: validated_points.csv).")


def _run_download(args: argparse.Namespace) -> int:
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    downloader = WaybackDownloader(
        output_dir=args.output,
        zoom=args.zoom,
        logs_dir=args.logs,
    )
    stats = downloader.process_csv(args.csv)

    if "error" in stats:
        print(f"Processing failed: {stats['error']}", file=sys.stderr)
        return 1

    print("\n" + "=" * 50)
    print("Download Complete!")
    print("=" * 50)
    print(f"Total points:    {stats['total']}")
    print(f"Successful:      {stats['success']}")
    print(f"Failed:          {stats['failed']}")
    print(f"Output directory: {args.output}/")
    if stats['failed'] > 0:
        print(f"Failed points logged to: {args.logs}/failed_points.log")
    return 0 if stats['failed'] == 0 else 1


def _run_validate(args: argparse.Namespace) -> int:
    imagery_dir = Path(args.imagery)
    csv_path = Path(args.csv)
    output_dir = Path(args.output)

    if not imagery_dir.exists():
        print(f"Error: imagery directory not found: {imagery_dir}", file=sys.stderr)
        return 1
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / args.filename

    app = ImageValidator(imagery_dir, csv_path, output_path)
    app.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="grassval",
        description="Download Wayback imagery and validate points from a CSV.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_download_parser(subparsers)
    _add_validate_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command == "download":
        return _run_download(args)
    if args.command == "validate":
        return _run_validate(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
