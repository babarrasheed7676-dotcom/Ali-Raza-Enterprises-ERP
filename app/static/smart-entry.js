/* Ali Raza Enterprises ERP — reusable Smart Entry Engine.
   UI assistance only: no posting, stock, pricing, tax-rate or accounting decisions. */
(() => {
  "use strict";
  const form = document.querySelector('[data-smart-entry="purchase-receipt"]');
  if (!form) return;
  const lines = form.querySelector("#receiptLines");
  const add = form.querySelector("#addReceiptLine");
  const repeat = form.querySelector("#repeatReceiptLine");
  const status = form.querySelector("#smartEntryStatus");
  if (!lines || !add) return;
  const rows = () => [...lines.querySelectorAll(".receipt-line")];
  const announce = message => { if (status) status.textContent = message; };
  const setValue = (row, name, value) => {
    const el = row.querySelector('[name="' + name + '"]');
    if (el) el.value = value;
  };
  const addBlank = () => {
    if (rows().length >= 10) { announce("Maximum 10 lines per receipt."); return null; }
    add.click();
    return rows().at(-1);
  };
  const repeatLast = () => {
    const source = rows().at(-1);
    if (!source || rows().length >= 10) { announce("Maximum 10 lines per receipt."); return; }
    const row = addBlank();
    if (!row) return;
    ["item_variant_id","unit_id","purchase_order_line_id","unit_price"].forEach(name => {
      const from = source.querySelector('[name="' + name + '"]');
      if (from) setValue(row, name, from.value);
    });
    setValue(row, "received_quantity", "");
    setValue(row, "discount_amount_line", "0");
    setValue(row, "tax_amount", "0");
    setValue(row, "line_remarks", "");
    row.querySelector(".variant-select")?.dispatchEvent(new Event("change", {bubbles:true}));
    requestAnimationFrame(() => row.querySelector('[name="received_quantity"]')?.focus());
    announce("Last item's variant, unit and rate copied. Enter the new quantity.");
  };
  repeat?.addEventListener("click", repeatLast);
  add.addEventListener("click", () => {
    requestAnimationFrame(() => {
      const row = rows().at(-1);
      row?.querySelector(".variant-select")?.focus();
      announce("New item line ready.");
    });
  });
  // Enter advances through data fields; Ctrl+Enter submits the DRAFT form.
  form.addEventListener("keydown", event => {
    if (event.ctrlKey && event.key === "Enter") {
      event.preventDefault();
      form.requestSubmit();
      return;
    }
    if (event.altKey && event.key.toLowerCase() === "n") {
      event.preventDefault();
      add.click();
      return;
    }
    if (event.key !== "Enter" || event.shiftKey || event.target.matches("textarea,select,button,[type=submit]")) return;
    const fields = [...form.querySelectorAll("input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled])")]
      .filter(el => el.getClientRects().length && !el.readOnly);
    const index = fields.indexOf(event.target);
    if (index < 0 || index === fields.length - 1) return;
    event.preventDefault();
    fields[index + 1].focus();
    if (fields[index + 1].select && fields[index + 1].tagName === "INPUT") fields[index + 1].select();
  });
  // Warn, never block, when the same variant appears on multiple lines.
  const duplicateCheck = () => {
    const selected = rows().map(row => row.querySelector(".variant-select")?.value).filter(Boolean);
    const duplicate = selected.some((value, index) => selected.indexOf(value) !== index);
    announce(duplicate ? "Notice: same item appears on multiple lines. Check whether this is intentional." : "Smart Entry ready · Enter = next field · Alt+N = new line · Ctrl+Enter = save DRAFT");
  };
  lines.addEventListener("change", event => {
    if (event.target.matches(".variant-select")) duplicateCheck();
  });
  form.addEventListener("submit", () => announce("Saving as DRAFT only…"));
  // Searchable native selects support type-to-select without a third-party library.
  form.querySelector("#supplierSelect")?.focus({preventScroll:true});
  duplicateCheck();
})();
