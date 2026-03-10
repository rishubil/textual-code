#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    echo 'Usage: ./scripts/check-licenses.sh

Check licenses of Python dependencies in this project.
Inspects all packages installed in the uv virtual environment and reports
any that use disallowed licenses (GPL, AGPL, etc.).

Exit codes:
  0  All licenses allowed
  1  Disallowed license found
'
    exit
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

main() {
    echo "=== License check started ==="
    echo ""

    uv run python - << 'PYEOF'
import importlib.metadata
import sys

# License classification criteria
ALLOWED = {"MIT", "BSD", "ISC", "APACHE", "APACHE-2.0", "APACHE 2.0", "PSF", "PYTHON SOFTWARE FOUNDATION", "LGPL", "MPL", "MPL-2.0", "MOZILLA PUBLIC LICENSE 2.0", "CC0", "UNLICENSE", "PUBLIC DOMAIN"}
BLOCKED = {"GPL", "GPL-2.0", "GPL-3.0", "AGPL", "AGPL-3.0", "GNU GENERAL PUBLIC LICENSE", "GNU AFFERO GENERAL PUBLIC LICENSE"}
WARN = {"LGPL-2.0", "LGPL-2.1", "LGPL-3.0"}

def get_license(meta):
    """Extract license from package metadata."""
    license_val = meta.get("License") or meta.get("License-Expression") or ""
    if license_val and license_val.strip() and license_val.strip() != "UNKNOWN":
        return license_val.strip()
    # Fall back to Classifier
    classifiers = meta.get_all("Classifier") or []
    for c in classifiers:
        if c.startswith("License ::"):
            parts = c.split(" :: ")
            if len(parts) >= 3:
                return parts[-1].strip()
    return "UNKNOWN"

def classify(license_str):
    upper = license_str.upper()
    for blocked in BLOCKED:
        if blocked in upper:
            return "BLOCKED"
    for warn in WARN:
        if warn in upper:
            return "WARN"
    for allowed in ALLOWED:
        if allowed in upper:
            return "OK"
    return "UNKNOWN"

# Collect all installed distributions
try:
    dists = list(importlib.metadata.distributions())
except Exception as e:
    print(f"Error: could not retrieve package list: {e}", file=sys.stderr)
    sys.exit(1)

results = []
for dist in dists:
    try:
        meta = dist.metadata
        name = meta["Name"] or "unknown"
        version = meta["Version"] or "unknown"
        license_str = get_license(meta)
        status = classify(license_str)
        results.append((name, version, license_str, status))
    except Exception:
        continue

results.sort(key=lambda x: (x[3] == "OK", x[0].lower()))

blocked = [(n, v, l) for n, v, l, s in results if s == "BLOCKED"]
warned  = [(n, v, l) for n, v, l, s in results if s == "WARN"]
unknown = [(n, v, l) for n, v, l, s in results if s == "UNKNOWN"]
ok      = [(n, v, l) for n, v, l, s in results if s == "OK"]

# Print results
if blocked:
    print("❌ Disallowed licenses found:")
    for name, ver, lic in blocked:
        print(f"   {name} {ver} — {lic}")
    print("")

if warned:
    print("⚠️  Licenses requiring review (LGPL):")
    for name, ver, lic in warned:
        print(f"   {name} {ver} — {lic}")
    print("")

if unknown:
    print("❓ License unknown (manual check required):")
    for name, ver, lic in unknown:
        print(f"   {name} {ver} — {lic}")
    print("")

print(f"✅ Allowed packages: {len(ok)}")
if blocked or warned:
    print(f"❌ Blocked packages: {len(blocked)}")
    print(f"⚠️  Warning packages: {len(warned)}")
if unknown:
    print(f"❓ Unknown packages: {len(unknown)}")

print("")
print(f"Checked {len(results)} packages total")

if blocked:
    sys.exit(1)
PYEOF

}

main "$@"
