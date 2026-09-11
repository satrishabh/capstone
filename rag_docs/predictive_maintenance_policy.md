# Synthetic Predictive Maintenance Decision Policy

IMPORTANT: Synthetic policy for the capstone/demo only.

## Risk levels
- 0–30: LOW
- 31–60: MEDIUM
- 61–80: HIGH
- 81–100: CRITICAL

## Critical indicators
Any of the following can trigger critical review:
- Oil pressure < 1.5 bar and persistent
- Coolant temperature > 110°C and persistent
- Strong worsening trend across multiple trips
- Multiple correlated engine-health indicators abnormal

## Decision principle
The system must not claim certainty of component failure from telemetry alone.
It should state:
- observed evidence
- historical trend
- possible causes
- recommended verification
- ML failure probability
- confidence/limitations

## Human-in-the-loop
Critical cases require qualified human review before a major maintenance action is authorized.

## Rejection/re-analysis
If a technician rejects the recommendation or supplies new evidence, the workflow must re-run diagnosis using the new information and should explicitly explain what changed.
