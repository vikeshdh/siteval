"""Esri Wayback imagery downloader for grassval.

Refactored from `vhr_downloader.py` into a reusable module. Given any CSV
with the columns `id, lat, lon, target_year`, fetches up to four visually
unique Wayback snapshots per point and writes them as PNGs into
``<output>/<id>/``. Image hashing is used to deduplicate visually identical
captures across Wayback releases.

Used by the `grassval download` CLI command.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

from .utils import load_points

logger = logging.getLogger(__name__)


class WaybackDownloader:
    """Download visually unique Esri Wayback imagery for points in a CSV."""

    WAYBACK_CONFIG_URL = (
        "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/"
        "waybackconfig.json"
    )

    def __init__(self, output_dir: str | Path = "output", zoom: int = 18,
                 logs_dir: str | Path = "logs"):
        self.output_dir = Path(output_dir)
        self.logs_dir = Path(logs_dir)
        self.zoom = zoom
        self.wayback_items: Optional[list[dict]] = None
        self.failed_points: list[dict] = []

    # ── Wayback config ──────────────────────────────────────────────────

    def fetch_wayback_config(self) -> bool:
        """Fetch the Wayback configuration containing all available layers."""
        try:
            logger.info("Fetching Wayback configuration...")
            response = requests.get(self.WAYBACK_CONFIG_URL, timeout=30)
            response.raise_for_status()
            config = response.json()

            self.wayback_items = []
            for key, item in config.items():
                item_title = item.get("itemTitle", "")
                match = re.search(r'(\d{4}-\d{2}-\d{2})', item_title)
                if match:
                    try:
                        date_str = match.group(1)
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                        self.wayback_items.append({
                            "date": parsed_date,
                            "date_str": date_str,
                            "year": parsed_date.year,
                            "item_id": item.get("itemID"),
                            "item_url": item.get("itemURL"),
                            "layer_key": key,
                        })
                    except ValueError:
                        continue

            self.wayback_items.sort(key=lambda x: x["date"])
            logger.info(f"Found {len(self.wayback_items)} Wayback layers")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to fetch Wayback config: {e}")
            return False

    # ── Tile math ───────────────────────────────────────────────────────

    @staticmethod
    def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
        """Convert lat/lon to slippy-map tile coordinates at `zoom`."""
        lat_rad = math.radians(lat)
        n = 2 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x, y

    def download_tiles(self, layer: dict, lat: float, lon: float,
                       tile_size: int = 3):
        """Download a tile_size × tile_size grid and return a composite Image."""
        try:
            from PIL import Image

            center_x, center_y = self.lat_lon_to_tile(lat, lon, self.zoom)
            half = tile_size // 2
            tile_px = 256
            composite = Image.new('RGB', (tile_size * tile_px, tile_size * tile_px))

            base_url = layer.get("item_url", "")
            if not base_url:
                return None

            success_count = 0
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    tile_x = center_x + dx
                    tile_y = center_y + dy

                    tile_url = (base_url
                                .replace("{level}", str(self.zoom))
                                .replace("{row}", str(tile_y))
                                .replace("{col}", str(tile_x)))

                    try:
                        response = requests.get(tile_url, timeout=15)
                        if response.status_code == 200:
                            tile_img = Image.open(BytesIO(response.content))
                            pos_x = (dx + half) * tile_px
                            pos_y = (dy + half) * tile_px
                            composite.paste(tile_img, (pos_x, pos_y))
                            success_count += 1
                    except Exception:
                        pass

            return composite if success_count > 0 else None

        except ImportError:
            logger.error("PIL/Pillow required. Install: pip install pillow")
            return None
        except Exception as e:
            logger.debug(f"Failed to download tiles: {e}")
            return None

    # ── Image hashing & labelling ───────────────────────────────────────

    @staticmethod
    def compute_image_hash(image) -> str:
        """Compute a coarse perceptual hash for cross-layer deduplication."""
        small = image.resize((64, 64)).convert('L')
        pixels = list(small.getdata())
        return hashlib.md5(bytes(pixels)).hexdigest()

    @staticmethod
    def add_label_to_image(image, label: str, date_str: str) -> None:
        """Burn a `LABEL: YYYY-MM-DD` overlay into the bottom-left of `image`."""
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(image, 'RGBA')
        text = f"{label.upper()}: {date_str}"

        font_size = 28
        font = None
        for font_path in (
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except (IOError, OSError):
                continue
        if font is None:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        padding = 10
        margin = 15
        x = margin
        y = image.height - text_height - padding * 2 - margin

        draw.rectangle([x - padding, y - padding,
                        x + text_width + padding, y + text_height + padding],
                       fill=(0, 0, 0, 180))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    # ── Layer selection ─────────────────────────────────────────────────

    def find_unique_layers(self, target_year: int, lat: float,
                           lon: float) -> list[tuple[str, dict, "Image.Image"]]:
        """Pick up to 4 visually distinct layers around `target_year`."""
        if not self.wayback_items:
            return []

        target_idx = None
        min_diff = float('inf')
        for idx, item in enumerate(self.wayback_items):
            diff = abs(item["year"] - target_year)
            if diff < min_diff:
                min_diff = diff
                target_idx = idx

        if target_idx is None:
            return []

        unique_images: list[tuple[str, dict, "Image.Image"]] = []
        seen_hashes: set[str] = set()

        def try_add_layer(layer, label):
            img = self.download_tiles(layer, lat, lon)
            if img is None:
                return False
            img_hash = self.compute_image_hash(img)
            if img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                unique_images.append((label, layer, img))
                return True
            return False

        target_layer = self.wayback_items[target_idx]
        if not try_add_layer(target_layer, "target"):
            return []

        for idx in range(target_idx - 1, -1, -1):
            if try_add_layer(self.wayback_items[idx], "before"):
                break

        target_date = target_layer["date"]
        start_after_idx = target_idx + 1
        for idx in range(target_idx + 1, len(self.wayback_items)):
            if self.wayback_items[idx]["date"] >= target_date + timedelta(days=300):
                start_after_idx = idx
                break
        for idx in range(start_after_idx, len(self.wayback_items)):
            if try_add_layer(self.wayback_items[idx], "after"):
                break

        try_add_layer(self.wayback_items[-1], "recent")

        unique_images.sort(key=lambda x: x[1]["date"])
        return [(f"{i+1}", layer, img)
                for i, (_, layer, img) in enumerate(unique_images)]

    # ── Per-point and CSV processing ────────────────────────────────────

    def process_point(self, point_id: str, lat: float, lon: float,
                      target_year: int) -> bool:
        """Download and write all unique snapshots for one point."""
        unique_layers = self.find_unique_layers(target_year, lat, lon)

        if not unique_layers:
            logger.warning(f"Point {point_id}: No imagery found")
            return False

        point_dir = self.output_dir / str(point_id)
        point_dir.mkdir(parents=True, exist_ok=True)

        for label, layer, image in unique_layers:
            date_str = layer["date_str"]
            filename = f"{point_id}_{label}_{date_str}.png"
            output_path = point_dir / filename
            self.add_label_to_image(image, f"Image {label}", date_str)
            image.save(output_path, 'PNG')
            logger.debug(f"Point {point_id}: Saved {filename}")

        logger.debug(f"Point {point_id}: Saved {len(unique_layers)} unique images")
        return True

    def log_failed_points(self) -> None:
        """Write per-run failure log to ``<logs_dir>/failed_points.log``."""
        if not self.failed_points:
            return
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / "failed_points.log"
        with open(log_path, 'w') as f:
            f.write("# Failed points log\n")
            f.write("# Format: id,lat,lon,target_year,reason\n")
            for point in self.failed_points:
                f.write(f"{point['id']},{point['lat']},{point['lon']},"
                        f"{point['target_year']},{point.get('reason', 'unknown')}\n")
        logger.info(f"Logged {len(self.failed_points)} failed points to {log_path}")

    def process_csv(self, csv_path: str | Path) -> dict:
        """Process every point in `csv_path` and return a stats dict."""
        try:
            df = load_points(csv_path)
        except FileNotFoundError as e:
            logger.error(str(e))
            return {"error": "CSV file not found"}
        except ValueError as e:
            logger.error(str(e))
            return {"error": str(e)}

        if not self.fetch_wayback_config():
            return {"error": "Failed to fetch Wayback configuration"}

        stats = {"success": 0, "failed": 0, "total": len(df)}
        logger.info(f"Processing {len(df)} points...")

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Downloading imagery"):
            point_id = row['id']
            lat = float(row['lat'])
            lon = float(row['lon'])
            target_year = int(row['target_year'])

            try:
                if self.process_point(point_id, lat, lon, target_year):
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    self.failed_points.append({
                        "id": point_id, "lat": lat, "lon": lon,
                        "target_year": target_year, "reason": "no_imagery",
                    })
            except Exception as e:
                stats["failed"] += 1
                self.failed_points.append({
                    "id": point_id, "lat": lat, "lon": lon,
                    "target_year": target_year, "reason": str(e),
                })
                logger.debug(f"Point {point_id} failed: {e}")

        self.log_failed_points()
        return stats
