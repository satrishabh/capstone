from workflow import build_workflow
def main():
    app = build_workflow()
    initial_state = {
        "vehicle_id":"VH-1003",
        "user_request": "Generate predictive maintenance report",
        "telemetry": {
            "timestamp":"2026-09-09T10:00:00",
            "engine_rpm":2200,
            "coolant_temperature":88,
            "oil_pressure":2.4,
            "battery_voltage":13.8,
            "vibration":2.1,
            "vehicle_speed":70
        },
        "history": {
            "maintenance": [
                "2026-05-15: engine oil and filter service",
                "2026-06-20: routine vehicle inspection completed",
                "2026-08-20: oil pressure measured at 2.5 bar",
                "2026-08-20: vibration measured at 2.0 mm/s"
            ],
            "previous_faults": [
            ]
        },
        "audit_log": []
    }

    config = {
        "configurable": {
            "thread_id":
                "VH-1003-LOW-RISK-demo"
        }
    }

    result = app.invoke(initial_state,config=config)
    print("\n\n================================")
    print("FINAL REPORT")
    print("================================")
    print(result.get("final_report","No report generated"))

if __name__ == "__main__":
    main()