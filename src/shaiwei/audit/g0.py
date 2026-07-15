"""Assemble the frozen G0 decision from matching immutable evidence reports."""

import json
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.shadow.manifest import verify_signal_manifest


def _latest_matching(directory: Path, pattern: str, data_hash: str, code_hash: str) -> tuple[Path, dict]:
    for path in sorted(directory.glob(pattern), reverse=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("data_snapshot_sha256") == data_hash and payload.get("code_snapshot_sha256") == code_hash:
            return path, payload
    raise FileNotFoundError(f"no matching {pattern} report in {directory}")


def main() -> int:
    settings = load()
    data_hash = ingest_snapshot_sha256()
    code_hash = code_snapshot_sha256()
    missing = []
    evidence: dict[str, object] = {}
    reports: dict[str, tuple[Path, dict]] = {}
    for name, directory, pattern in (
        ("sentinel", PROJECT_ROOT / "logs/sentinels", "*.json"),
        ("baseline", PROJECT_ROOT / "logs/backtest", "stage0_baseline_*.json"),
        ("alphagen", PROJECT_ROOT / "logs/benchmark", "alphagen_cpu_*.json"),
    ):
        try:
            reports[name] = _latest_matching(directory, pattern, data_hash, code_hash)
        except FileNotFoundError as error:
            missing.append(str(error))

    if "sentinel" in reports:
        path, sentinel = reports["sentinel"]
        by_name = {result["sentinel"]: result for result in sentinel["results"]}
        required_pass = all(by_name[f"S{number}"]["status"] == "PASS" for number in range(1, 10))
        s10_status = by_name["S10"]["status"]
        s10_pass = s10_status == "PASS" or (
            settings.runtime.environment != "prod" and s10_status == "NOT_APPLICABLE"
        )
        evidence["sentinels"] = {
            "report_path": str(path),
            "condition_pass": required_pass and s10_pass,
            "required_failures": sentinel["required_failures"],
            "s4_units": by_name["S4"],
        }
    if "baseline" in reports:
        path, baseline = reports["baseline"]
        evidence["backtest"] = {"report_path": str(path), **baseline["g0_backtest"]}
    if "alphagen" in reports:
        path, alphagen = reports["alphagen"]
        evidence["alphagen_cpu"] = {"report_path": str(path), **alphagen["summary"]}

    signal_evidence = None
    manifests = sorted((PROJECT_ROOT / "signals").glob("*.json"), reverse=True)
    if manifests:
        document = json.loads(manifests[0].read_text(encoding="utf-8"))
        if (
            document.get("data_snapshot_sha256") == data_hash
            and document.get("code_snapshot_sha256") == code_hash
        ):
            signal_evidence = {
                "manifest_path": str(manifests[0]),
                "signal_sha256": verify_signal_manifest(manifests[0]),
            }
    if signal_evidence is None:
        missing.append("no shadow manifest matches the current data and code snapshots")
    else:
        evidence["shadow"] = signal_evidence

    sentinels_pass = bool(evidence.get("sentinels", {}).get("condition_pass", False))
    backtest = evidence.get("backtest", {})
    windows_pass = bool(backtest.get("window_condition_pass", False))
    cost_pass = bool(backtest.get("cost_1_5_condition_pass", False))
    g0_formula_pass = sentinels_pass and windows_pass and cost_pass
    stage0_complete = g0_formula_pass and not missing
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "status": "PASS" if stage0_complete else "FAIL",
        "g0": {
            "sentinels_condition_pass": sentinels_pass,
            "window_condition_pass": windows_pass,
            "cost_1_5_condition_pass": cost_pass,
            "pass": g0_formula_pass,
        },
        "hands_on_verification": {
            "vwap_units_evidence_present": "sentinels" in evidence,
            "alphagen_cpu_evidence_present": "alphagen_cpu" in evidence,
        },
        "missing_evidence": missing,
        "evidence": evidence,
        "stage0_complete": stage0_complete,
        "next_phase_authorized": False,
    }
    output_dir = PROJECT_ROOT / "logs/audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"g0_{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**payload, "report_path": str(output)}, ensure_ascii=False, sort_keys=True))
    return 0 if stage0_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
