"""Controlled creation of July-to-June fiscal years and monthly periods."""
from calendar import monthrange
from datetime import date

from ..db import get_connection
from ..audit_service import write_audit_log


def build_fiscal_year_definition(start_year):
    """Return a July 1–June 30 fiscal year and its twelve contiguous months."""
    try:
        year = int(start_year)
    except (TypeError, ValueError):
        raise ValueError("Fiscal year start year must be a valid four-digit year.")
    if year < 1900 or year > 9998:
        raise ValueError("Fiscal year start year must be between 1900 and 9998.")

    start = date(year, 7, 1)
    end = date(year + 1, 6, 30)
    name = f"FY {year}-{str(year + 1)[-2:]}"
    periods = []
    for offset in range(12):
        month_index = 7 + offset
        period_year = year + (month_index - 1) // 12
        period_month = (month_index - 1) % 12 + 1
        period_start = date(period_year, period_month, 1)
        period_end = date(
            period_year, period_month,
            monthrange(period_year, period_month)[1],
        )
        periods.append({
            "period_name": f"P{offset + 1:02d} - {period_start.strftime('%b %Y')}",
            "start_date": period_start,
            "end_date": period_end,
        })

    if periods[0]["start_date"] != start or periods[-1]["end_date"] != end:
        raise ValueError("Generated fiscal periods do not cover the fiscal year.")
    if any(
        periods[index]["end_date"].toordinal() + 1
        != periods[index + 1]["start_date"].toordinal()
        for index in range(11)
    ):
        raise ValueError("Generated fiscal periods are not contiguous.")

    return {"name": name, "start_date": start, "end_date": end, "periods": periods}


def create_fiscal_year(company_id, start_year, *, user, request):
    """Atomically create one company fiscal year, its twelve periods and audit row."""
    company_id = int(company_id)
    if int(user.get("company_id", -1)) != company_id:
        raise ValueError("User and fiscal year company do not match.")
    definition = build_fiscal_year_definition(start_year)

    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            # Serialize fiscal-year creation globally because fiscal_years.id
            # has no database sequence/default in the current schema.
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (7070700707,))
            cur.execute(
                """
                SELECT id, name, start_date, end_date, is_closed
                FROM core.fiscal_years
                WHERE company_id = %s
                  AND start_date <= %s
                  AND end_date >= %s
                ORDER BY start_date
                FOR UPDATE
                """,
                (company_id, definition["end_date"], definition["start_date"]),
            )
            conflicts = cur.fetchall()
            if conflicts:
                raise ValueError(
                    "This fiscal year overlaps an existing fiscal year. "
                    "Resolve the existing date range before creating it."
                )

            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM core.fiscal_years")
            fiscal_year_id = int(cur.fetchone()["next_id"])
            cur.execute(
                """
                INSERT INTO core.fiscal_years
                    (id, company_id, name, start_date, end_date, is_closed)
                VALUES (%s, %s, %s, %s, %s, FALSE)
                RETURNING id
                """,
                (
                    fiscal_year_id, company_id, definition["name"],
                    definition["start_date"], definition["end_date"],
                ),
            )
            fiscal_year_id = int(cur.fetchone()["id"])

            for period in definition["periods"]:
                cur.execute(
                    """
                    INSERT INTO core.accounting_periods
                        (fiscal_year_id, period_name, start_date, end_date, is_closed)
                    VALUES (%s, %s, %s, %s, FALSE)
                    """,
                    (
                        fiscal_year_id, period["period_name"],
                        period["start_date"], period["end_date"],
                    ),
                )

            write_audit_log(
                conn,
                user=user,
                request=request,
                action="CREATE",
                module="ACCOUNTING",
                table_name="core.fiscal_years",
                record_id=fiscal_year_id,
                document_no=definition["name"],
                new_values={
                    "company_id": company_id,
                    "name": definition["name"],
                    "start_date": definition["start_date"],
                    "end_date": definition["end_date"],
                    "period_count": len(definition["periods"]),
                    "periods": definition["periods"],
                    "is_closed": False,
                },
                reason="Create approved July-to-June fiscal year and twelve monthly periods.",
            )

    return {
        "id": fiscal_year_id,
        "name": definition["name"],
        "start_date": definition["start_date"],
        "end_date": definition["end_date"],
        "period_count": len(definition["periods"]),
    }