from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algo_manus.application.authenticated_historical_source import (
    AuthenticatedHistoricalCandleService,
)
from algo_manus.application.market_data import MarketDataRequest
from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository


class FixtureAuthenticatedHistoricalProvider:
    source_name = "fixture-authenticated-broker"
    source_kind = DataSourceKind.BROKER
    credentials_configured = True

    def __init__(self) -> None:
        self.calls = 0

    def fetch_candles(self, *, instrument_id, interval, start, end, retrieved_at):
        self.calls += 1
        raw = b"fixture-authenticated-candles"
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval=interval,
            provenance=DataProvenance(
                source_name=self.source_name,
                source_kind=self.source_kind,
                source_uri="fixture://authenticated-historical",
                retrieved_at=retrieved_at,
                raw_content_sha256=sha256(raw).hexdigest(),
                adjustment_basis="fixture unadjusted bars",
                use_case=DataUseCase.RESEARCH,
            ),
            candles=(
                Candle(start, 100, 102, 99, 101, 1000),
                Candle(start + timedelta(days=1), 101, 104, 100, 103, 1100),
            ),
        )


class UnconfiguredHistoricalProvider(FixtureAuthenticatedHistoricalProvider):
    credentials_configured = False


class AuthenticatedHistoricalCandleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repository = SqliteCandleDatasetRepository(
            Path(self.temp_dir.name) / "market_data.sqlite3"
        )
        self.provider = FixtureAuthenticatedHistoricalProvider()
        self.service = AuthenticatedHistoricalCandleService(self.repository, self.provider)
        self.start = datetime(2026, 8, 20, 9, 15, tzinfo=timezone.utc)
        self.request = MarketDataRequest(
            instrument_id="ANGEL_ONE:NSE:NSE:500325",
            interval="1d",
            start=self.start,
            end=self.start + timedelta(days=3),
            use_case=DataUseCase.RESEARCH,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_manual_research_sync_persists_immutable_dataset_and_status(self) -> None:
        before = self.service.status()
        dataset = self.service.sync(self.request, now=self.start + timedelta(days=4))
        after = self.service.status()

        self.assertEqual(before.availability, "not_downloaded")
        self.assertTrue(before.credentials_configured)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(after.availability, "available")
        self.assertEqual(after.dataset_id, dataset.dataset_id)
        self.assertEqual(after.candle_count, 2)
        self.assertEqual(self.service.preview(limit=1), dataset.candles[:1])

    def test_paper_requests_are_blocked_before_any_authenticated_fetch(self) -> None:
        paper_request = MarketDataRequest(
            instrument_id=self.request.instrument_id,
            interval=self.request.interval,
            start=self.request.start,
            end=self.request.end,
            use_case=DataUseCase.PAPER,
        )

        with self.assertRaisesRegex(ValueError, "research-only"):
            self.service.sync(paper_request, now=self.start + timedelta(days=4))

        self.assertEqual(self.provider.calls, 0)

    def test_unconfigured_status_blocks_sync_before_provider_fetch(self) -> None:
        provider = UnconfiguredHistoricalProvider()
        service = AuthenticatedHistoricalCandleService(self.repository, provider)

        self.assertEqual(service.status().availability, "local_configuration_required")
        with self.assertRaisesRegex(ValueError, "local read-only configuration"):
            service.sync(self.request, now=self.start + timedelta(days=4))

        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
