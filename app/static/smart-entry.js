/* Ali Raza Enterprises ERP — reusable Smart Entry Engine.
   UI assistance only: no posting, stock, pricing, tax-rate or accounting decisions. */
(() => {
  "use strict";
  const enhanceLargeSelect = select => {
    if (select.dataset.smartSearchReady || select.multiple || select.disabled) return;
    const options = [...select.options].filter(option => option.value);
    if (options.length < 25) return;

    select.dataset.smartSearchReady = "1";
    const label = (select.labels?.[0]?.textContent ||
      select.parentElement?.querySelector("label")?.textContent || "options").trim();
    const search = document.createElement("input");
    search.type = "search";
    search.className = "smart-select-search";
    search.autocomplete = "off";
    search.spellcheck = false;
    search.placeholder = "Search " + label + " (" + options.length + " options)…";
    search.setAttribute("aria-label", "Search " + label);
    if (select.id) search.setAttribute("aria-controls", select.id);
    const result = document.createElement("span");
    result.className = "smart-select-result";
    result.setAttribute("aria-live", "polite");
    select.parentNode.insertBefore(search, select);
    search.insertAdjacentElement("afterend", result);

    const resetOptions = () => {
      [...select.options].forEach(option => { option.hidden = false; });
      [...select.querySelectorAll("optgroup")].forEach(group => { group.hidden = false; });
      result.textContent = "";
    };
    const filterOptions = () => {
      const query = search.value.trim().toLocaleLowerCase();
      let matches = 0;
      [...select.options].forEach(option => {
        const group = option.parentElement?.tagName === "OPTGROUP"
          ? option.parentElement.label + " " : "";
        const matched = !option.value || !query ||
          (group + option.textContent).toLocaleLowerCase().includes(query);
        option.hidden = !matched;
        if (matched && option.value) matches += 1;
      });
      [...select.querySelectorAll("optgroup")].forEach(group => {
        group.hidden = ![...group.children].some(option => !option.hidden);
      });
      result.textContent = query
        ? (matches ? matches + " matching option(s). Choose below." : "No matching options.")
        : "";
    };
    search.addEventListener("input", filterOptions);
    search.addEventListener("keydown", event => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        select.focus();
      } else if (event.key === "Enter") {
        const query = search.value.trim().toLocaleLowerCase();
        if (!query) return;
        const matches = [...select.options].filter(option =>
          option.value && !option.hidden
        );
        if (matches.length === 1) {
          select.value = matches[0].value;
          select.dispatchEvent(new Event("change", {bubbles:true}));
          select.focus();
        } else if (matches.length > 1) {
          event.preventDefault();
          select.focus();
        }
      } else if (event.key === "Escape") {
        search.value = "";
        resetOptions();
      }
    });
    select.addEventListener("change", () => {
      if (search.value) {
        search.value = "";
        resetOptions();
      }
    });
  };

  let autofocusClaimed = false;
  document.querySelectorAll("form[data-smart-entry]").forEach(form => {
    const mode = form.dataset.smartEntry;
    const status = form.querySelector(".smart-entry-status");
    const announce = message => { if (status) status.textContent = message; };
    const addButton = form.dataset.smartAddLine
      ? form.querySelector(form.dataset.smartAddLine) : null;
    const lineContainer = form.dataset.smartLineContainer
      ? form.querySelector(form.dataset.smartLineContainer) : null;
    const repeat = form.querySelector("#repeatReceiptLine");
    const scanLargeSelects = (root, cloned = false) => {
      const selects = root.matches?.("select")
        ? [root] : [...(root.querySelectorAll?.("select") || [])];
      selects.forEach(select => {
        if (cloned && select.dataset.smartSearchReady) {
          delete select.dataset.smartSearchReady;
          select.parentNode.querySelectorAll(":scope > .smart-select-search,:scope > .smart-select-result")
            .forEach(node => node.remove());
        }
        enhanceLargeSelect(select);
      });
    };
    scanLargeSelects(form);
    const selectObserver = new MutationObserver(records => {
      records.forEach(record => {
        if (record.target.matches?.("select")) enhanceLargeSelect(record.target);
        record.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) scanLargeSelects(node, true);
        });
      });
    });
    selectObserver.observe(form, {childList:true,subtree:true});
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

    if (form.dataset.smartRecovery === "session") {
      const recoveryKey = "are-erp:smart-recovery:v1:" + location.pathname + ":" + mode;
      const recoveryTtl = 2 * 60 * 60 * 1000;
      const recoveryClearedAfterSave = form.dataset.smartRecoveryClear === "true";
      if (recoveryClearedAfterSave) {
        try { sessionStorage.removeItem(recoveryKey); } catch (_) {}
        announce("Previous local recovery copy cleared after successful DRAFT save.");
      }
      const toolbar = form.querySelector(".smart-entry-toolbar");
      const recoveryControls = document.createElement("div");
      recoveryControls.className = "smart-recovery-controls";
      const saveRecovery = document.createElement("button");
      saveRecovery.type = "button";
      saveRecovery.className = "smart-entry-action";
      saveRecovery.textContent = "Save recovery copy";
      const restoreRecovery = document.createElement("button");
      restoreRecovery.type = "button";
      restoreRecovery.className = "smart-entry-action";
      restoreRecovery.textContent = "Restore copy";
      restoreRecovery.hidden = true;
      const deleteRecovery = document.createElement("button");
      deleteRecovery.type = "button";
      deleteRecovery.className = "smart-entry-action";
      deleteRecovery.textContent = "Delete copy";
      deleteRecovery.hidden = true;
      const recoveryNote = document.createElement("span");
      recoveryNote.className = "smart-recovery-note";
      recoveryNote.textContent = "This tab only · expires in 2 hours · never uploaded";
      recoveryControls.append(saveRecovery, restoreRecovery, deleteRecovery, recoveryNote);
      toolbar?.appendChild(recoveryControls);

      const eligibleRecoveryField = el =>
        el.name && el.matches?.("input,select,textarea") &&
        !el.disabled && !el.readOnly &&
        !el.closest(".smart-entry-toolbar") &&
        !el.classList.contains("smart-select-search") &&
        !/^(hidden|password|file|submit|button|reset|image)$/i.test(el.type || "") &&
        !/(csrf|token|password|secret)/i.test(el.name) &&
        !el.multiple;

      const getRecoveryRows = () => lineContainer
        ? [...lineContainer.children].filter(row => row.matches(".receipt-line,.return-line"))
        : [];

      const collectRecoveryFields = () => {
        const fields = Object.create(null);
        [...form.elements].forEach(el => {
          if (!eligibleRecoveryField(el)) return;
          const value = (el.type === "checkbox" || el.type === "radio")
            ? {value:el.value,checked:el.checked}
            : {value:el.value};
          (fields[el.name] ||= []).push(value);
        });
        return fields;
      };

      const validSavedRecovery = () => {
        try {
          const raw = sessionStorage.getItem(recoveryKey);
          if (!raw) return null;
          const saved = JSON.parse(raw);
          if (saved.version !== 1 || saved.formKey !== mode ||
              saved.path !== location.pathname || !saved.fields ||
              !Number.isFinite(saved.savedAt) ||
              Date.now() - saved.savedAt > recoveryTtl) {
            sessionStorage.removeItem(recoveryKey);
            return null;
          }
          return saved;
        } catch (_) {
          try { sessionStorage.removeItem(recoveryKey); } catch (_) {}
          return null;
        }
      };

      const refreshRecoveryControls = () => {
        const saved = validSavedRecovery();
        restoreRecovery.hidden = !saved;
        deleteRecovery.hidden = !saved;
        if (saved) announce("Local recovery copy available · saved " +
          new Date(saved.savedAt).toLocaleTimeString() + " · this tab only.");
      };

      const restoreRecoveryFields = (saved, predicate = () => true, onlyNames = null) => {
        const indexes = Object.create(null);
        [...form.elements].forEach(el => {
          if (!eligibleRecoveryField(el) || !predicate(el) ||
              (onlyNames && !onlyNames.includes(el.name))) return;
          const index = indexes[el.name] || 0;
          indexes[el.name] = index + 1;
          const entry = saved.fields[el.name]?.[index];
          if (!entry) return;
          if (el.type === "checkbox" || el.type === "radio") {
            el.checked = Boolean(entry.checked);
          } else {
            const value = String(entry.value ?? "");
            if (el.tagName === "SELECT" &&
                ![...el.options].some(option => option.value === value)) return;
            el.value = value;
          }
        });
      };

      saveRecovery.addEventListener("click", () => {
        try {
          const saved = {
            version:1,
            formKey:mode,
            path:location.pathname,
            savedAt:Date.now(),
            rowCount:getRecoveryRows().length,
            fields:collectRecoveryFields()
          };
          const encoded = JSON.stringify(saved);
          if (encoded.length > 128000) {
            announce("Recovery copy is too large. Remove unnecessary notes and try again.");
            return;
          }
          sessionStorage.setItem(recoveryKey, encoded);
          refreshRecoveryControls();
          announce("Recovery copy saved in this browser tab for up to 2 hours. It was not uploaded.");
        } catch (_) {
          announce("Could not save a local recovery copy. Browser session storage may be unavailable.");
        }
      });

      restoreRecovery.addEventListener("click", () => {
        const saved = validSavedRecovery();
        if (!saved) {
          refreshRecoveryControls();
          announce("No valid local recovery copy is available.");
          return;
        }
        try {
          restoreRecoveryFields(saved, el => !lineContainer?.contains(el));
          [...form.elements].filter(el => eligibleRecoveryField(el) &&
            el.tagName === "SELECT" && !lineContainer?.contains(el))
            .forEach(el => el.dispatchEvent(new Event("change", {bubbles:true})));

          const targetRows = Number(saved.rowCount || 0);
          if (lineContainer && targetRows > 0) {
            if (targetRows > 10) throw new Error("Saved line count exceeds the form limit.");
            while (getRecoveryRows().length < targetRows) {
              const before = getRecoveryRows().length;
              if (!addButton) throw new Error("This form cannot recreate its saved lines.");
              addButton.click();
              if (getRecoveryRows().length === before) throw new Error("Could not recreate all saved lines.");
            }
            while (getRecoveryRows().length > targetRows) {
              const last = getRecoveryRows().at(-1);
              const remove = last?.querySelector(".remove-line,.remove-return-line");
              if (!remove) throw new Error("Could not align the saved line count.");
              remove.click();
            }
          }

          restoreRecoveryFields(saved);
          if (mode === "purchase-receipt") {
            form.querySelectorAll(".variant-select").forEach(el =>
              el.dispatchEvent(new Event("change", {bubbles:true})));
            restoreRecoveryFields(saved, () => true, ["unit_id"]);
          }
          form.dispatchEvent(new Event("input", {bubbles:true}));
          announce("Recovery copy restored. Review every field and server validation before saving.");
        } catch (error) {
          announce("Recovery restore stopped safely: " + error.message);
        }
      });

      deleteRecovery.addEventListener("click", () => {
        try {
          sessionStorage.removeItem(recoveryKey);
          refreshRecoveryControls();
          announce("Local recovery copy deleted from this tab.");
        } catch (_) {
          announce("Could not delete the local recovery copy.");
        }
      });
      refreshRecoveryControls();
    }

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
        if (!submitter) {
          announce("This form has no available save action.");
          return;
        }
        if (submitter.disabled) {
          announce("Save is disabled until this form's setup requirements are ready.");
          return;
        }
        form.requestSubmit(submitter);
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
    if (!autofocusClaimed && first) {
      first.focus({preventScroll:true});
      autofocusClaimed = true;
    }
  });
})();
