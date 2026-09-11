import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

df = pd.read_csv("../data/telemetry.csv")

features = [
    "engine_rpm", "coolant_temperature", "oil_pressure",
    "battery_voltage", "vibration", "vehicle_speed"
]
X = df[features]
y = df["failure_label"]

# Educational demo only. The dataset is tiny and synthetic.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.30, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=6,
    random_state=42,
    class_weight="balanced"
)
model.fit(X_train, y_train)

print(classification_report(y_test, model.predict(X_test), zero_division=0))
joblib.dump({"model": model, "features": features}, "../models/failure_model.joblib")
print("Saved ../failure_model.joblib")
