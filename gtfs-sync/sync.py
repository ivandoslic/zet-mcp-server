import os
import time
import logging
import sqlite3
import zipfile
import io
import csv
import requests
from datetime import datetime, date
from google.transit import gtfs_realtime_pb2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

GTFS_STATIC_URL = os.getenv("GTFS_STATIC_URL", "https://www.zet.hr/gtfs-scheduled/latest")
GTFS_RT_URL     = os.getenv("GTFS_RT_URL", "https://www.zet.hr/gtfs-rt-protobuf")
RT_INTERVAL     = int(os.getenv("GTFS_RT_REFRESH_INTERVAL", "15"))
STATIC_INTERVAL = int(os.getenv("GTFS_STATIC_REFRESH_HOURS", "24")) * 3600
DB_PATH         = os.getenv("DB_PATH", "/data/zet.db")


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS routes (
            route_id    TEXT PRIMARY KEY,
            short_name  TEXT,
            long_name   TEXT,
            route_type  INTEGER
        );

        CREATE TABLE IF NOT EXISTS stops (
            stop_id         TEXT PRIMARY KEY,
            stop_code       TEXT,
            stop_name       TEXT,
            lat             REAL,
            lon             REAL,
            parent_station  TEXT
        );

        CREATE TABLE IF NOT EXISTS trips (
            trip_id      TEXT PRIMARY KEY,
            route_id     TEXT,
            service_id   TEXT,
            headsign     TEXT,
            direction_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS stop_times (
            trip_id        TEXT,
            stop_id        TEXT,
            arrival_time   TEXT,
            departure_time TEXT,
            stop_sequence  INTEGER,
            PRIMARY KEY (trip_id, stop_sequence)
        );

        CREATE TABLE IF NOT EXISTS calendar_dates (
            service_id     TEXT,
            date           TEXT,
            exception_type INTEGER,
            PRIMARY KEY (service_id, date)
        );

        CREATE TABLE IF NOT EXISTS rt_updates (
            trip_id        TEXT,
            route_id       TEXT,
            stop_id        TEXT,
            arrival_time   INTEGER,
            departure_time INTEGER,
            updated_at     INTEGER,
            PRIMARY KEY (trip_id, stop_id)
        );

        CREATE TABLE IF NOT EXISTS rt_vehicles (
            trip_id    TEXT PRIMARY KEY,
            route_id   TEXT,
            lat        REAL,
            lon        REAL,
            speed      REAL,
            bearing    REAL,
            updated_at INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_stop_times_stop    ON stop_times(stop_id);
        CREATE INDEX IF NOT EXISTS idx_stop_times_trip    ON stop_times(trip_id);
        CREATE INDEX IF NOT EXISTS idx_trips_route        ON trips(route_id);
        CREATE INDEX IF NOT EXISTS idx_trips_service      ON trips(service_id);
        CREATE INDEX IF NOT EXISTS idx_calendar_date      ON calendar_dates(date);
        CREATE INDEX IF NOT EXISTS idx_rt_updates_stop    ON rt_updates(stop_id);
        CREATE INDEX IF NOT EXISTS idx_rt_vehicles_route  ON rt_vehicles(route_id);
    """)
    con.commit()
    log.info("DB inicijalizirana")


# ---------------------------------------------------------------------------
# Static GTFS sync
# ---------------------------------------------------------------------------

def sync_static(con: sqlite3.Connection):
    log.info("Preuzimam statički GTFS...")
    r = requests.get(GTFS_STATIC_URL, timeout=60)
    r.raise_for_status()
    log.info(f"Preuzeto {len(r.content) / 1024 / 1024:.1f} MB")

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        _load_routes(con, z)
        _load_stops(con, z)
        _load_trips(con, z)
        _load_calendar_dates(con, z)
        _load_stop_times(con, z)

    log.info("Statički GTFS sync završen")


def _csv_rows(z: zipfile.ZipFile, filename: str):
    """Čita CSV iz ZIP-a, vraća redove kao dict."""
    with z.open(filename) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        yield from reader


def _load_routes(con: sqlite3.Connection, z: zipfile.ZipFile):
    rows = [
        (r["route_id"], r["route_short_name"], r["route_long_name"], r["route_type"])
        for r in _csv_rows(z, "routes.txt")
    ]
    con.execute("DELETE FROM routes")
    con.executemany("INSERT INTO routes VALUES (?,?,?,?)", rows)
    con.commit()
    log.info(f"  routes: {len(rows)} redaka")


def _load_stops(con: sqlite3.Connection, z: zipfile.ZipFile):
    rows = [
        (r["stop_id"], r.get("stop_code",""), r["stop_name"],
         float(r["stop_lat"]), float(r["stop_lon"]), r.get("parent_station",""))
        for r in _csv_rows(z, "stops.txt")
    ]
    con.execute("DELETE FROM stops")
    con.executemany("INSERT INTO stops VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    log.info(f"  stops: {len(rows)} redaka")


def _load_trips(con: sqlite3.Connection, z: zipfile.ZipFile):
    rows = [
        (r["trip_id"], r["route_id"], r["service_id"],
         r.get("trip_headsign",""), r.get("direction_id", 0))
        for r in _csv_rows(z, "trips.txt")
    ]
    con.execute("DELETE FROM trips")
    con.executemany("INSERT INTO trips VALUES (?,?,?,?,?)", rows)
    con.commit()
    log.info(f"  trips: {len(rows)} redaka")


def _load_calendar_dates(con: sqlite3.Connection, z: zipfile.ZipFile):
    rows = [
        (r["service_id"], r["date"], int(r["exception_type"]))
        for r in _csv_rows(z, "calendar_dates.txt")
    ]
    con.execute("DELETE FROM calendar_dates")
    con.executemany("INSERT INTO calendar_dates VALUES (?,?,?)", rows)
    con.commit()
    log.info(f"  calendar_dates: {len(rows)} redaka")


def _load_stop_times(con: sqlite3.Connection, z: zipfile.ZipFile):
    log.info("  Učitavam stop_times (može potrajati ~30-60s)...")
    BATCH = 50_000
    batch = []
    total = 0
    con.execute("DELETE FROM stop_times")
    for r in _csv_rows(z, "stop_times.txt"):
        batch.append((
            r["trip_id"], r["stop_id"],
            r["arrival_time"], r["departure_time"],
            int(r["stop_sequence"])
        ))
        if len(batch) >= BATCH:
            con.executemany("INSERT OR REPLACE INTO stop_times VALUES (?,?,?,?,?)", batch)
            con.commit()
            total += len(batch)
            batch = []
            log.info(f"    ...{total:,} redaka")
    if batch:
        con.executemany("INSERT OR REPLACE INTO stop_times VALUES (?,?,?,?,?)", batch)
        con.commit()
        total += len(batch)
    log.info(f"  stop_times: {total:,} redaka ukupno")


# ---------------------------------------------------------------------------
# GTFS-RT sync
# ---------------------------------------------------------------------------

def sync_realtime(con: sqlite3.Connection):
    try:
        r = requests.get(GTFS_RT_URL, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"RT fetch failed: {e}")
        return

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)
    now = int(time.time())

    tu_rows = []
    veh_rows = []

    for entity in feed.entity:
        if entity.HasField("trip_update"):
            tu = entity.trip_update
            for stu in tu.stop_time_update:
                tu_rows.append((
                    tu.trip.trip_id,
                    tu.trip.route_id,
                    stu.stop_id,
                    stu.arrival.time if stu.arrival.time else None,
                    stu.departure.time if stu.departure.time else None,
                    now
                ))

        if entity.HasField("vehicle"):
            v = entity.vehicle
            veh_rows.append((
                v.trip.trip_id,
                v.trip.route_id,
                v.position.latitude,
                v.position.longitude,
                v.position.speed,
                v.position.bearing,
                now
            ))

    con.execute("DELETE FROM rt_updates")
    con.executemany("INSERT OR REPLACE INTO rt_updates VALUES (?,?,?,?,?,?)", tu_rows)
    con.execute("DELETE FROM rt_vehicles")
    con.executemany("INSERT OR REPLACE INTO rt_vehicles VALUES (?,?,?,?,?,?,?)", veh_rows)
    con.commit()
    log.info(f"RT sync: {len(tu_rows)} stop_updates, {len(veh_rows)} vozila")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = get_db()
    init_db(con)

    sync_static(con)

    last_static = time.time()

    while True:
        sync_realtime(con)
        time.sleep(RT_INTERVAL)

        if time.time() - last_static > STATIC_INTERVAL:
            sync_static(con)
            last_static = time.time()