"""Resolve immutable persisted research evidence required to promote local paper proposals."""

from __future__ import annotations

from algo_manus.application.experiment_evidence import ExperimentEvidenceReadService
from algo_manus.domain.paper import PaperPromotionEvidence
from algo_manus.domain.research import DataValidationStatus, DatasetValidationOutcome


class PaperResearchPromotionService:
    """Read-only evidence resolver; it cannot create or upgrade research outcomes."""

    def __init__(self, evidence: ExperimentEvidenceReadService) -> None:
        self._evidence = evidence

    def resolve(
        self,
        *,
        batch_id: str,
        instrument_id: str,
    ) -> tuple[PaperPromotionEvidence, DatasetValidationOutcome] | None:
        view = self._evidence.get(batch_id)
        if view is None:
            return None
        result = next((item for item in view.batch.results if item.instrument_id == instrument_id), None)
        if result is None or view.manifest.parameter_revision_id != view.batch.parameter_revision_id:
            return None
        outcome = next(
            (item for item in view.manifest.validation_outcomes if item.dataset_id == result.dataset_id),
            None,
        )
        if outcome is None or outcome.status is not DataValidationStatus.ACCEPTED:
            return None
        return (
            PaperPromotionEvidence(
                batch_id=view.batch.batch_id,
                manifest_id=view.manifest.manifest_id,
                dataset_id=outcome.dataset_id,
                validation_policy_version=outcome.policy_version,
            ),
            outcome,
        )
