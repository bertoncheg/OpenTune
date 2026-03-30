# OpenTune

**The first open-source, AI-native vehicle diagnostic terminal.**

Free forever. Gets smarter forever.

---

## The Problem — And The Opportunity

Dealer diagnostic tools cost $80,000. Independent mechanics are locked out.

But that is not the real problem.

The real problem is fragmentation. Every mechanic in the world is solving the same faults in isolation — on forums, in notes, in their head — and none of it connects. A mechanic in Houston cracks a rare KDSS fault on a 2007 GX470 after three hours of trial and error. A mechanic in São Paulo faces the exact same fault tomorrow. They will never meet. The knowledge evaporates with the session.

Multiply that by every make, every model, every edge case, every failure mode — across millions of mechanics, across decades. An incomprehensible amount of hard-won diagnostic knowledge, generated every single day, disappearing every single day.

The software world solved this problem twenty years ago and never looked back. Linux did not beat Unix because one company out-engineered another — it won because a million engineers contributed to one shared foundation that nobody owned. npm crossed two million packages built by strangers for strangers, stacked into something no single company could have funded in ten lifetimes. Stack Overflow turned isolated answers into a permanent, searchable, compounding global knowledge layer. Git turned individual work into collective infrastructure. The pattern never changes: **open contribution compounds faster than any closed team can move. Always.**

The automotive repair world has never had this. The knowledge has always been siloed — locked inside proprietary tools, buried in forum threads, living in the heads of mechanics who retire and take it with them.

**OpenTune is the fix.** Not just a diagnostic tool — the foundation for a unified, ever-feeding vehicle diagnostic engine that gets smarter every time any mechanic anywhere uses it. Every fault cleared, every procedure engineered, every outcome logged feeds back into a shared knowledge base owned by the community, not by Snap-on, not by Autel, not by any dealer network.

The math compounds fast. One thousand mechanics contributing one outcome each gives the community one thousand solved problems. One hundred thousand mechanics gives it the most comprehensive free diagnostic database ever assembled — covering makes, models, edge cases, and failure modes that no $15,000 proprietary scanner even knows exist. The database never stops growing. It never gets taken away.

**This window is open right now.** The earlier you contribute, the more the community inherits from your experience. The mechanic who logs ten sessions in month one shapes what the tool knows in year three. Early contributors are not just users — they are the authors of what this becomes.

And diagnostics is only the beginning. The same engine will soon power tuning — mapping fuel trims, reading sensor baselines, engineering calibration changes from real-world data. Instead of spending hours searching a forum thread from 2019 hoping someone tuned your exact engine combination, you open OpenTune. The community already solved it. It is waiting for you.

One more thing. Every time a manufacturer locks a protocol, encrypts a calibration file, or paywalls a reset procedure — they are not protecting their product. They are handing us a roadmap. Every locked system we encounter gets documented, understood, and added to the knowledge base. History does not lie: DRM did not stop piracy, it accelerated reverse engineering. Locked bootloaders did not kill custom ROMs — they created XDA Developers. Walled gardens do not stop determined communities, they focus them. **Every wall they build tells us exactly where the value is.**

**Open diagnostics time. Nothing accelerates faster than community.**

---

## What It Does

Plug in an ELM327 adapter. OpenTune reads every ECU, surfaces every fault, and executes the solution — or engineers one from scratch when none exists, using Claude as the reasoning engine.

Every session outcome is logged to the community knowledge base. Permanently. Freely.

- **Full ECU scan** — every DTC across every system, plain-English descriptions, severity context
- **Live data monitoring** — real-time anomaly detection running in the background while you work
- **Natural language chat** — describe any problem in plain English, get a reasoned diagnostic response
- **Procedure execution** — runs known procedures from the community knowledge base
- **Procedure engineering** — when no procedure exists, builds one from first principles on the spot
- **Automatic knowledge contribution** — every resolved session feeds back into the shared database

---

## How It Thinks

OpenTune never opens with a blunt prompt. It reads the vehicle first, then asks:

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

Read first. One clarifying question if needed. Summarize findings and plan. Wait for confirmation. Never "Run it? Y/N."

---

## The Knowledge Base

Every diagnostic session that resolves a fault is written to the community knowledge base — searchable, browsable, free to submit to, free forever.

This is the moat. Not the software. The software can be forked, cloned, rewritten. The knowledge base — built from millions of real diagnostic sessions, verified by mechanics who were actually there — cannot be replicated by any company with a budget and a deadline. It grows because mechanics use it. It gets more accurate because mechanics correct it. It covers obscure edge cases because someone, somewhere, already hit that fault and logged the fix.

Linux took a decade to become indispensable infrastructure. Stack Overflow took years to become the default. The OpenTune knowledge base compounds the same way — and every session you run today is a contribution to what it becomes.

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

Find your COM port: **Device Manager → Ports (COM & LPT)**

---

## Knowledge API

The local knowledge API lets you browse, search, and submit procedures directly:

```bash
uvicorn api.main:app --reload --port 8765
```

`/health` `/search` `/browse` `/submit` `/verify` `/stats`

---

## Architecture

```
opentune/
  main.py               # Terminal UI, connection flow, chat loop
  core/
    connection.py        # OBD2 connection — ELM327
    scanner.py           # Full ECU scan, live monitor, anomaly detection
    session_logger.py    # JSONL session logging
    knowledge_engine.py  # Procedure lookup and execution
    live_scan.py         # Real-time data monitor
    quips.py             # Because diagnostics should have personality
  ai/
    engineer.py          # Generative core — builds procedures on the fly
    monitor.py           # Live data AI analysis, anomaly enrichment
  api/
    main.py              # FastAPI knowledge base server
    db.py                # SQLite / Postgres-ready schema
    embeddings.py        # Semantic search (sentence-transformers, local, free)
    seed.py              # Seed procedures loader
  knowledge/             # Seeded procedures — KDSS, EPB, TPMS, SAS, Throttle, and more
```

---

## Pricing

| Tier | Price | What you get |
|------|-------|--------------|
| Free | $0 | Bring your own API key. Full terminal. Community KB always free. |
| Pro | $29/mo | Hosted AI, priority KB access, full session history |
| Shop | $99/mo | Multi-bay, team accounts, shop-level reporting |

The knowledge database is always free. No exceptions. Price trajectory: down forever.

---

## Requirements

- Python 3.11+
- ELM327 OBD2 adapter (USB or Bluetooth)
- Anthropic API key — or a Pro/Shop subscription for hosted AI

---

## License

MIT — open source, open diagnostics.

---

*Built for the mechanic who is better than the tool they can afford.*

*The tool is catching up.*
