import sqlite3
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from fastmcp import FastMCP

DB_PATH = os.getenv("DB_PATH", "/data/zet.db")
TZ = ZoneInfo("Europe/Zagreb")

mcp = FastMCP("ZET Tramvaji 🚃")


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def get_active_service_ids(con: sqlite3.Connection) -> list[str]:
    """Vraća service_id-eve koji voze danas."""
    today = date.today().strftime("%Y%m%d")
    rows = con.execute(
        "SELECT service_id FROM calendar_dates WHERE date = ? AND exception_type = 1",
        (today,)
    ).fetchall()
    return [r["service_id"] for r in rows]


def normalize_time(t: str) -> str:
    """GTFS dozvoljava 25:10:00 za poslije ponoći — normaliziramo za usporedbu."""
    parts = t.split(":")
    h = int(parts[0])
    if h >= 24:
        parts[0] = str(h - 24).zfill(2)
    return ":".join(parts)


@mcp.tool()
def search_stops(name: str) -> list[dict]:
    """
    Pretraži stajališta ZET-a po imenu (djelomično podudaranje).
    Vraća listu stajališta s ID-em, imenom i koordinatama.
    """
    con = get_db()
    rows = con.execute(
        """
        SELECT
            COALESCE(NULLIF(parent_station, ''), stop_id) AS stop_id,
            stop_name,
            AVG(lat) AS lat,
            AVG(lon) AS lon
        FROM stops
        WHERE stop_name LIKE ?
        GROUP BY COALESCE(NULLIF(parent_station, ''), stop_id), stop_name
        ORDER BY stop_name
        LIMIT 20
        """,
        (f"%{name}%",)
    ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def routes_at_stop(stop_id: str) -> list[dict]:
    """
    Koje linije (rute) staju na određenom stajalištu danas.
    Vrati route_id, kratko ime linije, dugo ime i krajnje odredište (headsign).
    """
    con = get_db()
    service_ids = get_active_service_ids(con)
    if not service_ids:
        return []

    placeholders = ",".join("?" * len(service_ids))

    child_stops = con.execute(
        "SELECT stop_id FROM stops WHERE stop_id = ? OR parent_station = ?",
        (stop_id, stop_id)
    ).fetchall()
    child_ids = [r["stop_id"] for r in child_stops]
    stop_placeholders = ",".join("?" * len(child_ids))

    rows = con.execute(
        f"""
        SELECT DISTINCT
            r.route_id,
            r.short_name,
            r.long_name,
            t.headsign,
            t.direction_id
        FROM stop_times st
        JOIN trips t ON st.trip_id = t.trip_id
        JOIN routes r ON t.route_id = r.route_id
        WHERE st.stop_id IN ({stop_placeholders})
          AND t.service_id IN ({placeholders})
        ORDER BY CAST(r.short_name AS INTEGER), t.direction_id
        """,
        (*child_ids, *service_ids)
    ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def next_arrivals(stop_id: str, minutes: int = 30, headsign: str = "", route: str = "") -> list[dict]:
    """
    Iduća dolazišta na stajalištu u sljedećih N minuta.
    Uključuje RT korekciju ako je dostupna.
    Opcionalno filtrira po odredištu (headsign), npr. 'Borongaj' ili 'Prečko'.
    Opcionalno filtrira po liniji (route), npr. '5' ili '13'.
    Vraća: route short_name, headsign, scheduled_time, realtime_time, delay_seconds.
    """
    con = get_db()
    service_ids = get_active_service_ids(con)
    if not service_ids:
        return []

    now_naive = datetime.now(TZ).replace(tzinfo=None)
    window_end = now_naive + timedelta(minutes=minutes)
    now_str = now_naive.strftime("%H:%M:%S")
    end_str = window_end.strftime("%H:%M:%S")

    child_stops = con.execute(
        "SELECT stop_id FROM stops WHERE stop_id = ? OR parent_station = ?",
        (stop_id, stop_id)
    ).fetchall()
    child_ids = [r["stop_id"] for r in child_stops]
    stop_placeholders = ",".join("?" * len(child_ids))
    svc_placeholders = ",".join("?" * len(service_ids))

    headsign_clause = "AND LOWER(t.headsign) LIKE LOWER(?)" if headsign else ""
    route_clause = "AND r.short_name = ?" if route else ""

    params = [
        *child_ids,
        *service_ids,
        now_str,
        end_str,
        *([f"%{headsign}%"] if headsign else []),
        *([route] if route else []),
    ]

    rows = con.execute(
        f"""
        SELECT
            st.trip_id,
            st.stop_id,
            st.departure_time,
            r.short_name   AS route_name,
            t.headsign,
            t.direction_id
        FROM stop_times st
        JOIN trips t ON st.trip_id = t.trip_id
        JOIN routes r ON t.route_id = r.route_id
        WHERE st.stop_id IN ({stop_placeholders})
          AND t.service_id IN ({svc_placeholders})
          AND st.departure_time >= ?
          AND st.departure_time <= ?
          {headsign_clause}
          {route_clause}
        ORDER BY st.departure_time
        LIMIT 20
        """,
        params
    ).fetchall()

    trip_ids = [r["trip_id"] for r in rows]
    rt_map = {}
    if trip_ids:
        rt_placeholders = ",".join("?" * len(trip_ids))
        rt_rows = con.execute(
            f"""
            SELECT trip_id, stop_id, departure_time, arrival_time
            FROM rt_updates
            WHERE trip_id IN ({rt_placeholders})
            """,
            trip_ids
        ).fetchall()
        for rt in rt_rows:
            rt_map[(rt["trip_id"], rt["stop_id"])] = rt

    results = []
    for r in rows:
        scheduled = r["departure_time"]
        rt = rt_map.get((r["trip_id"], r["stop_id"]))

        realtime_time = None
        delay_seconds = None
        if rt and rt["departure_time"]:
            rt_dt = datetime.fromtimestamp(rt["departure_time"], TZ).replace(tzinfo=None)
            realtime_time = rt_dt.strftime("%H:%M:%S")
            sched_dt = datetime.strptime(
                f"{now_naive.date()} {normalize_time(scheduled)}", "%Y-%m-%d %H:%M:%S"
            )
            delay_seconds = int((rt_dt - sched_dt).total_seconds())

        results.append({
            "route":          r["route_name"],
            "headsign":       r["headsign"],
            "scheduled_time": scheduled,
            "realtime_time":  realtime_time,
            "delay_seconds":  delay_seconds,
        })

    return results

@mcp.tool()
def vehicle_positions(route: str) -> list[dict]:
    """
    Trenutne GPS pozicije svih vozila određene linije.
    Parametar route je kratki naziv linije, npr. '5' ili '13'.
    Vraća: route, trip_id, lat, lon, speed, bearing, updated_at.
    """
    con = get_db()
    rows = con.execute(
        """
        SELECT
            v.route_id,
            v.trip_id,
            v.lat,
            v.lon,
            v.speed,
            v.bearing,
            v.updated_at
        FROM rt_vehicles v
        JOIN routes r ON v.route_id = r.route_id
        WHERE r.short_name = ?
        ORDER BY v.updated_at DESC
        """,
        (route,)
    ).fetchall()

    return [
        {
            "route":      r["route_id"],
            "trip_id":    r["trip_id"],
            "lat":        r["lat"],
            "lon":        r["lon"],
            "speed":      r["speed"],
            "bearing":    r["bearing"],
            "updated_at": datetime.fromtimestamp(r["updated_at"], TZ).strftime("%H:%M:%S"),
        }
        for r in rows
    ]


if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "sse"
    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="stdio")