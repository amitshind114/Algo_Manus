from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from algo_manus.application.market_data import DataPolicyError, MarketDataRequest, MarketDataService
from algo_manus.domain.market_data import (
    Candle,
    CandleDataset,
    DataProvenance,
    DataSourceKind,
    DataUseCase,
)
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository


class FixtureMarketDataProvider:
    def __init__(self, source_kind: DataSourceKind, use_case: DataUseCase) -> None:
        self.source_name = "fixture-broker" if source_kind is DataSourceKind.BROKER else "fixture-public"
        self.source_kind = source_kind
        self.use_case = use_case
        self.calls = 0

    def fetch_candles(self, *, instrument_id, interval, start, end, retrieved_at):
        self.calls += 1
        raw = b"fixture-candles-v1"
        provenance = DataProvenance(
            source_name=self.source_name,
            source_kind=self.source_kind,
            source_uri="fixture://market-data/candles",
            retrieved_at=retrieved_at,
            raw_content_sha256=sha256(raw).hexdigest(),
            adjustment_basis="unadjusted fixture bars",
            use_case=self.use_case,
        )
        return CandleDataset.create(
            instrument_id=instrument_id,
            interval=interval,
            provenance=provenance,
            candles=(
                Candle(start, 100, 104, 99, 103, 1000),
                Candle(start + timedelta(days=1), 103, 106, 102, 105, 1200),
            ),
        )


class MarketDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SqliteCandleDatasetRepository(Path(self.temp_dir.name) / "market_data.sqlite3")
        self.start = datetime(2026, 8, 20, 9, 15, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _request(self, use_case: DataUseCase) -> MarketDataRequest:
        return MarketDataRequest(
            instrument_id="ANGEL_ONE:NSE:NSE:500325",
            interval="1d",
            start=self.start,
            end=self.end,
            use_case=use_case,
        )

    def test_research_accepts_fixture_data_and_persists_lineage(self) -> None:
        provider = FixtureMarketDataProvider(DataSourceKind.FIXTURE, DataUseCase.RESEARCH)
        dataset = MarketDataService(self.repository).ingest(provider, self._request(DataUseCase.RESEARCH))

        restored = self.repository.get(dataset.dataset_id)

        self.assertEqual(provider.calls, 1)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.provenance.source_kind, DataSourceKind.FIXTURE)
        self.assertEqual(len(restored.candles), 2)

    def test_paper_rejects_non_broker_source_before_fetch(self) -> None:
        provider = FixtureMarketDataProvider(DataSourceKind.PUBLIC_FALLBACK, DataUseCase.PAPER)

        with self.assertRaisesRegex(DataPolicyError, "broker-authoritative"):
            MarketDataService(self.repository).ingest(provider, self._request(DataUseCase.PAPER))

        self.assertEqual(provider.calls, 0)

    def test_provider_cannot_return_mismatched_policy_context(self) -> None:
        provider = FixtureMarketDataProvider(DataSourceKind.BROKER, DataUseCase.RESEARCH)

        with self.assertRaisesRegex(DataPolicyError, "use case"):
            MarketDataService(self.repository).ingest(provider, self._request(DataUseCase.PAPER))


if __name__ == "__main__":
    unittest.main()
