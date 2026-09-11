import joblib
import pandas as pd

bundle = joblib.load("../failure_model.joblib")
model = bundle["model"]
features = bundle["features"]

sample = pd.DataFrame([{
    "engine_rpm": 2400,
    "coolant_temperature": 108,
    "oil_pressure": 1.3,
    "battery_voltage": 13.3,
    "vibration": 8.2,
    "vehicle_speed": 70
}])

probability = float(model.predict_proba(sample[features])[0][1])
print(f"Failure probability: {probability:.3f}")
