# OpenTune

```
 ██████╗ ██████╗ ███████╗███╗   ██╗████████╗██╗   ██╗███╗   ██╗███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║╚══██╔══╝██║   ██║████╗  ██║██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║   ██║   ██║   ██║██╔██╗ ██║█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║╚██╗██║██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║   ██║   ╚██████╔╝██║ ╚████║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚══════╝
```

**Open Diagnostics. Infinite Solutions.**

The first open-source, AI-native vehicle diagnostic terminal.  
It connects to any vehicle via OBD2, reads every system, monitors every process, and converses with the mechanic in plain English.  
When a solution exists — it executes it.  
When a solution doesn't exist — **it engineers one.**

---

## The Problem

The automotive repair industry runs on locked knowledge.

Dealer scan tools cost $40,000–$80,000 a year. Independent mechanics — the majority of the industry — can't access the software needed to service modern vehicles. They are dependent on dealer networks, proprietary protocols, and software companies that have built a monopoly on diagnostic intelligence.

The mechanic is skilled. **The tool is the bottleneck.**

And the tools are designed that way on purpose.

---

## The Enemy

Every other diagnostic tool is a menu. A finite list of known procedures, built by a company, locked behind a license. Here's what that monopoly costs:

| Tool | Price | What it does |
|------|-------|--------------|
| Snap-on Pro Link | ~$8,500 | Menus |
| Autel MaxiSYS Elite II | $2,000–$5,000 | Menus, faster |
| Bosch ADS 625X | $3,500+ | Menus, nicer screen |
| Dealer factory tools (Toyota TIS, GM GDS2…) | $40,000–$80,000/yr | Menus, with a monopoly |
| **OpenTune** | **Free** | **Thinks. Learns. Never stops.** |

When a menu tool hits a procedure it doesn't know, it says: *"Not found."*  
When OpenTune hits a procedure it doesn't know, it reads the live sensor stream, correlates the data, reasons through the system, designs a solution in real time, executes it step by step — and when it's done, **it writes it down permanently, in the open, for every mechanic who comes after.**

OpenTune has no ceiling.

---

## How It Works

Connect an ELM327 OBD2 adapter. Launch OpenTune. Describe the problem the way you'd tell a colleague.

OpenTune reads the vehicle first — every active DTC, every live sensor, every module — then reasons through the fault.

```
mechanic: I need my GX suspension calibrated

OpenTune: Before I run anything — let me check what the system sees.
          → C1840 active — KDSS hydraulic fault, rear pressure below spec
          → Rear ride height -3.2cm below spec
          Is this after recent suspension work, or did the warning come on by itself?

mechanic: after replacing rear shocks

OpenTune: Got it. Engineering solution...

          Plan: KDSS Fault Clear + Rear Height Calibration
          1. Clear KDSS fault (C1840)
          2. Run rear air suspension height calibration
          3. Verify sensor baseline
          Estimated time: 8 min

          Ready to start?
```

It always reads first. Asks one clarifying question if the picture isn't complete. Lays out the full plan. Waits for your go-ahead. Then executes — step by step, with you.

Not a menu. Not a wizard. A diagnostic partner.

---

## The Knowledge Engine

Every solved problem feeds a self-building knowledge base, organized by make and system:

```
knowledge/
  toyota_lexus/
    suspension/kdss_neutralization.json       ← 17 cases, 94% success rate
    tpms/sensor_registration.json             ← 28 cases, 92% success rate
  honda_acura/
    fuel_system/throttle_body_relearn.json    ← 22 cases, 89% success rate
  ford_lincoln/
    transmission/tcm_relearn.json             ← in progress
  general/
    brakes/epb_service.json                   ← 34 cases, 98% success rate
```

Every new problem creates a new entry — symptom, solution, outcome, ECU bytes exchanged.  
Every repeat problem on a different vehicle enriches the existing one — new vehicles seen, updated success rate, refined procedure.

The more mechanics use it, the smarter it becomes for every mechanic who comes after.

This is the dataset that no company can buy and no tool can replicate.  
Built by mechanics. For mechanics. **Owned by no one.**

Before calling Claude, OpenTune searches this base for similar past solutions and injects the best matches as proven context. Over time it needs to reason from scratch less and less. It's building institutional memory.

---

## Why Open Source?

Because diagnostic knowledge should belong to mechanics, not corporations.

Snap-on doesn't sell you a tool. They sell you dependency. They spend enormous resources ensuring their tools are the only tools that can perform certain procedures on certain vehicles. They lobby. They litigate. They lock. Meanwhile an independent shop owner with 20 years of experience can't run an 8-minute calibration — because they can't afford the subscription.

Open source means:

- **No subscriptions.** No per-VIN fees. No "activation required."
- **Community ownership.** Every reverse-engineered protocol, every contributed procedure, belongs to everyone.
- **Auditability.** You can see exactly what commands OpenTune sends to your vehicle's ECUs. No black boxes.
- **Longevity.** When a tool vendor folds, their tools die. OpenTune doesn't depend on anyone staying in business.

OpenTune is to automotive diagnostics what Linux was to operating systems. What Wikipedia was to encyclopedias.

**The dealer monopoly on diagnostic software ends here.**

---

## Pricing

| Tier | Price | What you get |
|------|-------|-------------|
| **Free** | $0 | Full tool, full database, bring your own Anthropic API key |
| **Pro** | $29/mo | Managed inference — cheaper than running Claude yourself at volume |
| **Shop** | $79/mo | Multi-user, fleet mode, session analytics, priority support |

The database is always free. Always open. Always growing.  
The tool is always free. Forever.  
Price goes one direction: **down.**

---

## Installation

**Requirements:** Python 3.11+ · ELM327 OBD2 adapter (for real mode) · Anthropic API key (for AI engineering — scan-only mode works without it)

### macOS / Linux

```bash
git clone https://github.com/your-org/opentune.git
cd opentune
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

python main.py --sim            # no hardware needed
python main.py --real           # auto-detects ELM327
python main.py --real --port /dev/ttyUSB0
```

### Windows

```cmd
git clone https://github.com/your-org/opentune.git
cd opentune
install_windows.bat             :: one-click setup

python main.py --sim
python main.py --real --port COM4
```

Find your COM port: **Device Manager → Ports (COM & LPT)**

```powershell
.\opentune.ps1 --sim
.\opentune.ps1 --real --port COM4
```

---

## Architecture

```
opentune/
  main.py                  # Terminal UI, connection flow, chat loop
  config.py                # Config, thresholds, API settings
  core/
    connection.py          # OBD2 — ELM327 + simulation, auto port detection
    scanner.py             # Full ECU scan, live monitor, anomaly detection
    knowledge_engine.py    # Self-building knowledge base — record, search, browse by make
    session_logger.py      # JSONL session logging — the dataset funnel
  ai/
    engineer.py            # Generative core — builds procedures on the fly
    monitor.py             # Live data AI analysis, enriched anomaly alerts
  knowledge/               # Per-make, per-system knowledge files (auto-created)
  sessions/                # JSONL diagnostic session logs (auto-created)
```

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md).**

Short version: mechanics contribute by running sessions. Developers contribute by reverse-engineering protocols. Both matter equally. Bounties are available for cracking proprietary manufacturer protocols.

---

## Roadmap

- [ ] Multi-make knowledge expansion — Honda/Acura, Ford/Lincoln, GM, BMW, Mercedes, VW/Audi
- [ ] Web UI (FastAPI + React)
- [ ] Community knowledge sync — opt-in JSONL sharing
- [ ] Model fine-tuning pipeline on aggregated session data
- [ ] Protocol reverse-engineering toolkit
- [ ] Mobile companion via WiFi ELM327

---

## License

MIT.

---

## Open Diagnostics. Infinite Solutions.

The industry spent decades building walls around diagnostic knowledge.  
We are not asking permission to tear them down.

Every procedure OpenTune engineers, every protocol reverse-engineered, every session logged — it goes back into the commons. No one owns it. Everyone benefits.

If you're a mechanic who's been locked out of a calibration you know how to do: **this is your tool.**  
If you're a developer who believes vehicles shouldn't have proprietary black boxes: **this is your project.**  
If you think Right to Repair is a technical problem as much as a political one: **start here.**

**[Star on GitHub](#) · [Join the Discord](#) · [Read the Contributing Guide](CONTRIBUTING.md)**
