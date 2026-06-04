"""Command-line entry point for the siteval package.

Subcommands
-----------
run       Launch the full GUI workflow (upload -> params -> download -> validate).
download  Download imagery headlessly from a CSV (power-user / scripting mode).
validate  Open the validator GUI for an existing imagery directory.

After ``pip install siteval`` invoke as::

    siteval run
    siteval download --csv points.csv --output imagery/
    siteval validate --csv points.csv --imagery imagery/ --output results/
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .downloader import WaybackDownloader
from .validator import ImageValidator


def _add_download_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "download",
        help="Download Wayback imagery for points in a CSV (headless).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Download temporally-sampled Esri Wayback imagery for every\n"
            "point in a CSV (id, lat, lon, target_date or target_year).\n"
            "Imagery is written to <output>/<id>/<id>_<N>_<date>.png."
        ),
    )
    p.add_argument("--csv", "-c", required=True, help="Path to input CSV.")
    p.add_argument("--output", "-o", required=True,
                   help="Output directory (one sub-folder per point id).")
    p.add_argument("--back", type=float, default=1.0,
                   help="How far before each target date to look (default: 1).")
    p.add_argument("--back-unit", default="years",
                   choices=["days", "months", "years"],
                   help="Unit for --back (default: years).")
    p.add_argument("--forward", type=float, default=1.0,
                   help="How far after each target date to look (default: 1).")
    p.add_argument("--forward-unit", default="years",
                   choices=["days", "months", "years"],
                   help="Unit for --forward (default: years).")
    p.add_argument("--interval", type=float, default=1.0,
                   help="Step between sampled images (default: 1).")
    p.add_argument("--interval-unit", default="years",
                   choices=["days", "months", "years"],
                   help="Unit for --interval (default: years).")
    p.add_argument("--zoom", "-z", type=int, default=18, choices=[17, 18, 19],
                   help="Tile zoom level (default: 18).")
    p.add_argument("--tile-size", "-t", type=int, default=3, choices=[1, 3, 5],
                   help="Tile grid side length: 1, 3, or 5 (default: 3).")
    p.add_argument("--logs", "-l", default="logs",
                   help="Directory for failure logs (default: logs/).")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable verbose/debug output.")


def _add_validate_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "validate",
        help="Open the Accept / Reject / Caution GUI for downloaded imagery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keyboard shortcuts:
    A / R / C     Accept, Reject, Caution
    Left / Right  Previous / Next point
    Enter         Save & go to next
    Ctrl+S        Save & go to next
""",
    )
    p.add_argument("--csv", "-c", required=True,
                   help="Original input CSV (id, lat, lon, target_date).")
    p.add_argument("--imagery", "-i", required=True,
                   help="Directory containing imagery (one sub-folder per id).")
    p.add_argument("--output", "-o", required=True,
                   help="Output directory for the validated CSV.")
    p.add_argument("--filename", default="validated_points.csv",
                   help="Output filename (default: validated_points.csv).")


def _add_run_parser(sub: argparse._SubParsersAction) -> None:
    sub.add_parser(
        "run",
        help="Launch the full siteval GUI (CSV -> parameters -> download -> validate).",
    )


_UNIT_DAYS = {"days": 1.0, "months": 30.4375, "years": 365.25}


def _run_download(args: argparse.Namespace) -> int:
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level,
                        format='%(asctime)s  %(levelname)s  %(message)s')

    downloader = WaybackDownloader(
        output_dir=args.output,
        zoom=args.zoom,
        logs_dir=args.logs,
        back_days=args.back * _UNIT_DAYS[args.back_unit],
        forward_days=args.forward * _UNIT_DAYS[args.forward_unit],
        interval_days=args.interval * _UNIT_DAYS[args.interval_unit],
        tile_size=args.tile_size,
    )
    stats = downloader.process_csv(args.csv)

    if "error" in stats:
        print(f"Error: {stats['error']}", file=sys.stderr)
        return 1

    print("\n" + "=" * 50)
    print("Download complete")
    print("=" * 50)
    print(f"  Total:      {stats['total']}")
    print(f"  Succeeded:  {stats['success']}")
    print(f"  Failed:     {stats['failed']}")
    print(f"  Output:     {args.output}/")
    if stats['failed'] > 0:
        print(f"  Failed log: {args.logs}/failed_points.log")
    return 0 if stats['failed'] == 0 else 1


def _run_validate(args: argparse.Namespace) -> int:
    imagery_dir = Path(args.imagery)
    csv_path = Path(args.csv)
    output_dir = Path(args.output)

    if not imagery_dir.exists():
        print(f"Error: imagery directory not found: {imagery_dir}", file=sys.stderr)
        return 1
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    app = ImageValidator(imagery_dir, csv_path, output_dir / args.filename)
    app.run()
    return 0


def _run_gui(_args: argparse.Namespace) -> int:
    from .app import SitevalApp
    SitevalApp().run()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="siteval",
        description="Download Wayback imagery and validate geographic points from a CSV.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_run_parser(sub)
    _add_download_parser(sub)
    _add_validate_parser(sub)

    args = parser.parse_args(argv)

    if args.command == "run":
        return _run_gui(args)
    if args.command == "download":
        return _run_download(args)
    if args.command == "validate":
        return _run_validate(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
