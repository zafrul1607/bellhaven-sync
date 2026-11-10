

import json
import requests
from pathlib import Path

BASE_URL = "https://analyst-assessment-production.up.railway.app"

response = requests.get(
    f"{BASE_URL}/api/openapi.json",
    timeout=30
)
response.raise_for_status()

spec = response.json()


# Find references to other schemas
def find_refs(obj):
    refs = set()

    if isinstance(obj, dict):
        if "$ref" in obj:
            refs.add(obj["$ref"])

        for value in obj.values():
            refs.update(find_refs(value))

    elif isinstance(obj, list):
        for value in obj:
            refs.update(find_refs(value))

    return refs


# Follow a reference to its actual definition
def resolve_ref(ref):
    result = spec

    for part in ref.removeprefix("#/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        result = result[part]

    return result


# Examine both write operations
operations = [
    ("post", "/api/v1/accounts"),
    ("patch", "/api/v1/accounts/{account_id}")
]

report = []

for method, path in operations:
    operation = spec["paths"][path][method]

    report.append(f"\n=== {method.upper()} {path} ===")

    body = operation.get("requestBody", {})

    pending = [("Request body", body)]
    visited = set()

    while pending:
        label, definition = pending.pop(0)

        report.append(f"\n{label}:")
        report.append(json.dumps(definition, indent=2))

        for ref in sorted(find_refs(definition)):
            if ref.startswith("#/") and ref not in visited:
                visited.add(ref)
                pending.append((ref, resolve_ref(ref)))


# Save a readable report
output = Path("data") / "account_write_schema.txt"

output.parent.mkdir(exist_ok=True)

output.write_text(
    "\n".join(report),
    encoding="utf-8"
)

print("API write schema inspection completed!")
print(f"Saved report to: {output}")
print("Operations inspected: POST and PATCH")
