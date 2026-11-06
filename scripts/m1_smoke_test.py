"""Week 1 DB bootstrap smoke test, no third-party Python dependencies."""
import os
import subprocess
import sys


def main():
    user = os.environ.get("POSTGRES_USER", "taxi_admin")
    db = os.environ.get("POSTGRES_DB", "nyc_taxi")
    query = "SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('staging','warehouse','marts','audit') ORDER BY schema_name;"
    cmd = ["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", db, "-Atc", query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        sys.stderr.write(result.stderr)
        return result.returncode
    got = set(result.stdout.splitlines())
    expected = {"staging", "warehouse", "marts", "audit"}
    print("[M1] schemas:", ", ".join(sorted(got)))
    if got != expected:
        print("[ERROR] Missing schemas:", sorted(expected - got), file=sys.stderr)
        print("[HINT] On a preexisting database, execute docker/postgres/init/01_schemas.sql manually.")
        return 1
    print("[OK] Week 1 PostgreSQL smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
