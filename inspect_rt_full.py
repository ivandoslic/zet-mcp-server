# Dodaj na kraj decode_rt_protobuf.py ili napravi novu skriptu inspect_rt_full.py

from google.transit import gtfs_realtime_pb2
from datetime import datetime

with open(r"data/gtfs-rt-sample.bin", "rb") as f:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(f.read())

# Statistika
trip_updates = [e for e in feed.entity if e.HasField('trip_update')]
vehicles = [e for e in feed.entity if e.HasField('vehicle')]
alerts = [e for e in feed.entity if e.HasField('alert')]

print(f"trip_updates: {len(trip_updates)}")
print(f"vehicle positions: {len(vehicles)}")
print(f"alerts: {len(alerts)}")

# Prvih 5 trip_updates detaljno
print("\n--- Prvih 5 trip_updates ---")
for e in trip_updates[:5]:
    tu = e.trip_update
    print(f"\nroute_id={tu.trip.route_id} trip_id={tu.trip.trip_id}")
    for stu in tu.stop_time_update:
        dep = datetime.fromtimestamp(stu.departure.time) if stu.departure.time else "N/A"
        arr = datetime.fromtimestamp(stu.arrival.time) if stu.arrival.time else "N/A"
        print(f"  stop_id={stu.stop_id:12s} arr={arr}  dep={dep}")

# Dodaj u inspect_rt_full.py ili nova skripta
print("\n--- Prvih 3 vehicle positions ---")
for e in vehicles[:3]:
    v = e.vehicle
    print(f"route_id={v.trip.route_id} trip_id={v.trip.trip_id}")
    print(f"  lat={v.position.latitude:.6f} lon={v.position.longitude:.6f}")
    print(f"  speed={v.position.speed} bearing={v.position.bearing}")
    print(f"  timestamp={datetime.fromtimestamp(v.timestamp) if v.timestamp else 'N/A'}")

# Koje route_id-eve vidimo?
route_ids = sorted(set(e.trip_update.trip.route_id for e in trip_updates))
print(f"\nRoute IDs u RT feedu: {route_ids}")