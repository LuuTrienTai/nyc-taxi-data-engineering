from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Contract B: Bronze Directories
BRONZE_TAXI_DIR = DATA_DIR / "bronze" / "taxi"
BRONZE_WEATHER_DIR = DATA_DIR / "bronze" / "weather"
BRONZE_ZONES_DIR = DATA_DIR / "bronze" / "zones"

# Contract B: Silver Directories
SILVER_TAXI_DIR = DATA_DIR / "silver" / "taxi"
SILVER_WEATHER_DIR = DATA_DIR / "silver" / "weather"
SILVER_ZONES_DIR = DATA_DIR / "silver" / "zones"

# Contract B: Quarantine Directories
QUARANTINE_DIR = DATA_DIR / "quarantine"
QUARANTINE_TAXI_DIR = QUARANTINE_DIR / "taxi"
QUARANTINE_WEATHER_DIR = QUARANTINE_DIR / "weather"
QUARANTINE_ZONES_DIR = QUARANTINE_DIR / "zones"

# Audit Log File
AUDIT_LOG_PATH = DATA_DIR / "bronze" / "ingestion_audit.jsonl"

# Upstream Endpoints
TLC_TRIP_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
TLC_ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# NYC Coordinates (Central Park / Midtown Manhattan reference hub) & Timezone Contract
NYC_LATITUDE = 40.7831
NYC_LONGITUDE = -73.9712
BUSINESS_TIMEZONE = "America/New_York"

def ensure_directories() -> None:
    """Create all required Contract B directories if they do not exist."""
    for folder in [
        BRONZE_TAXI_DIR, BRONZE_WEATHER_DIR, BRONZE_ZONES_DIR,
        SILVER_TAXI_DIR, SILVER_WEATHER_DIR, SILVER_ZONES_DIR,
        QUARANTINE_TAXI_DIR, QUARANTINE_WEATHER_DIR, QUARANTINE_ZONES_DIR,
    ]:
        folder.mkdir(parents=True, exist_ok=True)