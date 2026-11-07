from app.accounting.report_service import get_inventory_gl_mapping_readiness

data = get_inventory_gl_mapping_readiness(1)
print("purchase_journal_ready:", data.get("purchase_journal_ready"))
for blocker in data.get("purchase_blockers", []):
    if "separate register" in blocker or "free-text remarks marker" in blocker:
        print("VERIFIED BLOCKER:", blocker)
print("posted_grn_count:", data.get("posted_grn_count"))
print("posted_return_count:", data.get("posted_return_count"))