# OpenTune v0.1.0 — Build Summary

**Built:** 2026-03-28
**Status:** Complete, import-verified, simulation-ready

---

## What Was Built

OpenTune is an open-source terminal diagnostic tool for mechanics — the generative, self-learning cousin of OBDAgent. Same Rich terminal interface, but instead of a fixed procedure registry, it engineers solutions on the fly using Claude.

---

## File Map

| File | Purpose |
|------|---------|
| `main.py` | Entry point — launch screen, connection flow, scan display, chat loop, procedure execution, outcome capture |
| `config.py` | API keys, model config, anomaly thresholds, version |
| `core/connection.py` | OBD2 connection layer — ELM327 real + simulation mode, VehicleInfo, LiveData, DTC, UDS primitives |
| `core/scanner.py` | ECUScanner (full scan on connect), LiveMonitor (background thread), AnomalyAlert detection |
| `core/session_logger.py` | JSONL session logging — every outcome logged to `sessions/YYYYMMDD.jsonl` |
| `ai/engineer.py` | ProcedureEngineer — generative core, assembles vehicle context, calls Claude, returns EngineeredProcedure |
| `ai/monitor.py` | AIMonitor — enriches raw anomaly alerts with Claude interpretation, urgency, causes |
| `requirements.txt` | `anthropic`, `rich`, `pyserial`, `python-dotenv` |
| `.env.example` | Template for API key configuration |
| `README.md` | Full project documentation |

---

## Key Design Decisions

### Generative Core (`ai/engineer.py`)
- `ProcedureEngineer.engineer_solution()` assembles full context: VIN, make/model/year, all active DTCs with severity, full live data snapshot, ECU communication map
- Claude returns structured JSON with title, steps, confidence, reasoning, safety notes, estimated time
- Steps typed as: `read_pid`, `send_uds`, `instruct_mechanic`, `verify`, `wait`
- Streaming variant available via `engineer_solution_streaming()` for real-time terminal feedback
- Graceful fallback when API unavailable: basic 3-step investigation procedure

### Live Monitor (`core/scanner.py`)
- Background daemon thread polling at 0.5s interval
- 13 PID thresholds configured with min/max/warn levels
- 60-second alert suppression per PID to prevent spam
- Feeds `AnomalyAlert` objects to queue consumed by main chat loop

### AI Monitor (`ai/monitor.py`)
- Second background thread consuming raw anomaly alerts
- Calls Claude to interpret each anomaly: mechanical meaning, likely causes, urgency level
- Urgency: `immediate` | `soon` | `monitor`
- Graceful degradation to basic alert if API unavailable

### Simulation Mode
- 5 realistic vehicle profiles (Honda, BMW, Chevrolet, Nissan, Ford)
- Live data that drifts realistically using random walk
- 1-3 random DTCs from an 8-code pool
- ECU probing returns randomized OK/NO RESPONSE
- No hardware required

### Session Logger
- JSONL format: one JSON object per line
- Captures: timestamp, session_id, VIN, vehicle, user input, procedure engineered flag, title, all steps with status, outcome, notes, full live data snapshot, all DTCs, AI reasoning, confidence score
- This IS the dataset that feeds OBDAgent's procedure registry

### Terminal UI
- Full Rich styling throughout — cyan/blue gradient ASCII art on launch
- Mode badge (SIM/REAL), API engine status, vehicle info on launch screen
- DTC table with severity color coding
- Live data panel with all key PIDs
- ECU map probe results
- Procedure display: confidence bar, reasoning panel, safety notes, numbered steps
- Step-by-step execution with inline results and mechanic prompts

---

## How to Run

```bash
cd /Users/newowner/Desktop/OpenTune
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
python3 main.py --sim
```

---

## Differences from OBDAgent

| OBDAgent | OpenTune |
|----------|---------|
| Fixed procedure registry | Generates procedures on the fly |
| Intent matching via keyword patterns | Natural language → Claude engineers solution |
| Known vehicles/ECUs (Toyota/Lexus) | Any make, model, year |
| Procedures are pre-written Python classes | Procedures are JSON from Claude, executed by runtime |
| Copilot = fallback tool | Claude = primary engine |
| No session-level outcome logging | Every session logged to JSONL dataset |

---

## Import Verification

```
python3 -c "import main" 2>&1 | head -5
# (no output — clean import)
```
