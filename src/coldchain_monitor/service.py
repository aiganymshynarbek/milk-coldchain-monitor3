"""Forecast summary shared by the command line and the REST service."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from coldchain_monitor.cascade import tier2_active
from coldchain_monitor.data import STEPS_PER_HOUR
from coldchain_monitor.forecasting import (
    arima_forecast_path,
    linear_trend,
    moving_average,
    persistence,
)
from coldchain_monitor.warning import DEFAULT_LIMIT

MAX_HOURS = 24


@dataclass(frozen=True)
class ForecastSummary:
    """Forecasts of all Tier-1 methods for one horizon and the resulting status."""

    readings: int
    latest: float
    hours: int
    limit: float
    persistence: float
    moving_average: float
    linear_trend: float
    arima: float
    arima_max: float
    status: str  #: "ok", "warning" or "excursion"
    tier2_active: bool

    def to_dict(self) -> dict:
        return asdict(self)


def forecast_summary(temperature, hours: int = 3, limit: float = DEFAULT_LIMIT) -> ForecastSummary:
    """Forecast ``hours`` ahead from the end of a 5-minute temperature series."""
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= MAX_HOURS:
        raise ValueError(f"hours must be a whole number between 1 and {MAX_HOURS}")
    history = np.asarray(temperature, dtype=float)
    if history.ndim != 1 or history.size < 2:
        raise ValueError("at least two temperature readings are required")
    if not np.all(np.isfinite(history)):
        raise ValueError("temperature readings must be finite numbers")
    steps = hours * STEPS_PER_HOUR
    path = arima_forecast_path(history, steps)
    latest = float(history[-1])
    if latest > limit:
        status = "excursion"
    elif float(path.max()) > limit:
        status = "warning"
    else:
        status = "ok"
    return ForecastSummary(
        readings=int(history.size),
        latest=round(latest, 3),
        hours=hours,
        limit=float(limit),
        persistence=round(persistence(history, steps), 3),
        moving_average=round(moving_average(history, steps), 3),
        linear_trend=round(linear_trend(history, steps), 3),
        arima=round(float(path[-1]), 3),
        arima_max=round(float(path.max()), 3),
        status=status,
        tier2_active=bool(tier2_active(history)[-1]),
    )
