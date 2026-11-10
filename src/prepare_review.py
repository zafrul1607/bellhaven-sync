
import csv
import json
import re
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


crm = load_json("crm_accounts.json")
website = load_json("website_facilities.json")
report = load_json("discrepancy_report.json")

crm_by_id = {
    str(account["account_id"]): account for account in crm
}


def normalize(value):
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


# Explain what the reviewer should investigate
RECOMMENDATIONS = {
    "apparently_correct": "Verify match; no change suggested",
    "incorrect_parent_review": "Verify identity and parent ownership",
    "outdated_name_review": "Verify facility rename",
    "name_match_address_review": "Investigate address difference",
    "possible_duplicate_review": "Compare all candidate CRM accounts",
    "unresolved_facility_review": "Search further before creating an account"
}


review_rows = []

for item in report["website_matches"]:

    facility = item["website_facility"]
    classification = item["classification"]
    candidates = item.get("candidates", [])

    # Include exact-name matches even when they were
    # missing from the top-five fuzzy candidates.
    candidate_ids = [
        str(c["account_id"]) for c in candidates
        if c.get("account_id")
    ]

    for account_id in item.get("exact_name_account_ids", []):
        account_id = str(account_id)
        if account_id not in candidate_ids:
            candidate_ids.append(account_id)

    selected_id = None

    # A single address match gives us a strong candidate,
    # but it still needs verification.
    if item.get("matched_account_id"):
        selected_id = str(item["matched_account_id"])

    # An exact name match without an address match
    # is still only a candidate.
    elif classification == "name_match_address_review":
        exact_ids = item.get("exact_name_account_ids", [])

        if len(exact_ids) == 1:
            selected_id = str(exact_ids[0])

    account = crm_by_id.get(selected_id, {}) if selected_id else {}

    name_score = ""

    if account:
        name_score = round(
            fuzz.token_sort_ratio(
                normalize(facility["name"]),
                normalize(account.get("name"))
            ),
            1
        )

    website_address = ", ".join([
        str(facility.get("street") or ""),
        str(facility.get("city") or ""),
        str(facility.get("state") or ""),
        str(facility.get("zip") or "")
    ])

    crm_address = ", ".join([
        str(account.get("billing_street") or ""),
        str(account.get("billing_city") or ""),
        str(account.get("billing_state") or ""),
        str(account.get("billing_zip") or "")
    ]) if account else ""

    warnings = []

    if classification == "unresolved_facility_review":
        warnings.append("No verified CRM match")

    if classification == "possible_duplicate_review":
        warnings.append("Multiple accounts at same address")

    if classification == "name_match_address_review":
        warnings.append("Name matches but address differs")

    if account and name_score < 65:
        warnings.append("Weak name similarity")

    if account and normalize(facility.get("city")) != normalize(
        account.get("billing_city")
    ):
        warnings.append("City mismatch")

    if item.get("financial_rule") == "preserve_old_create_new":
        warnings.append("CHOW: preserve old account")

    if item.get("financial_rule") == "verify_financial_fields":
        warnings.append("Verify financial history")

    review_rows.append({
        "website_name": facility["name"],
        "website_address": website_address,
        "website_care": "; ".join(
            facility.get("care_offerings", [])
        ),
        "website_url": facility["source_url"],
        "classification": classification,
        "crm_account_id": selected_id or "",
        "crm_name": account.get("name", ""),
        "crm_address": crm_address,
        "crm_parent": account.get("parent_name", ""),
        "crm_care": account.get("care_type", ""),
        "name_similarity": name_score,
        "lifetime_revenue": account.get("lifetime_revenue", ""),
        "outstanding_ar": account.get("outstanding_ar", ""),
        "financial_rule": item.get("financial_rule") or "",
        "candidate_account_ids": "; ".join(candidate_ids),
        "review_warnings": "; ".join(warnings),
        "recommended_investigation": RECOMMENDATIONS.get(
            classification, "Manual review"
        ),
        "review_status": "Pending"
    })


# Verify every website facility is represented
if len(review_rows) != len(website):
    raise ValueError("Review report is missing website facilities")

urls = [row["website_url"] for row in review_rows]

if len(urls) != len(set(urls)):
    raise ValueError("Duplicate website URLs detected")


# Save a human-readable CSV
output_file = DATA_DIR / "review_audit.csv"

with open(
    output_file, "w", newline="", encoding="utf-8-sig"
) as file:

    writer = csv.DictWriter(
        file, fieldnames=review_rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(review_rows)


# Save potentially stale accounts separately
stale_file = DATA_DIR / "stale_review.csv"

stale_accounts = report["possibly_stale_accounts"]

with open(
    stale_file, "w", newline="", encoding="utf-8-sig"
) as file:

    if stale_accounts:
        writer = csv.DictWriter(
            file, fieldnames=stale_accounts[0].keys()
        )
        writer.writeheader()
        writer.writerows(stale_accounts)


# Display the summary
print("=== REVIEW PREPARATION SUMMARY ===")
print(f"Website facilities: {len(review_rows)}")
print(f"Potentially stale CRM accounts: {len(stale_accounts)}")

print("\nReview classifications:")

counts = Counter(
    row["classification"] for row in review_rows
)

for category, count in sorted(counts.items()):
    print(f"{category}: {count}")

print("\nPotential corrections requiring verification:")

for row in review_rows:
    if row["classification"] == "apparently_correct":
        continue

    print(
        f"- {row['website_name']} "
        f"| {row['classification']}"
    )

print("\nFiles created:")
print("data/review_audit.csv")
print("data/stale_review.csv")
print("\nNo CRM records were modified.")
