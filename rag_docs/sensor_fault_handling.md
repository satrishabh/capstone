# Synthetic Sensor Fault Handling Guide

IMPORTANT: Synthetic educational content; not an OEM manual.

## Sensor-quality indicators
Potential sensor/data-quality issue when:
- A value is physically impossible
- A sensor is stuck at one value for an unusually long period
- The value changes abruptly without correlated vehicle behavior
- Independent sensors strongly disagree

## Rule
Do not interpret every abnormal sensor value as a mechanical failure.
Validate sensor quality when the evidence is internally inconsistent.

## Example
If oil pressure suddenly changes from 2.5 bar to 0.2 bar while engine vibration, temperature, RPM, and vehicle behavior remain stable, sensor/wiring verification should be considered before concluding catastrophic mechanical failure.
