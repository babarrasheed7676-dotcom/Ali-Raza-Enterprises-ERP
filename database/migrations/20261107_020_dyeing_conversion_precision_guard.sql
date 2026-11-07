-- Ali Raza Enterprises ERP
-- 20261107_020_dyeing_conversion_precision_guard
-- Explicitly reject NULL rounding precision in approved conversion snapshots.
BEGIN;
ALTER TABLE production.dyeing_unit_conversion_snapshots DROP CONSTRAINT ck_dyeing_unit_conversion_status;
ALTER TABLE production.dyeing_unit_conversion_snapshots ADD CONSTRAINT ck_dyeing_unit_conversion_status CHECK (
 (status='NOT_REQUIRED' AND source_unit_code=target_unit_code AND source_unit_id=target_unit_id AND converted_quantity IS NOT NULL AND converted_quantity=source_quantity AND conversion_factor IS NOT NULL AND conversion_factor=1 AND configuration_version_id IS NULL AND rounding_places IS NULL AND rounding_mode='ROUND_HALF_UP')
 OR (status='APPROVED' AND source_unit_code<>target_unit_code AND source_unit_id<>target_unit_id AND converted_quantity IS NOT NULL AND converted_quantity>0 AND conversion_factor IS NOT NULL AND conversion_factor>0 AND configuration_version_id IS NOT NULL AND rounding_places IS NOT NULL AND rounding_places BETWEEN 0 AND 6 AND rounding_mode='ROUND_HALF_UP')
 OR (status='PENDING_CONFIGURATION' AND source_unit_code<>target_unit_code AND source_unit_id<>target_unit_id AND converted_quantity IS NULL AND configuration_version_id IS NULL AND conversion_factor IS NULL AND rounding_places IS NULL AND rounding_mode='ROUND_HALF_UP')
 OR (status='BLOCKED_PRECISION' AND source_unit_code<>target_unit_code AND source_unit_id<>target_unit_id AND converted_quantity IS NULL AND conversion_factor IS NOT NULL AND conversion_factor>0 AND configuration_version_id IS NOT NULL AND rounding_places IS NOT NULL AND rounding_places BETWEEN 0 AND 6 AND rounding_mode='ROUND_HALF_UP')
);
COMMIT;
