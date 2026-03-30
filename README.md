# OpenTune

Open-source vehicle diagnostics with generative AI. When the procedure doesn't exist — it engineers one.

```
 ██████╗ ██████╗ ███████╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝
                  Open Diagnostics. Infinite Solutions.
```

## What it does

- Scans all ECUs on connect — reads every DTC with plain English descriptions
- Monitors live vehicle data in the background — flags anomalies in real time
- Chat with it in plain English about any vehicle problem
- If a solution exists: runs it. If not: builds one from first principles using Claude
- Logs every session outcome to JSONL — feeding the collective diagnostic dataset

## Conversation flow

OpenTune never opens with a blunt Y/N prompt. It reads the vehicle first, then asks:

```
mechanic: I need my GX suspension calibrated

OpenTune: Before I run anything — let me check what the system sees.
          → C1840 active — KDSS hydraulic fault, rear pressure below spec
          → Rear ride height -3.2cm below spec
          Is this after recent suspension work, or did the warning come on by itself?

mechanic: after replacing rear shocks

OpenTune: Got it. Engineering solution...

          Plan:  (KDSS Fault Clear + Rear Height Calibration)
          1. Clear KDSS fault (C1840)
          2. Run rear air suspension height calibration
          3. Verify sensor baseline
          Estimated time: 8 min

          Ready to start?
```

The AI always: reads data first → asks one clarifying question if ambiguous → summarizes findings + plan → waits for "ready". Never just "Run it? Y/N".

## How it differs from OBDAgent

**OBDAgent** runs known procedures from a fixed registry.

**OpenTune** engineers unknown ones. When you describe a problem no template covers, OpenTune assembles full vehicle context — live data, DTCs, ECU map — and asks Claude to reason through the fault and build a step-by-step procedure on the spot.

Every outcome that gets logged teaches the system what works and what doesn't.

## Run it

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run in simulation mode (no hardware needed)
python main.py --sim

# Run with real ELM327 adapter
python main.py --real
python main.py --real --port /dev/ttyUSB0
```

## Architecture

```
opentune/
  main.py              # Terminal UI, connection flow, chat loop
  config.py            # Config, thresholds, API settings
  core/
    connection.py      # OBD2 connection — ELM327 + simulation
    scanner.py         # Full ECU scan, live monitor, anomaly detection
    session_logger.py  # JSONL session logging (the dataset funnel)
  ai/
    engineer.py        # Generative core — builds procedures on the fly
    monitor.py         # Live data AI analysis, enriched anomaly alerts
```

## Session Logs

Every diagnostic session is logged to `sessions/YYYYMMDD.jsonl`:

```json
{
  "timestamp": "2026-03-28T12:00:00Z",
  "vin": "1HGCM82633A123456",
  "vehicle": "2019 Honda Accord",
  "user_input": "engine shaking at idle, check engine light on",
  "procedure_engineered": true,
  "procedure_title": "Misfire Diagnosis — P0300",
  "steps_executed": [...],
  "outcome": "fixed",
  "live_data_snapshot": {...},
  "dtcs": [{"code": "P0300", "description": "...", "ecu": "ECM"}]
}
```

This JSONL file is the dataset that can feed OBDAgent's procedure registry and future model fine-tuning.

## Windows

```cmd
pip install -r requirements.txt
copy .env.example .env
python main.py --sim
```

Find your COM port: **Device Manager → Ports (COM & LPT)**

```cmd
python main.py --real --port COM4
```

Or use the provided launchers:

```cmd
install_windows.bat    # one-time setup
opentune.bat --sim     # run via batch script
```

```powershell
.\opentune.ps1 --sim   # run via PowerShell
```

## Requirements

- Python 3.11+
- Anthropic API key (for AI engineering; scan-only mode works without it)
- ELM327 OBD2 adapter (for real mode; simulation works without hardware)

## License

MIT — open source, open diagnostics.
