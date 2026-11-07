/* Ali Raza Enterprises ERP — reusable Smart Entry Engine.
   UI assistance only: no posting, stock, pricing, tax-rate or accounting decisions. */
(() => {
  "use strict";
  document.querySelectorAll("form[data-smart-entry]").forEach(form => {
    const mode = form.dataset.smartEntry;
    const status = form.querySelector("#smartEntryStatus");
    const announce = message => { if (status) status.textContent = message; };
    const addButton = form.dataset.smartAddLine
      ? form.querySelector(form.dataset.smartAddLine) : null;
    const lineContainer = form.dataset.smartLineContainer
      ? form.querySelector(form.dataset.smartLineContainer) : null;
    const repeat = form.querySelector("#repeatReceiptLine");
    const rows = () => lineContainer ? [...lineContainer.querySelectorAll(".receipt-line")] : [];
    const setValue = (row, name, value) => {
      const el = row.querySelector('[name="' + name + '"]');
      if (el) el.value = value;
    };

    const repeatLast = () => {
      const sourceRows = rows();
      const source = sourceRows[sourceRows.length - 1];
      if (!source || sourceRows.length >= 10 || !addButton) {
        announce("Maximum 10 lines per receipt.");
        return;
      }
      addButton.click();
      const currentRows = rows();
      const row = currentRows[currentRows.length - 1];
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
    if (repeat) repeat.addEventListener("click", repeatLast);

    if (addButton) {
      addButton.addEventListener("click", () => {
        requestAnimationFrame(() => {
          const currentRows = rows();
          const row = mode === "purchase-receipt"
            ? currentRows[currentRows.length - 1]
            : lineContainer?.lastElementChild;
          const firstField = row?.querySelector(
            ".variant-select,input:not([type=hidden]):not([disabled]),select:not([disabled])"
          );
          firstField?.focus();
          announce("New entry line ready.");
        });
      });
    }

    // One keyboard contract for all opted-in entry forms.
    form.addEventListener("keydown", event => {
      if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        const submitter = form.querySelector('button[type="submit"],input[type="submit"]');
        if (submitter?.disabled) {
          announce("Save is disabled until this form's setup requirements are ready.");
          return;
        }
        if (submitter) form.requestSubmit(submitter);
        else form.requestSubmit();
        return;
      }
      if (event.altKey && event.key.toLowerCase() === "n" && addButton) {
        event.preventDefault();
        addButton.click();
        return;
      }
      if (event.key === "Enter" && !event.shiftKey && event.target.matches("select")) {
        const selectFields = [...form.elements].filter(el =>
          el.matches &&
          el.matches("input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled])") &&
          el.getClientRects().length && !el.readOnly
        );
        const selectIndex = selectFields.indexOf(event.target);
        if (selectIndex >= 0 && selectIndex < selectFields.length - 1) {
          requestAnimationFrame(() => selectFields[selectIndex + 1].focus());
        }
        return;
      }
      if (event.key !== "Enter" || event.shiftKey ||
          event.target.matches("textarea,select,button,[type=submit]")) return;
      const fields = [...form.elements].filter(el =>
        el.matches &&
        el.matches("input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled])") &&
        el.getClientRects().length && !el.readOnly
      );
      const index = fields.indexOf(event.target);
      if (index < 0 || index === fields.length - 1) return;
      event.preventDefault();
      fields[index + 1].focus();
      if (fields[index + 1].select && fields[index + 1].tagName === "INPUT") fields[index + 1].select();
    });

    if (mode === "purchase-receipt" && lineContainer) {
      const duplicateCheck = () => {
        const selected = rows().map(row => row.querySelector(".variant-select")?.value).filter(Boolean);
        const duplicate = selected.some((value, index) => selected.indexOf(value) !== index);
        announce(duplicate
          ? "Notice: same item appears on multiple lines. Check whether this is intentional."
          : "Smart Entry ready · Enter = next field · Alt+N = new line · Ctrl+Enter = save DRAFT");
      };
      lineContainer.addEventListener("change", event => {
        if (event.target.matches(".variant-select")) duplicateCheck();
      });
      duplicateCheck();
    } else {
      announce("Smart Entry ready · Enter = next field · Ctrl+Enter = save");
    }
    form.addEventListener("submit", () => announce("Submitting form for server validation…"));
    const first = form.querySelector("[data-smart-autofocus]") ||
      [...form.elements].find(el => el.matches &&
        el.matches("input:not([type=hidden]):not([disabled]),select:not([disabled])") &&
        el.getClientRects().length);
    first?.focus({preventScroll:true});
  });
})();
