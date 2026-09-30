# Tools

Tool definitions and the shared `MAINTENANCE_TOOL_MAP` are in `src/tools.py`.
The adapters are synthetic placeholders. They do not connect to live fleet, OEM,
inventory, warranty, service scheduling, messaging, or work-order systems.

## Tool Use by Agent

| Agent | Tools | Current behavior |
| --- | --- | --- |
| Telemetry Agent | `analyze_telemetry` | Called directly by the workflow. Applies thresholds to oil pressure, coolant temperature, vibration, and battery voltage. |
| Diagnostic Agent | `get_additional_telemetry`, `lookup_dtc_code`, `get_similar_fleet_cases`, `check_recalls_and_tsbs` | Bound to the diagnostic LLM. Results are empty or synthetic placeholders where the real service is not connected. |
| Risk Agent | `send_approval_request` | Called directly for critical risk. Returns a simulated receipt. |
| Service Planning Agent | `check_parts_inventory`, `check_warranty_status`, `estimate_repair_cost`, `schedule_service_appointment`, `order_replacement_parts`, `create_work_order`, `notify_driver` | Bound to the planning LLM. The prompt restricts side effects to requests that explicitly ask for scheduling, ordering, work-order creation, or notification. |
| Report Agent | `send_report`, `upload_to_dashboard` | Bound to the report LLM and intended for explicit delivery requests. The workflow separately attempts S3 upload if configured. |

The history, RAG, ML, human approval, and re-analysis nodes do not use any of
these maintenance-system tools. RAG retrieval and the ML model are separate
functions, not entries in the LangChain tool map.

## Tool Reference

| Tool | Inputs | Output / behavior |
| --- | --- | --- |
| `analyze_telemetry` | Telemetry dictionary | Returns raw readings and threshold abnormalities. |
| `get_additional_telemetry` | Vehicle ID, parameter, time range | Returns an empty readings list and an unconfigured-source note. |
| `lookup_dtc_code` | Diagnostic trouble code | Normalizes the code and decodes a few synthetic known codes. |
| `get_similar_fleet_cases` | Symptom pattern | Returns no matches and a note that fleet history is not connected. |
| `check_recalls_and_tsbs` | Vehicle model and year | Returns empty recall and TSB lists. |
| `check_parts_inventory` | Part name and location | Returns not in stock, quantity zero, and a note that live inventory is unavailable. |
| `check_warranty_status` | Vehicle ID | Returns unknown coverage because no warranty service is connected. |
| `estimate_repair_cost` | Service plan | Returns USD with unset estimates. |
| `schedule_service_appointment` | Vehicle ID and date | Creates a simulated receipt only. |
| `order_replacement_parts` | Part list | Creates a simulated receipt only. |
| `send_approval_request` | Optional channel: email, Slack, or SMS | Returns a simulated receipt for supported channels. |
| `create_work_order` | Optional system: ServiceNow or Jira | Returns a simulated receipt for supported systems. |
| `notify_driver` | Vehicle ID and message | Creates a simulated receipt only. |
| `send_report` | Channel and recipient | Creates a simulated delivery receipt only. |
| `upload_to_dashboard` | Report text | Creates a simulated receipt containing a shortened report. |

LLM-invoked tool calls run through `invoke_with_tools` in `src/workflow.py`. It
allows up to four tool-loop iterations and stores results in the workflow state's
`tool_results` list. Tool exceptions are converted into error results. Direct
workflow calls such as telemetry analysis and approval notification do not use
that shared LLM dispatch loop.