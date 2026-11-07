"""Read-only random packing source candidates with explicit process-stage evidence."""
from __future__ import annotations

from typing import Any

from .db import get_connection


def _query_candidates(conn: Any, company_id: int) -> list[dict[str, Any]]:
    query = """
        WITH source_lines AS (
            SELECT
                'FRESH_NALKI'::text AS source_type,
                'production.nalki_output_lines'::text AS source_table,
                ol.id AS source_line_id,
                o.id AS source_order_id,
                o.nalki_no AS source_order_no,
                o.nalki_date AS source_date,
                ol.item_variant_id, ol.batch_id, ol.location_id,
                ol.process_stage_id, ol.ownership_type_id, ol.owner_party_id,
                ol.quantity_pieces AS source_quantity,
                ol.unit_cost,
                ol.output_type, ol.quality_status,
                NULL::text AS return_status,
                NULL::bigint AS source_nalki_line_id
            FROM production.nalki_output_lines ol
            JOIN production.nalki_orders o ON o.id=ol.nalki_order_id
            WHERE o.company_id=%s AND o.status='POSTED'
              AND ol.output_type='GOOD' AND ol.quality_status='ACCEPTED'
              AND ol.process_stage_id IS NOT NULL
              AND ol.unit_cost IS NOT NULL

            UNION ALL

            SELECT
                'PARTY_REJECTED_USABLE'::text,
                'production.outside_labeling_return_lines'::text,
                rl.id,
                lo.id,
                lo.labeling_no,
                lo.labeling_date,
                rl.item_variant_id, rl.batch_id, rl.location_id,
                rl.process_stage_id,
                rl.ownership_type_id, rl.owner_party_id,
                rl.quantity_pieces,
                rl.unit_cost,
                'REJECTED_USABLE'::text,
                rl.quality_status,
                rl.return_status,
                rl.source_nalki_line_id
            FROM production.outside_labeling_return_lines rl
            JOIN production.outside_labeling_orders lo
              ON lo.id=rl.outside_labeling_order_id
            WHERE lo.company_id=%s AND lo.status IN ('PARTIAL_RETURN','RETURNED')
              AND rl.return_status='ACCEPTED' AND rl.quality_status='ACCEPTED'
              AND rl.source_nalki_line_id IS NOT NULL
              AND rl.process_stage_id IS NOT NULL
              AND rl.unit_cost IS NOT NULL
              AND rl.ownership_type_id=2 AND rl.owner_party_id IS NOT NULL
              AND rl.location_id IS NOT NULL
        ),
        enriched AS (
            SELECT s.*,
                   v.brand_id, v.shade_id, sh.shade_code, sh.shade_name,
                   b.name AS brand_name, i.item_code, i.item_name,
                   ps.code AS process_stage_code,
                   p.party_name AS owner_party_name,
                   COUNT(*) OVER (
                     PARTITION BY s.item_variant_id,
                       COALESCE(s.batch_id,0), COALESCE(s.location_id,0),
                       COALESCE(s.process_stage_id,0), s.ownership_type_id,
                       COALESCE(s.owner_party_id,0)
                   ) AS source_bucket_count
            FROM source_lines s
            JOIN master.item_variants v ON v.id=s.item_variant_id AND v.is_active=TRUE
            JOIN master.items i ON i.id=v.item_id AND i.company_id=%s
              AND i.item_code='NALKI' AND i.is_active=TRUE
            JOIN master.shades sh ON sh.id=v.shade_id AND sh.is_active=TRUE
            JOIN master.brands b ON b.id=v.brand_id AND b.is_active=TRUE
            JOIN master.process_stages ps
              ON ps.id=s.process_stage_id AND ps.company_id=%s AND ps.is_active=TRUE
            LEFT JOIN master.parties p ON p.id=s.owner_party_id
        ),
        balances AS (
            SELECT sb.company_id, sb.item_variant_id, sb.batch_id,
                   sb.location_id, sb.process_stage_id, sb.ownership_type_id,
                   sb.owner_party_id, SUM(sb.quantity) AS available_pieces
            FROM inventory.stock_balances sb
            WHERE sb.company_id=%s AND sb.quantity>0
            GROUP BY sb.company_id,sb.item_variant_id,sb.batch_id,sb.location_id,
                     sb.process_stage_id,sb.ownership_type_id,sb.owner_party_id
        )
        SELECT e.source_type,e.source_table,e.source_line_id,e.source_order_id,
               e.source_order_no,e.source_date,e.item_variant_id,e.brand_id,
               e.brand_name,e.shade_id,e.shade_code,e.shade_name,
               e.batch_id,e.location_id,e.process_stage_id,e.process_stage_code,
               e.ownership_type_id,e.owner_party_id,e.owner_party_name,
               e.source_quantity,
               LEAST(e.source_quantity,b.available_pieces) AS available_pieces,
               e.unit_cost,e.output_type,e.quality_status,e.return_status,
               e.source_nalki_line_id,TRUE AS stock_verified
        FROM enriched e
        JOIN balances b ON b.company_id=%s
          AND b.item_variant_id=e.item_variant_id
          AND b.batch_id IS NOT DISTINCT FROM e.batch_id
          AND b.location_id IS NOT DISTINCT FROM e.location_id
          AND b.process_stage_id IS NOT DISTINCT FROM e.process_stage_id
          AND b.ownership_type_id=e.ownership_type_id
          AND b.owner_party_id IS NOT DISTINCT FROM e.owner_party_id
        WHERE e.source_bucket_count=1
          AND b.available_pieces>0
          AND (
            (e.source_type='FRESH_NALKI'
             AND e.process_stage_code IN ('NALKI','LABELING'))
            OR
            (e.source_type='PARTY_REJECTED_USABLE'
             AND e.process_stage_code IN ('NALKI','LABELING')
             AND e.ownership_type_id=2 AND e.owner_party_id IS NOT NULL)
          )
        ORDER BY e.source_date,e.source_order_no,e.source_line_id
    """
    with conn.cursor() as cur:
        cur.execute(
            query,
            (company_id, company_id, company_id, company_id, company_id, company_id),
        )
        return [dict(row) for row in cur.fetchall()]


def get_random_packing_source_candidates(
    company_id: int, *, connection: Any | None = None
) -> list[dict[str, Any]]:
    """Return source-line candidates with unique, exact stock-bucket attribution.

    Pass an existing transaction connection to obtain candidates inside the
    caller's transaction; otherwise a short-lived read-only connection is used.
    """
    company_id = int(company_id)
    if company_id <= 0:
        raise ValueError("A valid company is required.")
    if connection is not None:
        return _query_candidates(connection, company_id)
    with get_connection() as conn:
        return _query_candidates(conn, company_id)