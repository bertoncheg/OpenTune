# OpenTune

**The first open-source, AI-native vehicle diagnostic terminal.**

Free forever. Gets smarter forever.

---

## The Problem — And The Opportunity

Dealer diagnostic tools cost $80,000. Independent mechanics are locked out.

But that is not the real problem.

The real problem is that every mechanic in the world is solving the same faults in isolation — on forums, in notes, in their head — and none of it connects. A mechanic in Houston figures out a rare KDSS fault on a 2007 GX470. A mechanic in São Paulo is staring at the exact same fault tomorrow. They will never meet. The knowledge dies with the session.

Meanwhile, the software world solved this twenty years ago. Linux did not beat Unix because one company out-engineered another. It won because a million engineers contributed to one shared foundation that nobody owned. npm has over two million packages — built by strangers for strangers, stacked into something no single company could have funded. Stack Overflow turned individual answers into a permanent global knowledge layer. The pattern is always the same: **open contribution compounds faster than any closed team can move.**

The automotive repair world has never had that. Until now.

**OpenTune is not just a diagnostic tool. It is the foundation for a unified, ever-feeding vehicle diagnostic engine** — one that gets smarter every time any mechanic anywhere uses it. Every fault cleared, every procedure engineered, every outcome logged feeds back into a shared knowledge base that belongs to the community, not to Snap-on, not to Autel, not to any dealer network.

The math is simple: if 1,000 mechanics contribute one diagnostic outcome each, we have 1,000 solved problems. If 100,000 mechanics contribute, we have the most comprehensive free diagnostic database ever built — covering makes, models, edge cases, and failure modes that no $15,000 proprietary tool even knows exist.

**This window is open right now. The earlier you contribute, the more the community inherits from your experience.** The mechanic who logs ten sessions in month one shapes what the tool knows in year three.

And this is just the beginning. The same engine that diagnoses faults will soon power vehicle tuning — mapping fuel trims, analyzing sensor baselines, recommending calibration changes. Instead of spending hours searching forums for someone who maybe tuned the same engine five years ago, you open OpenTune. The community already figured it out. It is waiting for you.

**Open diagnostics time. Nothing accelerates faster than community effort.**

---

## What It Does

Connect an ELM327 adapter. OpenTune reads every ECU, surfaces every fault, and if a solution exists it runs it. If one does not exist — it engineers one from first principles using Claude.

Every outcome gets logged to the community knowledge base that nobody owns and nobody can take away.

- Scans all ECUs on connect — reads every DTC with plain-English descriptions
- Monitors live vehicle data in real time — flags anomalies as they happen
- Chat in plain English about any vehicle problem
- Runs known procedures. Engineers unknown ones.
- Writes every outcome to the community diagnostic database

---

## Conversation Flow

OpenTune never opens with a blunt Y/N prompt. It reads the vehicle first, then asks:

```
mechanic: I need my GX suspension calibrated

OpenTune: Before I run anything — let me check what the system sees.
          C1840 active — KDSS hydraulic fault, rear pressure below spec
          Rear ride height -3.2cm below spec
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

The AI always: reads data first, asks one clarifying question if needed, summarizes findings + plan, waits for confirmation. Never just "Run it? Y/N".

---

## The Knowledge Base

Every diagnostic session that resolves a fault gets written to a shared, open knowledge base.

Search it. Browse it. Submit to it. It belongs to the community.

Over time it becomes the largest free diagnostic procedure database on earth — built by mechanics, for mechanics, unkillable because it is owned by no one.

---

## Run It

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# Connect your ELM327 adapter and run
python main.py

# Windows: specify COM port if needed
python main.py --port COM4
```

**Windows launchers:**

```cmd
install_windows.bat    # one-time setup
opentune.bat           # run
```

```powershell
.\opentune.ps1         # run via PowerShell
```

Find your COM port: **Device Manager > Ports (COM & LPT)**

---

## Knowledge API

Run the local knowledge API to browse, search, and submit procedures:

```bash
uvicorn api.main:app --reload --port 8765
```

Endpoints: `/health` `/search` `/browse` `/submit` `/verify` `/stats`

---

## Architecture

```
opentune/
  main.py              # Terminal UI, connection flow, chat loop
  core/
    connection.py      # OBD2 connection — ELM327
    scanner.py         # Full ECU scan, live monitor, anomaly detection
    session_logger.py  # JSONL session logging
    knowledge_engine.py# Procedure lookup and execution
    live_scan.py       # Real-time data monitor
    quips.py           # Because diagnostics should have personality
  ai/
    engineer.py        # Generative core — builds procedures on the fly
    monitor.py         # Live data AI analysis, anomaly enrichment
  api/
    main.py            # FastAPI knowledge base server
    db.py              # SQLite / Postgres-ready schema
    embeddings.py      # Semantic search (sentence-transformers, local, free)
    seed.py            # Seed procedures loader
  knowledge/           # Seeded diagnostic procedures (KDSS, EPB, TPMS, and more)
```

---

## Pricing

| Tier | Price | What you get |
|------|-------|--------------|
| Free | $0 | Bring your own API key. Full diagnostic terminal. Community KB always free. |
| Pro | $29/mo | Hosted AI, priority KB access, session history |
| Shop | $99/mo | Multi-bay, team accounts, shop reporting |

The knowledge database is always free. Price trajectory: down forever.

---

## Requirements

- Python 3.11+
- ELM327 OBD2 adapter (USB or Bluetooth)
- Anthropic API key (or Pro/Shop subscription for hosted AI)

---

## License

MIT — open source, open diagnostics.

---

*Built for the mechanic who is better than the tool they can afford.*
