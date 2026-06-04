"""Esri Wayback imagery downloader for siteval.

Given a CSV with columns ``id, lat, lon`` and either ``target_date``
(YYYY-MM-DD) or ``target_year`` (integer), fetches N visually unique Wayback
snapshots per point centred on the target date and writes them as PNGs into
``<output>/<id>/``.

Temporal selection strategy
---------------------------
1. Compute N evenly-spaced target timestamps centred on the point's
   ``target_date``, spanning ±(span_years/2) years.
2. Cap the window at the earliest and most-recent available Wayback capture.
3. For each target timestamp, pick the Wayback capture whose date is closest
   by absolute difference.
4. Deduplicate with a coarse perceptual hash so visually identical captures
   are never written twice.
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
    """Download temporally-sampled Esri Wayback imagery for points in a CSV."""

    WAYBACK_CONFIG_URL = (
        "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/"
        "waybackconfig.json"
    )

    def __init__(
        self,
        output_dir: str | Path = "output",
        zoom: int = 18,
        logs_dir: str | Path = "logs",
        back_days: float = 365.25,
        forward_days: float = 365.25,
        interval_days: float = 365.25,
        tile_size: int = 3,
    ):
        """
        Parameters
        ----------
        output_dir:    Root directory for PNG output (one sub-folder per id).
        zoom:          Wayback tile zoom level (17, 18, or 19).
        logs_dir:      Directory for failed_points.log.
        back_days:     Days before target_date to start the window.
        forward_days:  Days after  target_date to end the window.
        interval_days: Step in days between sampled dates.
        tile_size:     Tile grid side length (1, 3, or 5 -> 256/768/1280 px).
        """
        self.output_dir = Path(output_dir)
        self.logs_dir = Path(logs_dir)
        self.zoom = zoom
        self.back_days = max(0.0, float(back_days))
        self.forward_days = max(0.0, float(forward_days))
        self.interval_days = max(1.0, float(interval_days))
        self.tile_size = tile_size
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
        """Convert lat/lon to slippy-map tile coordinates at ``zoom``."""
        lat_rad = math.radians(lat)
        n = 2 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return x, y

    def download_tiles(self, layer: dict, lat: float, lon: float):
        """Download a tile_size x tile_size grid and return a composite Image."""
        try:
            from PIL import Image

            center_x, center_y = self.lat_lon_to_tile(lat, lon, self.zoom)
            half = self.tile_size // 2
            tile_px = 256
            composite = Image.new(
                'RGB',
                (self.tile_size * tile_px, self.tile_size * tile_px),
            )

            base_url = layer.get("item_url", "")
            if not base_url:
                return None

            success_count = 0
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    tile_x = center_x + dx
                    tile_y = center_y + dy
                    tile_url = (
                        base_url
                        .replace("{level}", str(self.zoom))
                        .replace("{row}", str(tile_y))
                        .replace("{col}", str(tile_x))
                    )
                    try:
                        r = requests.get(tile_url, timeout=15)
                        if r.status_code == 200:
                            tile_img = Image.open(BytesIO(r.content))
                            composite.paste(
                                tile_img,
                                ((dx + half) * tile_px, (dy + half) * tile_px),
                            )
                            success_count += 1
                    except Exception:
                        pass

            return composite if success_count > 0 else None

        except ImportError:
            logger.error("Pillow required: pip install pillow")
            return None
        except Exception as e:
            logger.debug(f"Failed to download tiles: {e}")
            return None

    # ── Image hashing & labelling ───────────────────────────────────────

    @staticmethod
    def compute_image_hash(image) -> str:
        """Coarse perceptual hash for deduplication across Wayback layers."""
        small = image.resize((64, 64)).convert('L')
        return hashlib.md5(bytes(list(small.getdata()))).hexdigest()

    @staticmethod
    def add_label_to_image(image, date_str: str) -> None:
        """Burn a date label overlay into the bottom-left of ``image``."""
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(image, 'RGBA')
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

        bbox = draw.textbbox((0, 0), date_str, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding, margin = 10, 15
        x = margin
        y = image.height - th - padding * 2 - margin
        draw.rectangle(
            [x - padding, y - padding, x + tw + padding, y + th + padding],
            fill=(0, 0, 0, 180),
        )
        draw.text((x, y), date_str, font=font, fill=(255, 255, 255, 255))

    # ── Temporal sampling ───────────────────────────────────────────────

    def _sample_target_dates(self, target_date: datetime) -> list[datetime]:
        """Return datetimes at interval steps within the back/forward window.

        Steps are generated from (target - back_days) in interval_days
        increments up to (target + forward_days), then capped to the
        Wayback archive bounds.
        """
        earliest = self.wayback_items[0]["date"]
        latest = self.wayback_items[-1]["date"]

        raw_start = target_date - timedelta(days=self.back_days)
        raw_end = target_date + timedelta(days=self.forward_days)

        # Cap to archive availability
        cap_start = max(raw_start, earliest)
        cap_end = min(raw_end, latest)

        if cap_start > cap_end:
            return [target_date]

        dates: list[datetime] = []
        current = raw_start
        tolerance = timedelta(hours=12)
        while current <= raw_end + tolerance:
            if cap_start <= current <= cap_end + tolerance:
                dates.append(current)
            current += timedelta(days=self.interval_days)

        return dates if dates else [target_date]

    def _closest_layer(self, target_dt: datetime) -> Optional[dict]:
        """Return the Wayback layer whose date is closest to ``target_dt``."""
        if not self.wayback_items:
            return None
        return min(
            self.wayback_items,
            key=lambda item: abs((item["date"] - target_dt).total_seconds()),
        )

    def find_layers_for_point(
        self, target_date: datetime, lat: float, lon: float
    ) -> list[tuple[str, dict, object]]:
        """Pick up to N visually distinct Wayback layers for one point."""
        target_dates = self._sample_target_dates(target_date)

        seen_hashes: set[str] = set()
        seen_layer_keys: set[str] = set()
        results: list[tuple[str, dict, object]] = []

        for td in target_dates:
            layer = self._closest_layer(td)
            if layer is None:
                continue
            if layer["layer_key"] in seen_layer_keys:
                continue

            img = self.download_tiles(layer, lat, lon)
            if img is None:
                continue

            img_hash = self.compute_image_hash(img)
            if img_hash in seen_hashes:
                seen_layer_keys.add(layer["layer_key"])
                continue

            seen_hashes.add(img_hash)
            seen_layer_keys.add(layer["layer_key"])
            results.append(("", layer, img))

        results.sort(key=lambda x: x[1]["date"])
        return [(str(i + 1), layer, img) for i, (_, layer, img) in enumerate(results)]

    # ── Per-point and CSV processing ────────────────────────────────────

    def process_point(
        self, point_id: str, lat: float, lon: float, target_date: datetime
    ) -> bool:
        """Download and write all sampled snapshots for one point."""
        layers = self.find_layers_for_point(target_date, lat, lon)
        if not layers:
            logger.warning(f"Point {point_id}: No imagery found")
            return False

        point_dir = self.output_dir / str(point_id)
        point_dir.mkdir(parents=True, exist_ok=True)

        for label, layer, image in layers:
            date_str = layer["date_str"]
            filename = f"{point_id}_{label}_{date_str}.png"
            self.add_label_to_image(image, date_str)
            image.save(point_dir / filename, 'PNG')
            logger.debug(f"Point {point_id}: saved {filename}")

        logger.debug(f"Point {point_id}: {len(layers)} images saved")
        return True

    def log_failed_points(self) -> None:
        """Write failure log to ``<logs_dir>/failed_points.log``."""
        if not self.failed_points:
            return
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / "failed_points.log"
        with open(log_path, 'w') as f:
            f.write("# id,lat,lon,target_date,reason\n")
            for p in self.failed_points:
                f.write(
                    f"{p['id']},{p['lat']},{p['lon']},"
                    f"{p['target_date']},{p.get('reason', 'unknown')}\n"
                )
        logger.info(f"Logged {len(self.failed_points)} failed points to {log_path}")

    def process_csv(
        self,
        csv_path: str | Path,
        progress_callback=None,
    ) -> dict:
        """Process every point in ``csv_path`` and return a stats dict.

        Parameters
        ----------
        csv_path:
            Path to the input CSV.
        progress_callback:
            Optional callable(current, total) invoked after each point,
            for GUI progress bars.
        """
        try:
            df = load_points(csv_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return {"error": str(e)}

        if not self.fetch_wayback_config():
            return {"error": "Failed to fetch Wayback configuration"}

        stats = {"success": 0, "failed": 0, "total": len(df)}
        logger.info(f"Processing {len(df)} points...")

        for i, (_, row) in enumerate(
            tqdm(df.iterrows(), total=len(df), desc="Downloading imagery")
        ):
            point_id = str(row['id'])
            lat = float(row['lat'])
            lon = float(row['lon'])
            target_date = datetime.combine(row['target_date'], datetime.min.time())

            try:
                if self.process_point(point_id, lat, lon, target_date):
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    self.failed_points.append({
                        "id": point_id, "lat": lat, "lon": lon,
                        "target_date": row['target_date'], "reason": "no_imagery",
                    })
            except Exception as e:
                stats["failed"] += 1
                self.failed_points.append({
                    "id": point_id, "lat": lat, "lon": lon,
                    "target_date": row['target_date'], "reason": str(e),
                })
                logger.debug(f"Point {point_id} failed: {e}")

            if progress_callback:
                progress_callback(i + 1, stats["total"])

        self.log_failed_points()
        return stats
