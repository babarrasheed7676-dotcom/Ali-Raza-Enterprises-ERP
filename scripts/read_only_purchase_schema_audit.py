from app.db import get_connection

with get_connection() as conn, conn.transaction():
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('purchasing', 'accounting', 'master')
              AND table_type = 'BASE TABLE'
              AND (table_name ILIKE '%invoice%'
                   OR table_name ILIKE '%tax%'
                   OR table_name ILIKE '%receipt%'
                   OR table_name ILIKE '%landed%')
            ORDER BY table_schema, table_name
        """)
        print("MATCHING TABLES:")
        for row in cur.fetchall():
            print(dict(row))
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'purchasing'
              AND table_name IN ('purchase_receipts', 'purchase_receipt_lines',
                                 'purchase_orders', 'purchase_returns')
            ORDER BY table_name, ordinal_position
        """)
        print("PURCHASING COLUMNS:")
        for row in cur.fetchall():
            print(dict(row))