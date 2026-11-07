from pathlib import Path
root=Path(r"C:\Users\its_b\Downloads\ARE ERP SAFE TEST\Ali_Raza_Enterprises_ERP_SAFE_WORKING_COPY_CSS_FIXED_18-Oct-2026")
p=root/"app/configuration_master_service.py"
s=p.read_text(encoding="utf-8-sig")
s=s.replace('_ALLOWED_TYPES = {"BRAND", "UNIT", "SHADE", "VARIANT"}','_ALLOWED_TYPES = {"BRAND", "UNIT", "SHADE", "VARIANT", "YARN_COUNT", "FIBER_TYPE", "SHADE_CATEGORY"}')
s=s.replace('table = {"BRAND":"brands", "UNIT":"units", "SHADE":"shades", "VARIANT":"item_variants"}[kind]','table = {"BRAND":"brands", "UNIT":"units", "SHADE":"shades", "VARIANT":"item_variants", "YARN_COUNT":"yarn_counts", "FIBER_TYPE":"fiber_types", "SHADE_CATEGORY":"shade_categories"}[kind]')
needle='''                else:  # VARIANT: create only with a complete, validated item identity.'''
insert='''                elif kind == "YARN_COUNT":
                    if creating:
                        code = _text(payload.get("code"), "Yarn count code", 30).upper()
                        name = _text(payload.get("name"), "Yarn count name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.yarn_counts(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Yarn count name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.item_variants WHERE yarn_count_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Yarn count is referenced by item variants and cannot be deactivated.")
                        cur.execute("""UPDATE master.yarn_counts SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.yarn_counts"

                elif kind == "FIBER_TYPE":
                    if creating:
                        code = _text(payload.get("code"), "Fiber type code", 30).upper()
                        name = _text(payload.get("name"), "Fiber type name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.fiber_types(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Fiber type name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.item_variants WHERE fiber_type_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Fiber type is referenced by item variants and cannot be deactivated.")
                        cur.execute("""UPDATE master.fiber_types SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.fiber_types"

                elif kind == "SHADE_CATEGORY":
                    if creating:
                        code = _text(payload.get("code"), "Shade category code", 30).upper()
                        name = _text(payload.get("name"), "Shade category name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.shade_categories(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Shade category name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.shades WHERE shade_category_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Shade category is referenced by shades and cannot be deactivated.")
                        cur.execute("""UPDATE master.shade_categories SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.shade_categories"

                else:  # VARIANT: create only with a complete, validated item identity.'''
if needle not in s: raise SystemExit("service insertion anchor not found")
s=s.replace(needle,insert)
p.write_text(s,encoding="utf-8")
p=root/"app/db.py"
s=p.read_text(encoding="utf-8-sig")
s=s.replace('"items": [], "yarn_counts": [], "fiber_types": [], "shade_options": [],','"items": [], "yarn_counts": [], "fiber_types": [], "shade_categories": [], "shade_options": [],')
s=s.replace('cur.execute("SELECT id,code,name FROM master.yarn_counts WHERE is_active ORDER BY code")','cur.execute("SELECT id,code,name,description,is_active FROM master.yarn_counts ORDER BY code")')
s=s.replace('cur.execute("SELECT id,code,name FROM master.fiber_types WHERE is_active ORDER BY code")','cur.execute("SELECT id,code,name,description,is_active FROM master.fiber_types ORDER BY code")')
anchor='''                result["fiber_types"] = [dict(row) for row in cur.fetchall()]
                cur.execute("""SELECT s.id,s.brand_id,s.shade_code,s.shade_name'''
replace='''                result["fiber_types"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT id,code,name,description,is_active FROM master.shade_categories ORDER BY name")
                result["shade_categories"] = [dict(row) for row in cur.fetchall()]
                cur.execute("""SELECT s.id,s.brand_id,s.shade_code,s.shade_name'''
if anchor not in s: raise SystemExit("db insertion anchor not found")
s=s.replace(anchor,replace)
p.write_text(s,encoding="utf-8")
p=root/"app/templates/configuration.html"
s=p.read_text(encoding="utf-8-sig")
anchor='''{% endif %}


{% if can_edit_master_data %}
<section class="config-card master-editor"'''
insert='''{% endif %}

{% if can_edit_master_data and not master_data.error %}
<div class="config-grid">
  {% for key, title, kind in [
    ("yarn_counts", "Yarn Counts", "YARN_COUNT"),
    ("fiber_types", "Fiber Types", "FIBER_TYPE"),
    ("shade_categories", "Shade Categories", "SHADE_CATEGORY")
  ] %}
  <article class="config-card">
    <h2>{{ title }}</h2>
    <p>{{ master_data[key]|length }} records</p>
    <div style="overflow-x:auto"><table>
      <thead><tr><th>Code</th><th>Name</th><th>Active</th><th>Action</th></tr></thead>
      <tbody>
      {% for row in master_data[key] %}
        <tr><td>{{ row.code }}</td><td>{{ row.name }}</td><td>{{ row.is_active }}</td>
        <td><button type="button" class="master-edit-row" data-master-kind="{{ kind }}" data-master-id="{{ row.id }}">Edit</button></td></tr>
      {% else %}
        <tr><td colspan="4">No records found.</td></tr>
      {% endfor %}
      </tbody>
    </table></div>
  </article>
  {% endfor %}
</div>
{% endif %}

{% if can_edit_master_data %}
<section class="config-card master-editor"'''
if anchor not in s: raise SystemExit("template cards anchor not found")
s=s.replace(anchor,insert)
s=s.replace('''          <option value="SHADE">Shade</option><option value="VARIANT">Item Variant</option>''','''          <option value="SHADE">Shade</option><option value="VARIANT">Item Variant</option>
          <option value="YARN_COUNT">Yarn Count</option><option value="FIBER_TYPE">Fiber Type</option>
          <option value="SHADE_CATEGORY">Shade Category</option>''')
s=s.replace('''    VARIANT:{item_id:null,variant_code:'NEW-VARIANT-CODE',variant_name:'',default_unit_id:null,yarn_count_id:null,fiber_type_id:null,brand_id:null,shade_id:null,is_active:true}
  };''','''    VARIANT:{item_id:null,variant_code:'NEW-VARIANT-CODE',variant_name:'',default_unit_id:null,yarn_count_id:null,fiber_type_id:null,brand_id:null,shade_id:null,is_active:true},
    YARN_COUNT:{code:'NEW-YARN-COUNT',name:'New yarn count',description:'',is_active:true},
    FIBER_TYPE:{code:'NEW-FIBER-TYPE',name:'New fiber type',description:'',is_active:true},
    SHADE_CATEGORY:{code:'NEW-SHADE-CATEGORY',name:'New shade category',description:'',is_active:true}
  };''')
s=s.replace("const yarns=masterDataRecords.yarn_counts||[], fibers=masterDataRecords.fiber_types||[];","const yarns=active(masterDataRecords.yarn_counts||[]), fibers=active(masterDataRecords.fiber_types||[]);")
s=s.replace("""    } else if(kind==='VARIANT') {
      if(!editing) {""","""    } else if(kind==='YARN_COUNT' || kind==='FIBER_TYPE' || kind==='SHADE_CATEGORY') {
      html+=editing?text(kind==='YARN_COUNT'?'Yarn count name':kind==='FIBER_TYPE'?'Fiber type name':'Shade category name','name',100,true):text('Code','code',30,true)+text('Name','name',100,true);
      html+=text('Description','description',300)+yesno('Active','is_active');
    } else if(kind==='VARIANT') {
      if(!editing) {""")
s=s.replace("""    if(kind==='VARIANT') return masterId.value ? {variant_name:get('variant_name'),is_active:bool('is_active')} : {item_id:Number(get('item_id')),variant_code:get('variant_code'),variant_name:get('variant_name'),default_unit_id:Number(get('default_unit_id')),brand_id:get('brand_id')?Number(get('brand_id')):null,shade_id:get('shade_id')?Number(get('shade_id')):null,yarn_count_id:get('yarn_count_id')?Number(get('yarn_count_id')):null,fiber_type_id:get('fiber_type_id')?Number(get('fiber_type_id')):null,is_active:bool('is_active')};
    return {};""","""    if(kind==='VARIANT') return masterId.value ? {variant_name:get('variant_name'),is_active:bool('is_active')} : {item_id:Number(get('item_id')),variant_code:get('variant_code'),variant_name:get('variant_name'),default_unit_id:Number(get('default_unit_id')),brand_id:get('brand_id')?Number(get('brand_id')):null,shade_id:get('shade_id')?Number(get('shade_id')):null,yarn_count_id:get('yarn_count_id')?Number(get('yarn_count_id')):null,fiber_type_id:get('fiber_type_id')?Number(get('fiber_type_id')):null,is_active:bool('is_active')};
    if(['YARN_COUNT','FIBER_TYPE','SHADE_CATEGORY'].includes(kind)) return masterId.value ? {name:get('name'),description:get('description'),is_active:bool('is_active')} : {code:get('code'),name:get('name'),description:get('description'),is_active:bool('is_active')};
    return {};""")
s=s.replace("""    const rows = masterDataRecords[kind.toLowerCase() + 's'] || [];
    const row = rows.find(item => String(item.id) === String(id));""","""    const dataKey = ({BRAND:'brands',UNIT:'units',SHADE:'shades',VARIANT:'variants',YARN_COUNT:'yarn_counts',FIBER_TYPE:'fiber_types',SHADE_CATEGORY:'shade_categories'})[kind];
    const rows = masterDataRecords[dataKey] || [];
    const row = rows.find(item => String(item.id) === String(id));""")
s=s.replace("""    else if (kind === 'UNIT') payload = {name:row.name,is_active:row.is_active};
    else if (kind === 'SHADE') payload = {shade_name:row.shade_name,shade_category_id:row.shade_category_id,is_common:row.is_common,is_active:row.is_active};
    else payload = {variant_name:row.variant_name,is_active:row.is_active};""","""    else if (kind === 'UNIT') payload = {name:row.name,is_active:row.is_active};
    else if (kind === 'SHADE') payload = {shade_name:row.shade_name,shade_category_id:row.shade_category_id,is_common:row.is_common,is_active:row.is_active};
    else if (['YARN_COUNT','FIBER_TYPE','SHADE_CATEGORY'].includes(kind)) payload = {name:row.name,description:row.description,is_active:row.is_active};
    else payload = {variant_name:row.variant_name,is_active:row.is_active};""")
p.write_text(s,encoding="utf-8")