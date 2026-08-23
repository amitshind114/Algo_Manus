"""Offline verification for local fixture evidence exports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import hmac
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


_CANONICALIZATION = "utf-8 JSON, sort_keys=true, separators=(',', ':'), verification excluded"
_SUPPORTED_SCHEMAS = {
    ("algo-manus.local-evidence-summary", 1),
    ("algo-manus.local-evidence-detail", 1),
}


class EvidenceVerificationStatus(str, Enum):
    VALID = "valid"
    MISMATCH = "mismatch"
    MISSING_VERIFICATION = "missing_verification"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class EvidenceVerificationResult:
    status: EvidenceVerificationStatus
    schema: str | None
    schema_version: int | None
    declared_sha256: str | None
    computed_sha256: str | None
    detail: str

    @property
    def is_valid(self) -> bool:
        return self.status is EvidenceVerificationStatus.VALID


class LocalEvidenceVerifier:
    """Verify an already-loaded local export payload without side effects."""

    def verify_json(self, text: str) -> EvidenceVerificationResult:
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return self._result(EvidenceVerificationStatus.MALFORMED, detail="payload is not valid JSON")
        return self.verify_payload(payload)

    def verify_payload(self, payload: object) -> EvidenceVerificationResult:
        if not isinstance(payload, Mapping):
            return self._result(EvidenceVerificationStatus.MALFORMED, detail="payload must be a JSON object")
        schema = payload.get("schema")
        schema_version = payload.get("schema_version")
        if not isinstance(schema, str) or not isinstance(schema_version, int):
            return self._result(EvidenceVerificationStatus.MALFORMED, detail="schema and schema_version are required")
        if (schema, schema_version) not in _SUPPORTED_SCHEMAS:
            return self._result(
                EvidenceVerificationStatus.UNSUPPORTED_SCHEMA,
                schema=schema,
                schema_version=schema_version,
                detail="local verifier does not support this export schema/version",
            )
        verification = payload.get("verification")
        if not isinstance(verification, Mapping) or not isinstance(verification.get("sha256"), str):
            return self._result(
                EvidenceVerificationStatus.MISSING_VERIFICATION,
                schema=schema,
                schema_version=schema_version,
                detail="verification.sha256 is required",
            )
        declared = verification["sha256"]
        if (
            verification.get("algorithm") != "sha256"
            or verification.get("canonicalization") != _CANONICALIZATION
        ):
            return self._result(
                EvidenceVerificationStatus.MALFORMED,
                schema=schema,
                schema_version=schema_version,
                declared_sha256=declared,
                detail="verification metadata does not match the supported canonicalization",
            )
        canonical_payload = {key: value for key, value in payload.items() if key != "verification"}
        try:
            canonical = json.dumps(
                canonical_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return self._result(
                EvidenceVerificationStatus.MALFORMED,
                schema=schema,
                schema_version=schema_version,
                declared_sha256=declared,
                detail="payload cannot be canonicalized as supported JSON",
            )
        computed = sha256(canonical).hexdigest()
        status = EvidenceVerificationStatus.VALID if hmac.compare_digest(declared, computed) else EvidenceVerificationStatus.MISMATCH
        return self._result(
            status,
            schema=schema,
            schema_version=schema_version,
            declared_sha256=declared,
            computed_sha256=computed,
            detail="canonical SHA-256 matches" if status is EvidenceVerificationStatus.VALID else "canonical SHA-256 does not match",
        )

    @staticmethod
    def _result(
        status: EvidenceVerificationStatus,
        *,
        schema: str | None = None,
        schema_version: int | None = None,
        declared_sha256: str | None = None,
        computed_sha256: str | None = None,
        detail: str,
    ) -> EvidenceVerificationResult:
        return EvidenceVerificationResult(
            status=status,
            schema=schema,
            schema_version=schema_version,
            declared_sha256=declared_sha256,
            computed_sha256=computed_sha256,
            detail=detail,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Verify a local JSON file entirely on the current machine."""

    import argparse

    parser = argparse.ArgumentParser(description="Verify a local Algo Manus fixture evidence JSON export")
    parser.add_argument("path", type=Path, help="local JSON export file to verify")
    arguments = parser.parse_args(argv)
    try:
        text = arguments.path.read_text(encoding="utf-8")
    except OSError as error:
        print(json.dumps({"status": "malformed", "detail": f"cannot read local file: {error}"}))
        return 2
    result = LocalEvidenceVerifier().verify_json(text)
    print(json.dumps({**asdict(result), "status": result.status.value}, indent=2, sort_keys=True))
    return 0 if result.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
