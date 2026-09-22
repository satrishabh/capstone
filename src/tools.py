from langchain_core.tools import tool

@tool
def analyze_telemetry(telemetry: dict) -> dict:
    """
    Analyze vehicle telemetry and identify abnormal parameters.
    """

    abnormalities = []
    # Oil pressure

    oil_pressure = telemetry.get("oil_pressure")

    if oil_pressure is not None:
        if oil_pressure < 1.5:
            abnormalities.append({
                "parameter": "oil_pressure",
                "value": oil_pressure,
                "severity": "CRITICAL",
                "reason": "Oil pressure below 1.5 bar"
            })
        elif oil_pressure < 2.0:
            abnormalities.append({
                "parameter": "oil_pressure",
                "value": oil_pressure,
                "severity": "WARNING",
                "reason": "Oil pressure below normal range"
            })

    # Coolant temperature
    coolant = telemetry.get("coolant_temperature")
    if coolant is not None:
        if coolant > 110:
            abnormalities.append({
                "parameter": "coolant_temperature",
                "value": coolant,
                "severity": "CRITICAL",
                "reason": "Engine overheating"
            })
        elif coolant > 105:
            abnormalities.append({
                "parameter": "coolant_temperature",
                "value": coolant,
                "severity": "WARNING",
                "reason": "Temperature above normal"
            })

    # Vibration
    vibration = telemetry.get("vibration")
    if vibration is not None:
        if vibration > 7:
            abnormalities.append({
                "parameter": "vibration",
                "value": vibration,
                "severity": "HIGH",
                "reason": "High engine vibration"
            })
        elif vibration > 5:
            abnormalities.append({
                "parameter": "vibration",
                "value": vibration,
                "severity": "WARNING",
                "reason": "Elevated vibration"
            })

    # Battery voltage
    battery = telemetry.get("battery_voltage")
    if battery is not None:
        if battery < 12.0:
            abnormalities.append({
                "parameter": "battery_voltage",
                "value": battery,
                "severity": "HIGH",
                "reason": "Low battery voltage"
            })
        elif battery < 12.4:
            abnormalities.append({
                "parameter": "battery_voltage",
                "value": battery,
                "severity": "WARNING",
                "reason": "Battery voltage is low"
            })
    return {
        "raw": telemetry,
        "abnormalities": abnormalities
    }