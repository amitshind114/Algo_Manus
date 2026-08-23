# Offline Local Evidence Verifier

## Scope

Phase 6F provides a small local utility for checking an exported fixture-evidence JSON package. It accepts a local file path, reads it on the current machine, checks the supported schema/version, removes the `verification` object, reproduces the documented canonical JSON encoding, and compares the computed SHA-256 to the exported value.

```bash
python -m algo_manus.application.evidence_verification path/to/export.json
```

The utility prints a JSON result and exits with `0` only for a valid verification result. It does not upload a file, open a network connection, access a broker, alter SQLite records, regenerate a backtest, or submit any paper order.

## Supported outcomes

| Outcome | Meaning |
|---|---|
| `valid` | The supported schema/version and the canonical SHA-256 value match. |
| `mismatch` | The supported payload content does not reproduce the declared SHA-256 value. |
| `missing_verification` | The payload lacks the required local `verification.sha256` field. |
| `unsupported_schema` | The schema/version is not supported by this local verifier release. |
| `malformed` | The supplied text is not a supported JSON object or has invalid verification metadata. |

## Verification method

The verifier supports `algo-manus.local-evidence-summary` version `1` and `algo-manus.local-evidence-detail` version `1`. It reproduces the same canonicalization used during export: UTF-8 JSON, sorted keys, compact separators, ASCII escaping and no `verification` field in the hashed payload. It compares SHA-256 values locally using a constant-time string comparison.

## Limits

`valid` means the local payload content matches its own declared verification metadata under the supported canonicalization. It does **not** establish source identity, broker origin, market-data accuracy, research validity, performance, execution, a trusted timestamp, a digital signature, or tamper resistance. A person able to modify both a file and its verification value can create another matching local package.

The tool is an offline fixture-evidence comparison aid only. It has no broker SDK, provider API, credential, cloud verifier, upload capability, scheduler, real paper-broker connection or live-execution capability.

This is research and analysis only, not personalized financial advice.
