(() => {
  "use strict";
  const form = document.getElementById("dyeing-form");
  if (!form || form.dataset.smartEntry !== "dyeing" || form.dataset.smartRecovery !== "session") return;

  const status = form.querySelector(".smart-entry-status");
  const announce = message => { if (status) status.textContent = message; };
  const key = "are-erp:smart-recovery:v2:" + location.pathname + ":dyeing";
  const ttl = 2 * 60 * 60 * 1000;
  const limit = 100;
  const sections = [
    {id:"material-lines", add:"add-material", template:"material-template",
     fields:["material_item_variant_id","material_quantity_kg","material_batch_id","material_notes"]},
    {id:"output-lines", add:"add-output", template:"output-template",
     fields:["output_source_line_no","output_source_quantity_kg","output_quantity_kg","output_actual_shade_id","output_notes"]},
    {id:"chemical-lines", add:"add-chemical", template:"chemical-template",
     fields:["item_variant_id","batch_id","source_line_no","quantity","unit_id","ownership_type_id","owner_party_id","notes"]}
  ];
  const scalarNames = ["dyeing_date","remarks","labour_cost","machine_cost","electricity_cost","water_cost","boiler_fuel_cost","drying_cost"];
  const toolbar = form.querySelector(".smart-entry-toolbar");
  if (!toolbar) return;

  const controls = document.createElement("div");
  controls.className = "smart-recovery-controls";
  const makeButton = label => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "smart-entry-action";
    button.textContent = label;
    return button;
  };
  const save = makeButton("Save recovery copy");
  const restore = makeButton("Restore copy");
  const remove = makeButton("Delete copy");
  const note = document.createElement("span");
  note.className = "smart-recovery-note";
  note.textContent = "This tab only · expires in 2 hours · never uploaded";
  controls.append(save,restore,remove,note);
  toolbar.appendChild(controls);

  const rowsFor = section => [...document.getElementById(section.id).querySelectorAll(":scope > .dy-line")];
  const readField = (row,name) => {
    const field = row.querySelector('[name="' + name + '"]');
    return field ? field.value : "";
  };
  const writeField = (row,name,value) => {
    const field = row.querySelector('[name="' + name + '"]');
    if (!field) return false;
    const text = String(value ?? "");
    if (field.tagName === "SELECT" && ![...field.options].some(option => option.value === text)) return false;
    field.value = text;
    return true;
  };
  const readScalars = () => {
    const values = {};
    scalarNames.forEach(name => {
      const field = form.elements.namedItem(name);
      if (field) values[name] = field.value;
    });
    return values;
  };
  const readSection = section => rowsFor(section).map(row => {
    const values = {};
    section.fields.forEach(name => { values[name] = readField(row,name); });
    return values;
  });
  const getSaved = () => {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) return null;
      const saved = JSON.parse(raw);
      if (saved.version !== 2 || saved.path !== location.pathname ||
          !Number.isFinite(saved.savedAt) || Date.now()-saved.savedAt > ttl ||
          !saved.sections || !saved.scalars) {
        sessionStorage.removeItem(key);
        return null;
      }
      for (const section of sections) {
        const values = saved.sections[section.id];
        if (!Array.isArray(values) || values.length < 1 || values.length > limit ||
            values.some(row => !row || typeof row !== "object")) {
          sessionStorage.removeItem(key);
          return null;
        }
      }
      return saved;
    } catch (_) {
      try { sessionStorage.removeItem(key); } catch (_) {}
      return null;
    }
  };
  const refresh = () => {
    const available = Boolean(getSaved());
    restore.hidden = !available;
    remove.hidden = !available;
  };
  const setSectionCount = (section,target) => {
    const container = document.getElementById(section.id);
    const add = document.getElementById(section.add);
    if (!container || !add || target < 1 || target > limit) throw new Error("Invalid " + section.id + " row count.");
    while (rowsFor(section).length < target) {
      const before = rowsFor(section).length;
      add.click();
      if (rowsFor(section).length !== before + 1) throw new Error("Could not recreate all " + section.id + " rows.");
    }
    while (rowsFor(section).length > target) {
      const current = rowsFor(section);
      if (current.length <= 1) throw new Error("Cannot remove the required first row.");
      current[current.length-1].querySelector(".dy-remove")?.click();
      if (rowsFor(section).length !== current.length - 1) throw new Error("Could not align " + section.id + " rows.");
    }
  };
  const restorePlainRow = (row,section,values) => {
    section.fields.forEach(name => {
      if (name === "batch_id") return;
      if (!writeField(row,name,values[name])) warnings.push(name + " option unavailable");
    });
  };
  let warnings = [];

  if (form.dataset.smartRecoveryClear === "true") {
    try { sessionStorage.removeItem(key); } catch (_) {}
    announce("Previous local recovery copy cleared after successful DRAFT save.");
  }
  save.addEventListener("click", () => {
    try {
      const saved = {
        version:2,path:location.pathname,savedAt:Date.now(),
        scalars:readScalars(),
        sections:Object.fromEntries(sections.map(section => [section.id,readSection(section)]))
      };
      const encoded = JSON.stringify(saved);
      if (encoded.length > 128000) {
        announce("Recovery copy is too large. Shorten notes and try again.");
        return;
      }
      sessionStorage.setItem(key,encoded);
      refresh();
      announce("Dyeing recovery copy saved in this tab for 2 hours. It was not uploaded.");
    } catch (_) {
      announce("Could not save the local recovery copy. Browser session storage may be unavailable.");
    }
  });
  restore.addEventListener("click", () => {
    const saved = getSaved();
    if (!saved) { refresh(); announce("No valid local Dyeing recovery copy is available."); return; }
    try {
      warnings = [];
      // Recreate and restore source yarn inputs first; dependent source selectors are rebuilt afterwards.
      const material = sections[0];
      setSectionCount(material,saved.sections[material.id].length);
      rowsFor(material).forEach((row,index) => restorePlainRow(row,material,saved.sections[material.id][index]));
      rowsFor(material).forEach(row => row.querySelector('[name="material_item_variant_id"]')?.dispatchEvent(new Event("change",{bubbles:true})));
      if (typeof window.syncSourceLineChoices === "function") window.syncSourceLineChoices();

      const output = sections[1];
      setSectionCount(output,saved.sections[output.id].length);
      rowsFor(output).forEach((row,index) => restorePlainRow(row,output,saved.sections[output.id][index]));

      const chemical = sections[2];
      setSectionCount(chemical,saved.sections[chemical.id].length);
      rowsFor(chemical).forEach((row,index) => {
        const values = saved.sections[chemical.id][index];
        ["item_variant_id","ownership_type_id","owner_party_id"].forEach(name => {
          if (!writeField(row,name,values[name])) warnings.push(name + " option unavailable");
          row.querySelector('[name="' + name + '"]')?.dispatchEvent(new Event("change",{bubbles:true}));
        });
        ["source_line_no","quantity","unit_id","notes"].forEach(name => {
          if (!writeField(row,name,values[name])) warnings.push(name + " option unavailable");
        });
        const batch = row.querySelector('[name="batch_id"]');
        const wanted = String(values.batch_id ?? "");
        if (batch && wanted) {
          const option = [...batch.options].find(item => item.value === wanted);
          if (option && !option.disabled && !option.hidden) batch.value = wanted;
          else { batch.value = ""; warnings.push("A saved chemical batch is no longer eligible; left blank"); }
        } else if (batch) batch.value = "";
      });

      Object.entries(saved.scalars).forEach(([name,value]) => {
        const field = form.elements.namedItem(name);
        if (field) field.value = String(value ?? "");
      });
      form.dispatchEvent(new Event("input",{bubbles:true}));
      announce("Dyeing recovery restored. Review all 3 sections and any warnings before saving." +
        (warnings.length ? " " + warnings.slice(0,5).join("; ") + (warnings.length>5 ? "…" : "") : ""));
    } catch (error) {
      announce("Recovery stopped safely: " + error.message + " The saved copy remains available.");
    }
  });
  remove.addEventListener("click", () => {
    try { sessionStorage.removeItem(key); refresh(); announce("Local Dyeing recovery copy deleted from this tab."); }
    catch (_) { announce("Could not delete the local recovery copy."); }
  });
  refresh();
})();
