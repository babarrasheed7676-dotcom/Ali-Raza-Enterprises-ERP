from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "migrations"


class ProductionSourceLineTraceabilityMigrationTests(unittest.TestCase):
    def read_migration(self, name: str) -> str:
        path = MIGRATIONS / name
        self.assertTrue(path.is_file(), f"Missing migration: {path}")
        return path.read_text(encoding="utf-8").upper()

    def test_big_cone_material_references_exact_dyeing_output_line(self):
        sql = self.read_migration("20261107_021_production_source_line_traceability.sql")
        self.assertIn("SOURCE_DYEING_OUTPUT_LINE_ID BIGINT", sql)
        self.assertIn("REFERENCES PRODUCTION.DYEING_OUTPUT_LINES(ID)", sql)
        self.assertIn("GUARD_BIG_CONE_SOURCE_OUTPUT_LINE", sql)
        self.assertIn("SOURCE_DYEING_ORDER_ID", sql)

    def test_baby_cone_material_references_exact_big_cone_output_line(self):
        sql = self.read_migration("20261107_021_production_source_line_traceability.sql")
        self.assertIn("SOURCE_BIG_CONE_OUTPUT_LINE_ID BIGINT", sql)
        self.assertIn("REFERENCES PRODUCTION.BIG_CONE_OUTPUT_LINES(ID)", sql)
        self.assertIn("GUARD_BABY_CONE_SOURCE_OUTPUT_LINE", sql)
        self.assertIn("SOURCE_BIG_CONE_ORDER_ID", sql)

    def test_dyeing_output_type_uses_real_dyed_thread_value(self):
        sql = self.read_migration("20261107_022_big_cone_dyeing_output_type_correction.sql")
        self.assertIn("IS DISTINCT FROM 'DYED_THREAD'", sql)
        self.assertNotIn("IS DISTINCT FROM 'OUTPUT'", sql)

    def test_upstream_output_allocations_are_quantity_limited(self):
        sql = self.read_migration("20261107_023_production_source_quantity_allocation_guard.sql")
        self.assertIn("V_ALLOCATED_QUANTITY + NEW.QUANTITY_KG > V_SOURCE_QUANTITY", sql)
        self.assertIn("FOR UPDATE OF L", sql)
        self.assertIn("SUM(QUANTITY_KG)", sql)

    def test_consumed_output_and_post_draft_lines_are_protected(self):
        sql = self.read_migration("20261107_024_production_source_line_immutability.sql")
        self.assertIn("BEFORE UPDATE OR DELETE ON PRODUCTION.DYEING_OUTPUT_LINES", sql)
        self.assertIn("BEFORE UPDATE OR DELETE ON PRODUCTION.BIG_CONE_OUTPUT_LINES", sql)
        self.assertIn("BEFORE DELETE ON PRODUCTION.BIG_CONE_MATERIAL_LINES", sql)
        self.assertIn("BEFORE DELETE ON PRODUCTION.BABY_CONE_MATERIAL_LINES", sql)
        self.assertIn("UNIT_ID, QUANTITY_KG", sql)

    def test_cancelled_and_reversed_orders_release_allocations(self):
        sql = self.read_migration("20261107_025_release_cancelled_production_source_allocations.sql")
        self.assertEqual(sql.count("O.STATUS NOT IN ('CANCELLED', 'REVERSED')"), 2)

    def test_big_and_baby_outputs_link_to_exact_material_inputs(self):
        sql = self.read_migration("20261107_026_production_input_output_lineage.sql")
        self.assertEqual(sql.count("SOURCE_MATERIAL_LINE_ID BIGINT"), 2)
        self.assertIn("GUARD_BIG_CONE_OUTPUT_SOURCE_MATERIAL", sql)
        self.assertIn("GUARD_BABY_CONE_OUTPUT_SOURCE_MATERIAL", sql)
        self.assertIn("OUTPUT ALLOCATION EXCEEDS ITS SOURCE MATERIAL QUANTITY", sql)

    def test_production_chain_uses_one_raw_store_and_process_stages(self):
        sql = self.read_migration("20261107_027_single_godown_production_stage_guards.sql")
        self.assertEqual(sql.count("CODE='RAW_STORE'"), 2)
        self.assertIn("CODE='DYEING'", sql)
        self.assertIn("CODE='BIG_CONE'", sql)
        self.assertIn("NEW.PROCESS_STAGE_ID IS DISTINCT FROM V_DYEING_STAGE_ID", sql)
        self.assertIn("NEW.PROCESS_STAGE_ID IS DISTINCT FROM V_BIG_CONE_STAGE_ID", sql)

    def test_missing_raw_store_or_process_stage_fails_closed(self):
        sql = self.read_migration("20261107_028_fail_closed_production_source_masters.sql")
        self.assertEqual(sql.count("V_RAW_LOCATION_ID IS NULL"), 2)
        self.assertIn("V_DYEING_STAGE_ID IS NULL", sql)
        self.assertIn("V_BIG_CONE_STAGE_ID IS NULL", sql)

    def test_dyeing_yarn_input_and_output_are_linked_and_guarded(self):
        sql = self.read_migration("20261107_029_dyeing_yarn_input_output_traceability.sql")
        self.assertIn("SOURCE_MATERIAL_LINE_ID BIGINT NOT NULL", sql)
        self.assertIn("SOURCE_MATERIAL_QUANTITY_KG NUMERIC NOT NULL", sql)
        self.assertIn("REFERENCES PRODUCTION.DYEING_MATERIAL_LINES(ID)", sql)
        self.assertIn("GUARD_DYEING_MATERIAL_SOURCE_LINE", sql)
        self.assertIn("GUARD_DYEING_OUTPUT_SOURCE_MATERIAL", sql)
        self.assertIn("SOURCE ALLOCATION EXCEEDS ITS RAW-YARN INPUT QUANTITY", sql)
        self.assertIn("CODE='RAW_STORE'", sql)
        self.assertIn("CODE='PURCHASE'", sql)
        self.assertIn("CODE='DYEING'", sql)
        self.assertIn("OUTPUT_TYPE='DYED_THREAD'", sql)
        self.assertIn("REQUIRES AN EXACT ACTIVE SHADE SELECTION", sql)

    def test_dyeing_chemical_consumption_links_exact_yarn_input(self):
        sql = self.read_migration("20261107_031_dyeing_consumption_source_yarn_lineage.sql")
        self.assertIn("SOURCE_MATERIAL_LINE_ID BIGINT", sql)
        self.assertIn("REFERENCES PRODUCTION.DYEING_MATERIAL_LINES(ID)", sql)
        self.assertIn("GUARD_DYEING_CONSUMPTION_SOURCE_MATERIAL", sql)
        self.assertIn("GUARD_DYEING_CONSUMPTION_SOURCE_BEFORE_ADVANCE", sql)
        self.assertIn("NEW.SOURCE_MATERIAL_LINE_ID IS NULL", sql)
        self.assertIn("V_SOURCE_ORDER_ID IS DISTINCT FROM NEW.DYEING_ORDER_ID", sql)
        self.assertIn("V_SOURCE_ITEM_CODE IS DISTINCT FROM 'YARN'", sql)
        self.assertIn("V_SOURCE_CATEGORY_CODE IS DISTINCT FROM 'YARN'", sql)
        self.assertIn("RAW_STORE/PURCHASE IN KG", sql)

    def test_dyeing_shade_variant_and_output_batch_are_distinct_from_raw_source(self):
        sql = self.read_migration("20261107_030_dyeing_shade_and_output_batch_identity.sql")
        self.assertIn("DRAFT OUTPUT BATCH MUST REMAIN BLANK", sql)
        self.assertIn("SOURCE_BATCH_ID IS NOT DISTINCT FROM V_SOURCE_BATCH_ID", sql)
        self.assertIn("OUTPUT_V.BRAND_ID IS DISTINCT FROM SHADE.BRAND_ID", sql)
        self.assertIn("OUTPUT_V.SHADE_ID IS DISTINCT FROM SHADE.ID", sql)
        self.assertIn("YARN_COUNT_ID IS DISTINCT FROM SOURCE_V.YARN_COUNT_ID", sql)
        self.assertIn("FIBER_TYPE_ID IS DISTINCT FROM SOURCE_V.FIBER_TYPE_ID", sql)
        self.assertIn("DYEING-STAGE BATCH LINKED TO THE SOURCE BATCH", sql)
        self.assertIn("CREATED AT POSTING", sql)



if __name__ == "__main__":
    unittest.main()