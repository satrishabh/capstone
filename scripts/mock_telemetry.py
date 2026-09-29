"""Mock telemetry data generator — simulates a fleet of vehicles sending data to Snowflake."""
import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from snowflake_utils import get_connection

VEHICLES = [
    # (vehicle_id, profile) — profile controls how telemetry degrades
    ("VH-2001", "healthy"),
    ("VH-2002", "degrading_oil"),
    ("VH-2003", "overheating"),
    ("VH-2004", "low_battery"),
    ("VH-2005", "multi_failure"),
    ("VH-2006", "healthy"),
    ("VH-2007", "vibration_spike"),
    ("VH-2008", "healthy"),
    ("VH-2009", "sensor_glitch"),
    ("VH-2010", "degrading_oil"),
]

PROFILES = {
    "healthy": {
        "engine_rpm": (1700, 2200), "coolant_temperature": (88, 98),
        "oil_pressure": (2.4, 3.2), "battery_voltage": (13.4, 14.2),
        "vibration": (1.5, 3.5), "vehicle_speed": (40, 80),
    },
    "degrading_oil": {
        "engine_rpm": (2000, 2500), "coolant_temperature": (95, 105),
        "oil_pressure": (0.8, 1.8), "battery_voltage": (13.0, 13.8),
        "vibration": (4.0, 7.0), "vehicle_speed": (50, 75),
    },
    "overheating": {
        "engine_rpm": (1900, 2300), "coolant_temperature": (105, 120),
        "oil_pressure": (2.0, 2.8), "battery_voltage": (13.2, 13.9),
        "vibration": (3.0, 5.0), "vehicle_speed": (45, 70),
    },
    "low_battery": {
        "engine_rpm": (1800, 2100), "coolant_temperature": (90, 98),
        "oil_pressure": (2.5, 3.0), "battery_voltage": (10.5, 12.2),
        "vibration": (2.0, 3.5), "vehicle_speed": (50, 70),
    },
    "multi_failure": {
        "engine_rpm": (2300, 2800), "coolant_temperature": (108, 122),
        "oil_pressure": (0.5, 1.5), "battery_voltage": (11.5, 12.8),
        "vibration": (6.0, 10.0), "vehicle_speed": (60, 85),
    },
    "vibration_spike": {
        "engine_rpm": (2100, 2600), "coolant_temperature": (94, 102),
        "oil_pressure": (2.2, 2.8), "battery_voltage": (13.3, 13.9),
        "vibration": (5.5, 9.0), "vehicle_speed": (55, 80),
    },
    "sensor_glitch": {
        "engine_rpm": (1800, 2200), "coolant_temperature": (90, 96),
        "oil_pressure": (0.1, 3.0), "battery_voltage": (13.5, 14.0),
        "vibration": (2.0, 3.5), "vehicle_speed": (50, 70),
    },
}


def generate_reading(vehicle_id, profile_name):
    profile = PROFILES[profile_name]
    return {
        "vehicle_id": vehicle_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_rpm": round(random.uniform(*profile["engine_rpm"]), 1),
        "coolant_temperature": round(random.uniform(*profile["coolant_temperature"]), 1),
        "oil_pressure": round(random.uniform(*profile["oil_pressure"]), 2),
        "battery_voltage": round(random.uniform(*profile["battery_voltage"]), 2),
        "vibration": round(random.uniform(*profile["vibration"]), 2),
        "vehicle_speed": round(random.uniform(*profile["vehicle_speed"]), 1),
        "failure_label": 1 if profile_name in ("degrading_oil", "overheating", "multi_failure", "vibration_spike") else 0,
    }


def insert_readings(readings):
    conn = get_connection()
    try:
        cur = conn.cursor()
        for r in readings:
            cur.execute(
                "INSERT INTO VEHICLE_TELEMETRY "
                "(vehicle_id, timestamp, engine_rpm, coolant_temperature, oil_pressure, "
                "battery_voltage, vibration, vehicle_speed, failure_label) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (r["vehicle_id"], r["timestamp"], r["engine_rpm"],
                 r["coolant_temperature"], r["oil_pressure"], r["battery_voltage"],
                 r["vibration"], r["vehicle_speed"], r["failure_label"]),
            )
        conn.commit()
        return len(readings)
    finally:
        conn.close()


def run_generator(interval_seconds=10, max_batches=None):
    batch = 0
    print(f"Mock telemetry generator started — {len(VEHICLES)} vehicles, every {interval_seconds}s")
    print(f"Profiles: {', '.join(set(p for _, p in VEHICLES))}")
    print("-" * 60)
    try:
        while True:
            batch += 1
            readings = [generate_reading(vid, profile) for vid, profile in VEHICLES]
            count = insert_readings(readings)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] Batch {batch}: inserted {count} readings")
            for r in readings:
                status = "FAIL" if r["failure_label"] == 1 else "OK"
                print(f"  {r['vehicle_id']}: oil={r['oil_pressure']:.1f} coolant={r['coolant_temperature']:.0f} vib={r['vibration']:.1f} batt={r['battery_voltage']:.1f} [{status}]")
            if max_batches and batch >= max_batches:
                print(f"\nCompleted {max_batches} batches.")
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print(f"\nStopped after {batch} batches.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Mock telemetry generator")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between batches")
    parser.add_argument("--batches", type=int, default=None, help="Max batches (None=infinite)")
    args = parser.parse_args()
    run_generator(interval_seconds=args.interval, max_batches=args.batches)
