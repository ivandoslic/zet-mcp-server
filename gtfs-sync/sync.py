import os
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

GTFS_STATIC_URL = os.getenv("GTFS_STATIC_URL", "")
GTFS_RT_TRIPS_URL = os.getenv("GTFS_RT_TRIPS_URL", "")
REFRESH_INTERVAL = int(os.getenv("GTFS_RT_REFRESH_INTERVAL", "30"))

def sync_static():
    log.info("TODO: download & parse static GTFS → SQLite")

def sync_realtime():
    log.info("TODO: fetch GTFS-RT and update SQLite")

if __name__ == "__main__":
    log.info("gtfs-sync starting...")
    sync_static()
    while True:
        sync_realtime()
        time.sleep(REFRESH_INTERVAL)