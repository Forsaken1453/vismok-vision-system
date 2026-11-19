"""Persistent energy and electricity-cost estimates from the PZEM meter."""

import json
import math
import os
import threading
from calendar import monthrange
from datetime import datetime


class BillingTracker:
    """Accumulate PZEM counter deltas into daily and monthly usage buckets."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()

    @staticmethod
    def _empty(now: datetime) -> dict:
        return {
            "day": now.date().isoformat(),
            "month": now.strftime("%Y-%m"),
            "month_started_at": None,
            "today_kwh": 0.0,
            "month_kwh": 0.0,
            "last_meter_kwh": None,
            "started_at": None,
            "last_updated": None,
        }

    def _load(self) -> dict:
        now = datetime.now()
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("billing data must be an object")
            merged = self._empty(now)
            merged.update(data)
            return merged
        except FileNotFoundError:
            return self._empty(now)
        except (OSError, ValueError, json.JSONDecodeError):
            return self._empty(now)

    def _save(self):
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self._data, file, indent=2)
        os.replace(temp_path, self.path)

    def _roll_periods(self, now: datetime):
        day = now.date().isoformat()
        month = now.strftime("%Y-%m")
        changed = False
        if self._data.get("day") != day:
            self._data["day"] = day
            self._data["today_kwh"] = 0.0
            changed = True
        if self._data.get("month") != month:
            self._data["month"] = month
            self._data["month_started_at"] = None
            self._data["month_kwh"] = 0.0
            changed = True
        if changed:
            self._save()

    def update(self, meter_kwh, tariff_rp_per_kwh: float, now=None) -> dict:
        now = now or datetime.now()
        try:
            reading = float(meter_kwh)
        except (TypeError, ValueError):
            reading = float("nan")

        with self._lock:
            self._roll_periods(now)
            if math.isfinite(reading) and reading >= 0:
                if not self._data.get("month_started_at"):
                    self._data["month_started_at"] = now.isoformat(timespec="seconds")
                previous = self._data.get("last_meter_kwh")
                if previous is None:
                    self._data["started_at"] = now.isoformat(timespec="seconds")
                else:
                    previous = float(previous)
                    # The PZEM counter can be reset. Count its new value as
                    # usage since reset instead of creating a negative delta.
                    delta = reading - previous if reading >= previous else reading
                    if math.isfinite(delta) and delta >= 0:
                        self._data["today_kwh"] = round(
                            self._data["today_kwh"] + delta, 6
                        )
                        self._data["month_kwh"] = round(
                            self._data["month_kwh"] + delta, 6
                        )
                self._data["last_meter_kwh"] = reading
                self._data["last_updated"] = now.isoformat(timespec="seconds")
                self._save()

            return self._summary(tariff_rp_per_kwh, now)

    def summary(self, tariff_rp_per_kwh: float, now=None) -> dict:
        now = now or datetime.now()
        with self._lock:
            self._roll_periods(now)
            return self._summary(tariff_rp_per_kwh, now)

    def _summary(self, tariff_rp_per_kwh: float, now: datetime) -> dict:
        tariff = float(tariff_rp_per_kwh)
        today_kwh = float(self._data.get("today_kwh", 0.0))
        month_kwh = float(self._data.get("month_kwh", 0.0))
        days_in_month = monthrange(now.year, now.month)[1]
        month_started_at = self._data.get("month_started_at")
        try:
            tracking_start = datetime.fromisoformat(month_started_at)
            tracked_days = max((now - tracking_start).total_seconds() / 86400.0, 0.0)
        except (TypeError, ValueError):
            tracked_days = 0.0
        projected_kwh = (
            month_kwh / tracked_days * days_in_month
            if tracked_days >= 1.0 else None
        )
        return {
            "tariff_rp_per_kwh": tariff,
            "today_kwh": round(today_kwh, 6),
            "today_cost_rp": round(today_kwh * tariff, 2),
            "month_kwh": round(month_kwh, 6),
            "month_cost_rp": round(month_kwh * tariff, 2),
            "projected_month_kwh": (
                round(projected_kwh, 6) if projected_kwh is not None else None
            ),
            "projected_month_cost_rp": (
                round(projected_kwh * tariff, 2)
                if projected_kwh is not None else None
            ),
            "days_in_month": days_in_month,
            "tracked_days_this_month": round(tracked_days, 3),
            "day": self._data.get("day"),
            "month": self._data.get("month"),
            "started_at": self._data.get("started_at"),
            "last_updated": self._data.get("last_updated"),
            "has_baseline": self._data.get("last_meter_kwh") is not None,
        }
