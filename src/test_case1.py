from workflow import build_workflow
def main():
    app = build_workflow()
    initial_state = {
        "vehicle_id":"VH-1002",
        "user_request": "Generate predictive maintenance report",
        "telemetry": {
            "timestamp":"2026-09-09T09:00:00",
            "engine_rpm":2400,
            "coolant_temperature":108,
            "oil_pressure":1.3,
            "battery_voltage":13.3,
            "vibration":8.2,
            "vehicle_speed":70
        },
        "history": {
            "maintenance": [
                "2026-05-15: "
                "engine oil and filter service",
                "2026-06-20: "
                "vibration complaint inspected",
                "2026-08-20: "
                "oil pressure measured at 1.8 bar"
            ],
            "previous_faults": [
                "increasing vibration",
                "declining oil pressure"
            ]
        },
        "audit_log": []
    }

    config = {
        "configurable": {
            "thread_id":
                "VH-1002-demo"
        }
    }

    result = app.invoke(initial_state,config=config)
    print("\n\n================================")
    print("FINAL REPORT")
    print("================================")
    print(result.get("final_report","No report generated"))

if __name__ == "__main__":
    main()