"""
StatCan WDS (Web Data Service) DAO — factory pattern.

Usage:
    from market_data.statcan import get_dao

    cpi = get_dao("cpi")
    latest = cpi.latest(41691130)          # Gasoline — single value
    series = cpi.series(41691130, n=24)    # Last 24 monthly observations
    batch  = cpi.batch([41691130, 41691063], n=1)  # Multiple vectors at once
    cagr   = cpi.cagr(41691130, years=10)  # Trailing geometric growth rate

    # Or access a specific table directly:
    dao = get_dao("table", product_id=18100004)
    dao.batch([41691130, 41691063], n=1)
"""

from __future__ import annotations

import subprocess
import json
from dataclasses import dataclass
from typing import Optional
from datetime import date


_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"

# CPI table — 18100004, monthly, Canada-level vectors for Geography member 2 (Canada)
CPI_PRODUCT_ID = 18100004


# ---------------------------------------------------------------------------
# Internal transport — uses curl to avoid SSL cert issues on macOS Python 3.13
# ---------------------------------------------------------------------------

def _post(endpoint: str, payload: list | dict) -> list | dict:
    proc = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            f"{_BASE_URL}/{endpoint}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"HTTP error from StatCan: {proc.stderr}")
    if not proc.stdout:
        raise RuntimeError(f"Empty response from StatCan endpoint /{endpoint}")
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class DataPoint:
    ref_date: str   # "YYYY-MM-DD"
    value: Optional[float]


@dataclass
class VectorSeries:
    vector_id: int
    product_id: int
    coordinate: str
    data: list[DataPoint]

    @property
    def latest_value(self) -> Optional[float]:
        return self.data[-1].value if self.data else None

    @property
    def latest_date(self) -> Optional[str]:
        return self.data[-1].ref_date if self.data else None


# ---------------------------------------------------------------------------
# Base DAO
# ---------------------------------------------------------------------------

class _StatCanDAO:
    """
    Base DAO for the StatCan WDS API. Subclasses specialise for particular
    data products (CPI, bond yields, etc.).
    """

    def batch(self, vector_ids: list[int], n: int = 1) -> list[VectorSeries]:
        payload = [{"vectorId": v, "latestN": n} for v in vector_ids]
        raw = _post("getDataFromVectorsAndLatestNPeriods", payload)
        results = []
        for item in raw:
            if item.get("status") != "SUCCESS":
                continue
            obj = item["object"]
            points = [
                DataPoint(ref_date=p["refPer"], value=p.get("value"))
                for p in obj.get("vectorDataPoint", [])
            ]
            results.append(VectorSeries(
                vector_id=obj["vectorId"],
                product_id=obj["productId"],
                coordinate=obj["coordinate"],
                data=points,
            ))
        return results

    def latest(self, vector_id: int) -> Optional[float]:
        series = self.batch([vector_id], n=1)
        return series[0].latest_value if series else None

    def series(self, vector_id: int, n: int = 12) -> VectorSeries:
        results = self.batch([vector_id], n=n)
        if not results:
            raise ValueError(f"No data returned for vector {vector_id}")
        return results[0]

    def cagr(self, vector_id: int, years: int = 10) -> Optional[float]:
        """
        Trailing geometric CAGR over `years` years (monthly data → years * 12 periods).
        Returns a decimal fraction (e.g., 0.021 = 2.1% annualised).
        """
        n = years * 12 + 1  # need start + end
        result = self.series(vector_id, n=n)
        points = [p for p in result.data if p.value is not None]
        if len(points) < 2:
            return None
        start, end = points[0].value, points[-1].value
        if start <= 0:
            return None
        total_periods = len(points) - 1
        return (end / start) ** (12 / total_periods) - 1


# ---------------------------------------------------------------------------
# Specialised DAOs
# ---------------------------------------------------------------------------

class CPISeriesDAO(_StatCanDAO):
    """
    DAO for StatCan table 18100004 — Consumer Price Index (Canada, monthly).

    Keeps only Canada-level results (product_id == CPI_PRODUCT_ID).
    """

    def batch(self, vector_ids: list[int], n: int = 1) -> list[VectorSeries]:
        all_series = super().batch(vector_ids, n)
        return [s for s in all_series if s.product_id == CPI_PRODUCT_ID]

    def inflation_rate(self, vector_id: int, years: int = 10) -> Optional[float]:
        """Alias for cagr — returns annualised inflation as a decimal."""
        return self.cagr(vector_id, years=years)


class TableDAO(_StatCanDAO):
    """Generic DAO for any StatCan product table."""

    def __init__(self, product_id: int):
        self.product_id = product_id

    def batch(self, vector_ids: list[int], n: int = 1) -> list[VectorSeries]:
        all_series = super().batch(vector_ids, n)
        return [s for s in all_series if s.product_id == self.product_id]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[_StatCanDAO]] = {
    "cpi": CPISeriesDAO,
}


def get_dao(kind: str, **kwargs) -> _StatCanDAO:
    """
    Factory entry-point.

    Supported kinds:
      "cpi"   — CPISeriesDAO for table 18100004
      "table" — TableDAO for any product (pass product_id=<int>)

    Examples:
        get_dao("cpi")
        get_dao("table", product_id=18100006)
    """
    if kind == "table":
        product_id = kwargs.get("product_id")
        if product_id is None:
            raise ValueError("get_dao('table') requires product_id=<int>")
        return TableDAO(product_id)
    if kind not in _REGISTRY:
        raise ValueError(f"Unknown DAO kind {kind!r}. Choose from: {list(_REGISTRY)}")
    return _REGISTRY[kind]()
