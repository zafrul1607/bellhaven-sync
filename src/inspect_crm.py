
import json
from pathlib import Path

import pandas as pd

# Step 1: Locate our saved CRM dataset
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "crm_accounts.json"

# Step 2: Load the JSON file
with open(DATA_FILE, "r", encoding="utf-8") as file:
    accounts = json.load(file)

# Step 3: Convert JSON records into a pandas DataFrame
df = pd.DataFrame(accounts)

print("=== BELLHAVEN CRM DATA ANALYSIS ===")

# Step 4: Examine the dataset
print(f"\nTotal CRM accounts: {len(df)}")

print("\nAvailable columns:")
print(df.columns.tolist())

print("\nAccount statuses:")
print(df["status"].fillna("(Missing)").value_counts())

# Step 5: Examine parent companies
print("\nTop parent company labels:")
print(
    df["parent_name"]
    .fillna("(Missing)")
    .value_counts()
    .head(10)
)

print("\nAccounts with Bellhaven in parent name:")
bellhaven_accounts = df[
    df["parent_name"]
    .fillna("")
    .str.contains("Bellhaven", case=False, regex=False)
]

print(len(bellhaven_accounts))

# Step 6: Check missing addresses
print("\nMissing address information:")

for column in [
    "billing_street",
    "billing_city",
    "billing_state",
    "billing_zip"
]:
    missing = (
        df[column].fillna("").astype(str).str.strip() == ""
    ).sum()

    print(f"{column}: {missing}")

# Step 7: Examine financial information
revenue = pd.to_numeric(
    df["lifetime_revenue"], errors="coerce"
).fillna(0)

outstanding_ar = pd.to_numeric(
    df["outstanding_ar"], errors="coerce"
).fillna(0)

print("\nAccounts with revenue history:", (revenue > 0).sum())

print(
    "Accounts with positive outstanding AR:",
    (outstanding_ar > 0).sum()
)

print(
    "Accounts with both revenue and positive AR:",
    ((revenue > 0) & (outstanding_ar > 0)).sum()
)

# Step 8: Check existing duplicate records
duplicate_links = (
    df["duplicate_of_account"]
    .fillna("")
    .astype(str)
    .str.strip() != ""
)

print("\nAccounts already linked as duplicates:", duplicate_links.sum())

print("\nCRM analysis completed successfully!")
