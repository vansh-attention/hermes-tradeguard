"""Verify cited-source bookkeeping and optionally exact pinned license bytes.

Developer command, never called by the plugin. --verify-licenses enables HTTPS
requests to fixed raw.githubusercontent.com URLs already recorded in ledgers.
The mechanical check does not certify paper conclusions or validate trading alpha.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-licenses", action="store_true")
    args = parser.parse_args(argv)
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "ledgers": {}, "errors": [],
              "mechanical_checks_only": True, "license_network_enabled": args.verify_licenses}
    unique_urls, pins, license_files = set(), set(), {}
    total_records = total_occurrences = 0
    for prefix, name, document in (
        ("eq", "sources_equity.json", "equity_etf_strategy_library.md"),
        ("micro", "sources_microstructure.json", "microstructure_ml_validation.md"),
    ):
        data = json.loads((ROOT / "docs" / "research" / name).read_text())
        rows = data["sources"]
        body, source_section = re.split(r"^## Sources\s*$", (ROOT / "docs" / "research" / document).read_text(), maxsplit=1, flags=re.MULTILINE)
        occurrences = re.findall(r"\[(\d+)\]", body)
        citations = {int(x) for x in occurrences}
        ids = {r["id"] for r in rows}
        listed = {int(key): url for key, url in re.findall(r"^\[(\d+)\]\s+(https?://\S+)", source_section, flags=re.MULTILINE)}
        problems = []
        if len(ids) != len(rows):
            problems.append("duplicate source IDs")
        if citations != ids:
            problems.append(f"citation/ledger mismatch: unknown={sorted(citations-ids)}, unused={sorted(ids-citations)}")
        if ids != set(listed):
            problems.append("Sources section IDs differ from ledger")
        if data.get("source_count") != len(rows):
            problems.append("declared source_count mismatch")
        for row in rows:
            unique_urls.add(row["url"])
            if listed.get(row["id"]) != row["url"]:
                problems.append(f"source {row['id']} URL mismatch")
            accessed = row.get("accessed_date", row.get("accessed_on"))
            if accessed != data["audit_date"]:
                problems.append(f"source {row['id']} audit/access date mismatch")
            audit = row.get("audit_verification", {})
            if not audit.get("supporting_excerpt_matched"):
                problems.append(f"source {row['id']} has no recorded excerpt verification")
            if "repository" in row:
                revision = row.get("revision", "")
                if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
                    problems.append(f"source {row['id']} has malformed commit pin")
                pins.add((row["repository"], revision))
            for field, hash_field in (("license_raw_url", "license_sha256"), ("license_notice_url", "license_notice_sha256")):
                if field in row:
                    license_files[row[field]] = row.get(hash_field)
        total_records += len(rows)
        total_occurrences += len(occurrences)
        report["ledgers"][prefix] = {"records": len(rows), "cited_ids": len(citations),
            "citation_occurrences": len(occurrences), "errors": problems}
        report["errors"].extend(f"{prefix}: {problem}" for problem in problems)
    report.update(source_records=total_records, distinct_source_urls=len(unique_urls),
                  citation_occurrences=total_occurrences, repository_commit_pins=len(pins))
    if args.verify_licenses:
        from tradeguard.providers import _tls_context
        checked = []
        for url, expected in sorted(license_files.items()):
            try:
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com" or re.search(r"/[0-9a-f]{40}/", parsed.path) is None:
                    raise ValueError("license URL must be a full-SHA pin at the official raw host")
                with urlopen(Request(url, headers={"User-Agent": "HermesTradeGuard/0.1 source-audit"}),
                             context=_tls_context(), timeout=20) as response:
                    if urlparse(response.url).hostname != "raw.githubusercontent.com":
                        raise ValueError("unexpected license redirect")
                    body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise ValueError("license response exceeds limit")
                actual = hashlib.sha256(body).hexdigest()
                if actual != expected:
                    raise ValueError("pinned license bytes differ from recorded SHA-256")
                checked.append({"url": url, "sha256": actual, "verified": True})
            except (OSError, ValueError) as exc:
                report["errors"].append(f"license: {url}: {exc}")
        report["pinned_license_files"] = checked
    from tradeguard.catalog import strategy_catalog
    report["runtime_research_families"] = strategy_catalog()["count"]
    report["ok"] = not report["errors"]
    filename = "source_integrity.json" if args.verify_licenses else "source_integrity_mechanical.json"
    destination = ROOT / "artifacts" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
