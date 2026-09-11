import joblib
import pandas as pd

MODEL_PATH = "../models/failure_model.joblib"


FEATURES = [
    "engine_rpm",
    "coolant_temperature",
    "oil_pressure",
    "battery_voltage",
    "vibration",
    "vehicle_speed"
]


def load_model():

    bundle = joblib.load(
        MODEL_PATH
    )

    return bundle["model"]


def predict_failure_probability(
    telemetry: dict
) -> float:

    model = load_model()

    row = pd.DataFrame([{
        feature: telemetry.get(
            feature,
            0
        )
        for feature in FEATURES
    }])

    probability = model.predict_proba(
        row[FEATURES]
    )[0][1]

    return float(probability)