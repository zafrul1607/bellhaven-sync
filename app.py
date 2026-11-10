
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DB_FILE = PROJECT_ROOT / "reviews.db"

st.set_page_config(
    page_title="Bellhaven CRM Review",
    page_icon="🏥",
    layout="wide"
)


# Load our existing datasets
def load_json(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def load_csv(filename):
    with open(
        DATA_DIR / filename,
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


# Create persistent review storage
def initialize_database():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                item_id TEXT PRIMARY KEY,
                review_status TEXT NOT NULL,
                selected_account_id TEXT,
                notes TEXT,
                updated_at TEXT NOT NULL
            )
        """)


def get_reviews():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute("""
            SELECT item_id, review_status,
                   selected_account_id, notes
            FROM reviews
        """).fetchall()

    return {
        row[0]: {
            "status": row[1],
            "account_id": row[2] or "",
            "notes": row[3] or ""
        }
        for row in rows
    }


def save_review(item_id, status, account_id, notes):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO reviews (
                item_id, review_status,
                selected_account_id, notes, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                review_status = excluded.review_status,
                selected_account_id = excluded.selected_account_id,
                notes = excluded.notes,
                updated_at = excluded.updated_at
        """, (
            item_id,
            status,
            account_id,
            notes,
            datetime.now(timezone.utc).isoformat()
        ))


initialize_database()

audit = load_csv("review_audit.csv")
stale = load_csv("stale_review.csv")
crm = load_json("crm_accounts.json")

crm_by_id = {
    str(account["account_id"]): account
    for account in crm
}


# Combine website findings and stale accounts
items = []

for row in audit:
    items.append({
        "id": "website:" + row["website_url"],
        "type": "website",
        "name": row["website_name"],
        "classification": row["classification"],
        "data": row
    })

for row in stale:
    items.append({
        "id": "stale:" + row["account_id"],
        "type": "stale",
        "name": row["name"],
        "classification": "possible_stale_review",
        "data": row
    })


st.title("🏥 Bellhaven CRM Review")
st.caption("Evidence review and discrepancy investigation")

st.warning(
    "CRM updates are enabled only for explicitly approved, "
    "verified non-CHOW parent corrections. "
    "Other changes remain in review mode."
)


# Dashboard summary
reviews = get_reviews()

reviewed_count = sum(
    item["id"] in reviews
    and reviews[item["id"]]["status"] != "Pending"
    for item in items
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Website facilities", len(audit))
col2.metric("Potential issues", sum(
    row["classification"] != "apparently_correct"
    for row in audit
))
col3.metric("Potentially stale", len(stale))
col4.metric("Reviewed", reviewed_count)


# Select a record to investigate
st.divider()

classification_options = sorted({
    item["classification"] for item in items
})

category = st.selectbox(
    "Filter by classification",
    ["All"] + classification_options
)

filtered = [
    item for item in items
    if category == "All"
    or item["classification"] == category
]

selected_id = st.selectbox(
    "Select a record to review",
    [item["id"] for item in filtered],
    format_func=lambda key: next(
        f"{item['name']} — {item['classification']}"
        for item in filtered if item["id"] == key
    )
)

item = next(
    item for item in filtered if item["id"] == selected_id
)

row = item["data"]

st.subheader(item["name"])
st.write("Classification:", item["classification"])


# Display website and CRM evidence
left, right = st.columns(2)

if item["type"] == "website":

    with left:
        st.markdown("### Website evidence")

        st.write("**Facility:**", row["website_name"])
        st.write("**Address:**", row["website_address"])
        st.write("**Care offerings:**", row["website_care"])

        st.link_button(
            "Open source website",
            row["website_url"]
        )

    with right:
        st.markdown("### Preliminary CRM match")

        st.write("**Account:**", row["crm_name"] or "Unresolved")
        st.write("**Account ID:**", row["crm_account_id"])
        st.write("**Address:**", row["crm_address"])
        st.write("**Current parent:**", row["crm_parent"])
        st.write("**Revenue:**", row["lifetime_revenue"])
        st.write("**Outstanding AR:**", row["outstanding_ar"])
        st.write("**Financial rule:**", row["financial_rule"])

    st.divider()

    st.write(
        "**Investigation recommendation:**",
        row["recommended_investigation"]
    )

    if row["review_warnings"]:
        st.warning(row["review_warnings"])

    # Show every candidate available in our review CSV
    candidate_ids = [
        value.strip()
        for value in row["candidate_account_ids"].split(";")
        if value.strip()
    ]

    candidate_records = [
        crm_by_id[account_id]
        for account_id in candidate_ids
        if account_id in crm_by_id
    ]

    with st.expander("View candidate CRM accounts"):
        st.dataframe(
            [
                {
                    "Account ID": acc.get("account_id"),
                    "Name": acc.get("name"),
                    "Street": acc.get("billing_street"),
                    "City": acc.get("billing_city"),
                    "Parent": acc.get("parent_name"),
                    "Status": acc.get("status")
                }
                for acc in candidate_records
            ],
            use_container_width=True
        )

else:
    st.markdown("### Potentially stale CRM account")
    st.write("**Account ID:**", row["account_id"])
    st.write("**Status:**", row["status"])
    st.write("**Reason:**", row["reason"])

    st.warning(
        "A missing website match is not sufficient "
        "evidence to deactivate an account."
    )


# Store human investigation decisions
st.divider()
st.subheader("Reviewer decision")

saved = reviews.get(selected_id, {})

options = [
    "Pending",
    "Needs investigation",
    "Verified for proposal",
    "Reject finding"
]

current_status = saved.get("status", "Pending")

with st.form("review_form"):

    decision = st.selectbox(
        "Investigation status",
        options,
        index=options.index(current_status)
        if current_status in options else 0
    )

    account_id = st.text_input(
        "Confirmed CRM account ID (optional)",
        value=saved.get("account_id", "")
    )

    notes = st.text_area(
        "Reviewer evidence and notes",
        value=saved.get("notes", ""),
        height=120,
        placeholder="Explain what you checked and concluded."
    )

    submitted = st.form_submit_button(
        "Save review decision",
        type="primary"
    )

if submitted:

    account_id = account_id.strip()

    if account_id and account_id not in crm_by_id:
        st.error("This CRM account ID was not found.")

    elif decision != "Pending" and not notes.strip():
        st.error("Please explain the decision in your notes.")

    else:
        save_review(
            selected_id,
            decision,
            account_id,
            notes.strip()
        )

        st.success("Review decision saved locally.")
        st.rerun()


st.divider()

st.caption(
    "Review decisions are persisted locally. "
    "Only explicitly approved, verified non-CHOW "
    "parent changes can be written to the CRM."
)


# Step 6.2B: Explicit CRM approval controls
from src.crm_writeback import (
    apply_reparent,
    read_action,
    record_action
)

st.divider()
st.subheader("Approve or reject proposed CRM change")

prior_action = read_action(selected_id)

if prior_action:
    st.info(
        f"Decision already recorded: {prior_action['status']}"
    )
    st.write(prior_action["detail"])

    if prior_action["status"] in ("applying", "uncertain"):
        st.error(
            "Inspect the live CRM before attempting another update."
        )

elif saved.get("status") == "Reject finding":
    st.info("This finding was previously rejected. No CRM change.")

else:
    reason = st.text_area(
        "Reason for this decision",
        value=saved.get("notes", ""),
        key=f"approval_reason_{selected_id}",
        placeholder="Explain the website and CRM evidence."
    )

    # REJECT: never modifies the CRM
    if st.button("Reject this proposed change"):
        if not reason.strip():
            st.error("Please provide a reason.")
        else:
            record_action(
                selected_id,
                "rejected",
                saved.get("account_id", ""),
                reason.strip()
            )

            save_review(
                selected_id,
                "Reject finding",
                saved.get("account_id", ""),
                reason.strip()
            )

            st.rerun()

    # APPROVE: direct parent correction only
    if (
        item["type"] == "website"
        and item["classification"] == "incorrect_parent_review"
    ):
        report = load_json("discrepancy_report.json")

        original_id = row["crm_account_id"]
        original = crm_by_id.get(original_id, {})
        target = report["bellhaven_parent_id"]

        st.write("**Account:**", row["crm_name"])
        st.write("**Account ID:**", original_id)
        st.write("**Current parent:**", row["crm_parent"])
        st.write(
            "**Proposed parent:**",
            "Bellhaven Senior Living (Parent Account)"
        )
        st.write("**Website evidence:**", row["website_url"])

        if row["financial_rule"] != "reparent_existing":
            st.warning(
                "CHOW or financial verification is required. "
                "Direct re-parenting is blocked."
            )

        elif (
            saved.get("status") != "Verified for proposal"
            or saved.get("account_id") != original_id
            or not saved.get("notes", "").strip()
        ):
            st.info(
                "First save Verified for proposal, "
                "the confirmed CRM account ID, "
                "and your evidence notes above."
            )

        else:
            confirmed = st.checkbox(
                "I verified this physical facility and authorize "
                "changing ONLY its parent_id."
            )

            if st.button(
                "Approve and update CRM",
                type="primary",
                disabled=(not confirmed or not reason.strip())
            ):
                # Persist an in-progress action before writing
                record_action(
                    selected_id,
                    "applying",
                    original_id,
                    reason.strip()
                )

                try:
                    facility = next(
                        f for f in load_json("website_facilities.json")
                        if f["source_url"] == row["website_url"]
                    )

                    result = apply_reparent(
                        original_id,
                        original.get("parent_id"),
                        target,
                        facility
                    )

                except Exception as exc:
                    # Never retry automatically after an uncertain write
                    record_action(
                        selected_id,
                        "uncertain",
                        original_id,
                        str(exc)
                    )

                    st.error(
                        f"Update not confirmed: {exc}. "
                        "Check the live CRM before retrying."
                    )

                else:
                    record_action(
                        selected_id,
                        "applied",
                        original_id,
                        result
                    )

                    st.success(result)

                st.rerun()

    else:
        st.info(
            "CRM write-back for this classification "
            "will be implemented separately."
        )
