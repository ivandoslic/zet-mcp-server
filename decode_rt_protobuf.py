from google.transit import gtfs_realtime_pb2

with open(r"data/gtfs-rt-sample.bin", "rb") as f:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(f.read())

print(f"GTFS-RT timestamp: {feed.header.timestamp}")
print(f"GTFS-RT version: {feed.header.gtfs_realtime_version}")
print(f"Broj entiteta u feedu: {len(feed.entity)}")

if feed.entity:
    e = feed.entity[0]
    print(f"\nPrvi entitet:")
    print(f"  id: {e.id}")
    print(f"  has trip_update: {e.HasField('trip_update')}")
    print(f"  has vehicle: {e.HasField('vehicle')}")
    print(f"  has alert: {e.HasField('alert')}")
    if e.HasField('trip_update'):
        tu = e.trip_update
        print(f"  trip_id: {tu.trip.trip_id}")
        print(f"  route_id: {tu.trip.route_id}")
        print(f"  stop_time_updates: {len(tu.stop_time_update)}")
        if tu.stop_time_update:
            stu = tu.stop_time_update[0]
            print(f"  prvi stop_time_update: stop_id={stu.stop_id}, departure={stu.departure.time}")
    if e.HasField('vehicle'):
        v = e.vehicle
        print(f"  vehicle trip_id: {v.trip.trip_id}")
        print(f"  position: lat={v.position.latitude}, lon={v.position.longitude}")