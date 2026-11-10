
import os
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "reviews.db"
BASE = "https://analyst-assessment-production.up.railway.app/api/v1"

load_dotenv(ROOT / ".env")


class UnsafeChange(Exception):
    pass


# Save approved, rejected, and uncertain actions
def record_action(item_id, status, account_id, detail):
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_actions (
                item_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                account_id TEXT NOT NULL,
                detail TEXT NOT NULL
            )
        """)

        conn.execute("""
            INSERT INTO crm_actions VALUES (?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                status=excluded.status,
                account_id=excluded.account_id,
                detail=excluded.detail
        """, (item_id, status, account_id, detail))


def read_action(item_id):
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_actions (
                item_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                account_id TEXT NOT NULL,
                detail TEXT NOT NULL
            )
        """)

        row = conn.execute("""
            SELECT status, account_id, detail
            FROM crm_actions WHERE item_id=?
        """, (item_id,)).fetchone()

    return dict(
        zip(("status", "account_id", "detail"), row)
    ) if row else None


# Authenticate with the CRM API
def headers():
    token = os.getenv("BELLHAVEN_API_TOKEN")

    if not token:
        raise UnsafeChange("API token missing in .env")

    return {"Authorization": f"Bearer {token}"}


# Retrieve the current CRM record
def fetch_account(account_id):
    response = requests.get(
        f"{BASE}/accounts/{account_id}",
        headers=headers(),
        timeout=20
    )
    response.raise_for_status()

    payload = response.json()

    account = (
        payload.get("data", payload)
        if isinstance(payload, dict) else None
    )

    if (
        not isinstance(account, dict)
        or str(account.get("account_id")) != str(account_id)
    ):
        raise UnsafeChange("Could not verify CRM account details")

    return account


# Normalize addresses before comparing
def street(value):
    replacements = {
        "rd": "road",
        "st": "street",
        "dr": "drive",
        "ave": "avenue",
        "ln": "lane",
        "blvd": "boulevard",
        "ct": "court",
        "pkwy": "parkway"
    }

    parts = re.sub(
        r"[^a-z0-9\s]", " ",
        str(value or "").lower()
    ).split()

    return " ".join(
        replacements.get(part, part) for part in parts
    )


def zip5(value):
    match = re.search(r"\d{5}", str(value or ""))
    return match.group() if match else ""


def amount(value):
    try:
        if value is None or str(value).strip() == "":
            raise InvalidOperation

        number = Decimal(str(value).replace(",", ""))

        if not number.is_finite():
            raise InvalidOperation

        return number

    except (InvalidOperation, ValueError):
        raise UnsafeChange(
            "Financial data is missing or invalid"
        )


# Apply one verified, non-CHOW parent correction
def apply_reparent(
    account_id,
    expected_parent_id,
    bellhaven_parent_id,
    website
):
    current = fetch_account(account_id)
    parent = fetch_account(bellhaven_parent_id)

    if parent.get("name") != "Bellhaven Senior Living (Parent Account)":
        raise UnsafeChange("Target parent could not be verified")

    # Prevent a repeated update
    if str(current.get("parent_id") or "") == str(bellhaven_parent_id):
        return "Already correct; no PATCH needed"

    # Make sure CRM ownership has not changed since extraction
    if str(current.get("parent_id") or "") != str(expected_parent_id):
        raise UnsafeChange(
            "Parent changed since initial extraction"
        )

    # Verify that the CRM record matches the website address
    if not (
        street(website.get("street"))
        and street(website.get("street"))
        == street(current.get("billing_street"))
        and zip5(website.get("zip"))
        and zip5(website.get("zip"))
        == zip5(current.get("billing_zip"))
        and str(website.get("state") or "").lower()
        == str(current.get("billing_state") or "").lower()
    ):
        raise UnsafeChange(
            "Live CRM address differs from website; update blocked"
        )

    # Enforce the special CHOW business rule
    if (
        amount(current.get("lifetime_revenue")) > 0
        and amount(current.get("outstanding_ar")) > 0
    ):
        raise UnsafeChange(
            "CHOW required; never reparent this existing account"
        )

    # Send one approved change; no automatic retry
    response = requests.patch(
        f"{BASE}/accounts/{account_id}",
        headers=headers(),
        json={"parent_id": bellhaven_parent_id},
        timeout=20
    )
    response.raise_for_status()

    # Read the CRM again to verify the update
    after = fetch_account(account_id)

    if str(after.get("parent_id") or "") != str(bellhaven_parent_id):
        raise UnsafeChange(
            "Write may have occurred, but verification failed"
        )

    return "Updated and verified in CRM"
