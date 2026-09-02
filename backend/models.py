"""Pydantic response models for server.py's API, in the strictest mode
pydantic offers (strict type matching, no extra fields). Field shapes mirror
frontend/src/types/dashboard.ts, which is the contract's other source of
truth - keep the two in sync by hand; nothing generates one from the other.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Kpis(StrictBaseModel):
    n_tests: int
    est_words_typed: float
    tests_started: float
    completion_rate_pct: float
    restarts_per_test: float
    best_wpm: float
    avg_wpm_all: float
    avg_wpm_recent: float
    avg_wpm_first: float
    best_raw_wpm: float
    avg_raw_wpm_all: float
    avg_raw_wpm_recent: float
    best_acc: float
    avg_acc_recent: float
    avg_acc_all: float
    best_consistency: float
    avg_consistency_recent: float
    avg_consistency_all: float
    avg_errors_recent: float
    avg_errors_first: float
    total_minutes_typing: float
    date_span_days: float


class Insights(StrictBaseModel):
    wpm_slope_per_test: float
    wpm_trend_r: float
    acc_slope_per_test: float
    acc_std_first_half: float | None
    acc_std_second_half: float | None
    acc_wpm_correlation: float
    acc_wpm_slope: float
    acc_wpm_intercept: float
    wpm_per_hour_typing: float


class Action(StrictBaseModel):
    status: Literal["good", "warning", "serious"]
    text: str


class BigramRow(StrictBaseModel):
    bigram: str
    n: int
    median: float
    mean: float


class PopularTestRow(StrictBaseModel):
    label: str
    n: int
    avg_wpm: float | None
    avg_acc: float | None
    best_wpm: float | None


class ErgoCategoryRow(StrictBaseModel):
    key: str
    label: str
    desc: str
    distinct: int
    n: int
    avg: float | None
    delta_pct: float | None
    median: float | None
    representative_bigram: str | None
    representative_median: float | None


class ErgoDetailRow(StrictBaseModel):
    bigram: str
    n: int
    median: float
    mean: float
    category: str


class ErgoRepresentative(StrictBaseModel):
    bigram: str
    median: float


class Ergonomics(StrictBaseModel):
    overall_avg: float | None
    overall_median: float | None
    overall_representative: ErgoRepresentative | None
    category_rows: list[ErgoCategoryRow]
    detail_rows: list[ErgoDetailRow]


class DrillInfo(StrictBaseModel):
    text: str | None
    path: str | None


class CategoryDrillInfo(StrictBaseModel):
    key: str
    label: str
    desc: str
    n_entries: int
    text: str | None
    path: str | None


class Drills(StrictBaseModel):
    overall: DrillInfo
    categories: list[CategoryDrillInfo]


class DrillValidationRow(StrictBaseModel):
    bigram: str
    category: str
    occurrences: int
    avg_before_median: float
    avg_after_median: float
    avg_delta_ms: float


class SeriesPoint(StrictBaseModel):
    timestamp: str
    wpm: float
    acc: float
    mode: str
    mode2: str | None
    is_pb: bool
    language: str | None
    punctuation: bool
    numbers: bool
    raw_wpm: float
    test_duration: float


class KeyStats(StrictBaseModel):
    freq: dict[str, int]
    latency: dict[str, float]


class DashboardPayload(StrictBaseModel):
    kpis: Kpis
    insights: Insights
    has_tags: bool
    actions: list[Action]
    bigram_rows: list[BigramRow]
    popular_tests: list[PopularTestRow]
    ergonomics: Ergonomics
    drills: Drills
    drill_validation: list[DrillValidationRow]
    series: list[SeriesPoint]
    key_stats: KeyStats
    keylog_events: int
    keylog_sessions: int


class DrillManifest(StrictBaseModel):
    key: str
    label: str
    bigrams: list[str]
    generated_at: str
    text: str | None


class DrillManifestResponse(StrictBaseModel):
    overall: DrillManifest | None
    categories: list[DrillManifest]
