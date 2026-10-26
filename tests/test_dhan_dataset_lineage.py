from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from algo_manus.application.market_data import MarketDataRequest, MarketDataService
from algo_manus.domain.market_data import DataSourceKind, DataUseCase
from algo_manus.infrastructure.market_data.dhan_historical import DhanHistoricalCandleProvider
from algo_manus.infrastructure.market_data.sqlite_repository import SqliteCandleDatasetRepository


class DhanDatasetLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "dhan_datasets.sqlite3"
        self.start = datetime(2026, 8, 3, 9, 15, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=5)
        self.retrieved_at = self.end + timedelta(hours=1)
        self.instrument_id = "DHAN:NSE_EQ:1333"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _payload(self, close_second: float = 102.0) -> dict:
        base = int(self.start.timestamp())
        return {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, close_second],
            "volume": [1000, 1100],
            "timestamp": [base, base + 300],
        }

    def _provider(self, payload: dict) -> DhanHistoricalCandleProvider:
        encoded = json.dumps(payload).encode("utf-8")

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            return encoded

        return DhanHistoricalCandleProvider(
            credentials=type("Credentials", (), {"access_token": "test-token"})(),
            transport=transport,
        )

    def _request(self) -> MarketDataRequest:
        return MarketDataRequest(
            instrument_id=self.instrument_id,
            interval="5m",
            start=self.start,
            end=self.end,
            use_case=DataUseCase.RESEARCH,
        )

    def test_persists_and_restores_dhan_dataset_with_full_lineage(self) -> None:
        repository = SqliteCandleDatasetRepository(self.database_path)
        service = MarketDataService(repository)
        dataset = service.ingest(
            self._provider(self._payload()),
            self._request(),
            retrieved_at=self.retrieved_at,
        )

        restored_repository = SqliteCandleDatasetRepository(self.database_path)
        restored = restored_repository.get(dataset.dataset_id)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.dataset_id, dataset.dataset_id)
        self.assertEqual(restored.instrument_id, self.instrument_id)
        self.assertEqual(restored.provenance.source_name, "dhan")
        self.assertEqual(restored.provenance.source_kind, DataSourceKind.BROKER)
        self.assertEqual(restored.provenance.use_case, DataUseCase.RESEARCH)
        self.assertEqual(restored.provenance.raw_content_sha256, dataset.provenance.raw_content_sha256)
        self.assertEqual(restored.provenance.retrieved_at, self.retrieved_at)
        self.assertEqual(len(restored.candles), 2)
        self.assertEqual(restored.candles[0].timestamp, self.start)

    def test_identical_response_is_idempotent_and_does_not_duplicate_candles(self) -> None:
        repository = SqliteCandleDatasetRepository(self.database_path)
        service = MarketDataService(repository)
        first = service.ingest(
            self._provider(self._payload()),
            self._request(),
            retrieved_at=self.retrieved_at,
        )
        second = service.ingest(
            self._provider(self._payload()),
            self._request(),
            retrieved_at=self.retrieved_at,
        )

        self.assertEqual(first.dataset_id, second.dataset_id)
        restored = repository.get(first.dataset_id)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(len(restored.candles), 2)

    def test_different_response_with_same_identity_raises_lineage_conflict(self) -> None:
        repository = SqliteCandleDatasetRepository(self.database_path)
        service = MarketDataService(repository)
        first = service.ingest(
            self._provider(self._payload()),
            self._request(),
            retrieved_at=self.retrieved_at,
        )

        with self.assertRaisesRegex(ValueError, "retained dataset identity conflict"):
            service.ingest(
                self._provider(self._payload(close_second=103.0)),
                self._request(),
                retrieved_at=self.retrieved_at,
            )

        restored = repository.get(first.dataset_id)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(len(restored.candles), 2)
        self.assertEqual(restored.candles[1].close, 102.0)

    def test_different_response_creates_distinct_immutable_dataset(self) -> None:
        repository = SqliteCandleDatasetRepository(self.database_path)
        service = MarketDataService(repository)
        first = service.ingest(
            self._provider(self._payload()),
            self._request(),
            retrieved_at=self.retrieved_at,
        )
        second = service.ingest(
            self._provider(self._payload(close_second=104.0)),
            self._request(),
            retrieved_at=self.retrieved_at + timedelta(minutes=1),
        )

        self.assertNotEqual(first.dataset_id, second.dataset_id)
        self.assertNotEqual(
            first.provenance.raw_content_sha256,
            second.provenance.raw_content_sha256,
        )
        self.assertIsNotNone(repository.get(first.dataset_id))
        self.assertIsNotNone(repository.get(second.dataset_id))


if __name__ == "__main__":
    unittest.main()
