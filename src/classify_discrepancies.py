
import json
import re
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


# Step 1: Read our existing datasets
def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


crm = load_json("crm_accounts.json")
website = load_json("website_facilities.json")
matches = load_json("match_candidates.json")


# Standardize names for comparison
def normalize(value):
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


# Convert financial values safely
def money(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


# Step 2: Identify the Bellhaven parent account
parents = [
    account for account in crm
    if normalize(account.get("name"))
    == normalize("Bellhaven Senior Living (Parent Account)")
]

if len(parents) != 1:
    raise ValueError(
        f"Expected one Bellhaven parent account; found {len(parents)}"
    )

bellhaven_id = str(parents[0]["account_id"])

crm_by_id = {
    str(account["account_id"]): account
    for account in crm
}

facility_accounts = [
    account for account in crm
    if "(parent account)" not in
    str(account.get("name") or "").lower()
]


# Step 3: Classify the website matches
classified = []
plausible_account_ids = set()

for match in matches:

    facility = match["website_facility"]
    match_type = match["match_type"]
    candidates = match["candidates"]

    record = {
        "website_facility": facility,
        "classification": "",
        "candidates": candidates[:5],
        "financial_rule": None,
        "evidence": {
            "website_url": facility["source_url"],
            "matching_method": match_type
        }
    }

    if match_type == "single_address_match":

        account_id = str(candidates[0]["account_id"])
        account = crm_by_id[account_id]
        plausible_account_ids.add(account_id)

        record["matched_account_id"] = account_id

        current_parent = str(account.get("parent_id") or "")

        if current_parent != bellhaven_id:

            record["classification"] = "incorrect_parent_review"

            revenue = money(account.get("lifetime_revenue"))
            ar = money(account.get("outstanding_ar"))

            if revenue is None or ar is None:
                record["financial_rule"] = "verify_financial_fields"

            elif revenue > 0 and ar > 0:
                record["financial_rule"] = "preserve_old_create_new"

            else:
                record["financial_rule"] = "reparent_existing"

        elif normalize(facility["name"]) != normalize(
            account.get("name")
        ):

            record["classification"] = "outdated_name_review"

        else:
            record["classification"] = "apparently_correct"

    elif match_type == "multiple_accounts_same_address":

        record["classification"] = "possible_duplicate_review"

        for candidate in candidates:
            plausible_account_ids.add(
                str(candidate["account_id"])
            )

    else:
        # Search ALL CRM accounts for identical names.
        # Don't rely on the earlier top-five ranking.
        exact_name_matches = [
            account for account in facility_accounts
            if normalize(account.get("name"))
            == normalize(facility["name"])
        ]

        record["exact_name_account_ids"] = [
            account["account_id"]
            for account in exact_name_matches
        ]

        if exact_name_matches:
            record["classification"] = "name_match_address_review"

            for account in exact_name_matches:
                plausible_account_ids.add(
                    str(account["account_id"])
                )

        else:
            record["classification"] = "unresolved_facility_review"

    classified.append(record)


# Step 4: Find Bellhaven accounts not clearly on website
website_names = {
    normalize(facility["name"])
    for facility in website
}

possibly_stale = []

for account in facility_accounts:

    if str(account.get("parent_id") or "") != bellhaven_id:
        continue

    account_id = str(account["account_id"])

    if account_id in plausible_account_ids:
        continue

    if normalize(account.get("name")) in website_names:
        continue

    possibly_stale.append({
        "account_id": account_id,
        "name": account.get("name"),
        "status": account.get("status"),
        "parent_id": account.get("parent_id"),
        "reason": "No confirmed website correspondence",
        "classification": "possible_stale_review"
    })


# Step 5: Save the discrepancy report
report = {
    "bellhaven_parent_id": bellhaven_id,
    "website_matches": classified,
    "possibly_stale_accounts": possibly_stale
}

output_file = DATA_DIR / "discrepancy_report.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(report, file, indent=4)


# Step 6: Display results
counts = Counter(
    item["classification"]
    for item in classified
)

print("\n=== CRM DISCREPANCY REPORT ===")

for category, count in sorted(counts.items()):
    print(f"{category}: {count}")

print(f"\nWebsite facilities analyzed: {len(classified)}")
print(f"Potentially stale Bellhaven accounts: {len(possibly_stale)}")

financial_counts = Counter(
    item["financial_rule"]
    for item in classified
    if item["financial_rule"]
)

print("\nOwnership correction rules:")

for rule, count in sorted(financial_counts.items()):
    print(f"{rule}: {count}")

print(f"\nSaved report to: {output_file.name}")
print("No CRM records were modified.")
