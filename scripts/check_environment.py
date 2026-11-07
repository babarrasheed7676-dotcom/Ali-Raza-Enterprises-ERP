"""Small local setup diagnostic; does not connect to or modify PostgreSQL."""
import sys

print("Python:", sys.version.split()[0])
if sys.version_info < (3, 11):
    print("ERROR: Python 3.11+ is recommended.")
    raise SystemExit(1)
try:
    import fastapi, psycopg, pydantic_settings, jinja2
except ImportError as exc:
    print("Missing package:", exc)
    print("Run: pip install -r requirements.txt")
    raise SystemExit(1)
print("Dependencies: OK")
print("This diagnostic did not connect to or modify the database.")