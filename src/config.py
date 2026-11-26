import os
from contextlib import contextmanager
from fcntl import LOCK_EX, flock
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR / 'data')))
BRONZE_TAXI_DIR = DATA_DIR / 'bronze/taxi'
BRONZE_WEATHER_DIR = DATA_DIR / 'bronze/weather'
BRONZE_ZONES_DIR = DATA_DIR / 'bronze/zones'
AUDIT_LOG_PATH = DATA_DIR / 'bronze/ingestion_audit.jsonl'
TLC_TRIP_BASE_URL = 'https://d37ci6vzurychx.cloudfront.net/trip-data'
TLC_ZONE_LOOKUP_URL = 'https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv'
OPEN_METEO_ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
NYC_LATITUDE, NYC_LONGITUDE = 40.7831, -73.9712
BUSINESS_TIMEZONE = 'America/New_York'


def ensure_directories():
    # Runner and Airflow share group 0 on the Compose data volume.
    os.umask(0o002)
    for path in (BRONZE_TAXI_DIR, BRONZE_WEATHER_DIR, BRONZE_ZONES_DIR):
        path.mkdir(parents=True, exist_ok=True)


@contextmanager
def bronze_lock():
    """Serialize ingestion and reads of the Bronze snapshot on a shared volume."""
    ensure_directories()
    with (DATA_DIR / 'bronze' / '.lock').open('a') as lock:
        flock(lock, LOCK_EX)
        yield


def connection_kwargs():
    return dict(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.getenv('POSTGRES_PORT', '5433')),
        user=os.getenv('POSTGRES_USER', 'taxi_admin'),
        password=os.environ['POSTGRES_PASSWORD'],
        dbname=os.getenv('POSTGRES_DB', 'nyc_taxi'),
        connect_timeout=15,
    )
