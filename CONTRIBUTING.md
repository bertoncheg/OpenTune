# Contributing to OpenTune

> "Every procedure OpenTune engineers, every protocol reverse-engineered, every session logged — it goes back into the commons. No one owns it. Everyone benefits."

OpenTune exists because mechanics deserve tools as good as the ones dealers use — and developers can build them. This is how you help.

---

## Two Kinds of Contributors. Both Essential.

**Mechanics** have the vehicles, the problems, and the ground truth. When you run a session and record the outcome — what worked, what didn't, what the ECU actually said — you are writing the knowledge base that every mechanic after you will benefit from. You don't need to write a line of code. You just need to run the tool and tell it what happened.

**Developers** have the systems knowledge to crack what manufacturers lock. Protocol reverse engineering, new make support, better AI prompts, UI improvements — every contribution expands what the tool can do for every shop running it.

Neither is more important. The tool is useless without real diagnostic outcomes. The outcomes are useless without a tool smart enough to act on them.

---

## How Mechanics Contribute

### Run Sessions, Report Outcomes

The most valuable thing you can do is use the tool on real vehicles and mark outcomes honestly.

When a session ends, OpenTune will ask: **Did this fix it?** Say yes or no. Add a note if something was different than expected. That's it. The knowledge engine writes the rest.

After enough sessions, patterns emerge:
- Which procedures work across different model years
- Which symptoms reliably point to which systems
- Which ECU bytes matter and which are noise

You are building the dataset. Every session is a data point. Every honest outcome makes the next mechanic's job easier.

### Share Edge Cases

If OpenTune engineered a solution that surprised you — or failed in an interesting way — open an issue and describe it. The more unusual the vehicle, the more valuable the case:
- High-mileage oddities
- Modified vehicles (lift kits, aftermarket suspension, engine swaps)
- Vehicles with multiple overlapping faults
- Anything where the standard procedure didn't apply

These are the cases that make the system smarter for everyone.

### Contribute Knowledge Files Directly

If you know a procedure cold — you've done it 50 times, you know exactly what the ECU expects — you can contribute it directly as a JSON knowledge file.

Format:

```json
{
  "service_type": "Throttle Body Relearn",
  "system": "fuel_system",
  "vehicles_seen": ["2018 Toyota Camry", "2020 Nissan Altima"],
  "common_symptoms": ["P0507 idle RPM high", "rough idle after cleaning"],
  "physical_solution": "After throttle body cleaning, run ECM idle relearn. Engine must be at operating temp.",
  "technical_solution": {
    "procedure_steps": [
      {"step": 1, "description": "Warm engine to 90°C coolant temp"},
      {"step": 2, "description": "Enter ECM idle relearn via UDS 31 01 02 09"},
      {"step": 3, "description": "Idle 3 minutes, no A/C load"},
      {"step": 4, "description": "Verify RPM settles to 650–800"}
    ],
    "ecu_addresses": ["0x7E0"],
    "bytes_exchanged": ["10 03", "31 01 02 09"]
  },
  "success_rate": 0.89,
  "total_cases": 22,
  "outcomes": []
}
```

Place it at: `knowledge/<make_family>/<system>/<procedure_name>.json`

Open a PR. That's it.

---

## How Developers Contribute

### Protocol Reverse Engineering (Most Valuable)

This is the frontier. This is where the wall is.

Manufacturers use UDS (ISO 14229) as the base protocol, but the specific service IDs, data identifiers, and byte sequences for proprietary functions — KDSS neutralization, EPB service modes, TPMS registration, transmission relearns — are not documented. They are guarded. The dealer tool knows them. Your tool doesn't. Yet.

Reverse engineering a proprietary procedure means:
1. Using a J2534 pass-through device or ELM327 to sniff the bus during a known procedure
2. Capturing the raw CAN frames
3. Identifying the request/response pattern
4. Writing it into a knowledge file
5. Testing it

If you crack a procedure that was previously locked behind a dealer tool, **you have just made that procedure free for every mechanic on earth who comes after you.** That is not a small thing.

### Bounty System

Some protocols are particularly valuable and particularly locked. We maintain a bounty list for these:

- GM Tech2 equivalent procedures (BCM programming, immobilizer relearn)
- BMW ISTA proprietary service functions
- Mercedes XENTRY equivalent calibrations
- Ford IDS-exclusive procedures (PCM adaptive relearn, PATS)
- Toyota/Lexus dealer-only service modes beyond what's currently seeded

When a bounty is cracked and merged, the contributor is credited permanently in the knowledge file and in the project changelog. As the project grows, bounties will have monetary value attached.

Open an issue tagged `bounty` to claim a target before you start working on it.

### Adding a New Make

To add full support for a new make family:

1. **Add the make family to `KnowledgeEngine._determine_make_family()`** in `core/knowledge_engine.py`. The method takes the vehicle display string and returns one of the standard family keys: `toyota_lexus`, `honda_acura`, `ford_lincoln`, `gm`, `bmw_mini`, `mercedes`, `nissan_infiniti`, `subaru`, `volkswagen_audi`, or `other`.

2. **Create the knowledge directory structure:**
   ```
   knowledge/<make_family>/<system>/
   ```
   Start with whatever systems you have knowledge for.

3. **Seed at least one knowledge file** so the directory isn't empty. Even a partially-complete procedure is better than nothing — mark `"total_cases": 0` and let the community fill it in.

4. **Update `KnowledgeEngine.seed_initial_knowledge()`** if you have validated procedures to seed.

5. **Open a PR** with a description of what vehicles you tested against and what procedures are covered.

### AI Prompt Improvements

The prompts in `ai/engineer.py` are the reasoning backbone. If you have a better way to structure the problem context, inject vehicle data, or elicit more reliable step-by-step procedures from Claude — test it, measure it, submit it.

Include before/after examples in your PR description.

### UI and Interface Work

The terminal UI lives in `main.py`. It uses [Rich](https://github.com/Textualize/rich) for layout. A web UI (FastAPI + React) is on the roadmap and is a significant open contribution opportunity — if you want to own that track, open an issue to coordinate.

---

## How to Add a New Vehicle Make — Step by Step

```bash
# 1. Fork and clone
git clone https://github.com/your-org/opentune.git
cd opentune

# 2. Create your knowledge directory
mkdir -p knowledge/honda_acura/fuel_system

# 3. Add your first knowledge file
# knowledge/honda_acura/fuel_system/vtec_oil_pressure_relearn.json

# 4. Add the make family mapping in core/knowledge_engine.py
#    → _determine_make_family() method

# 5. Test
python -c "from core.knowledge_engine import KnowledgeEngine; from pathlib import Path; ke = KnowledgeEngine(Path('.')); print(ke.browse_by_make('honda_acura'))"

# 6. Commit and open a PR
git checkout -b add-honda-acura-support
git add .
git commit -m "feat: add honda_acura make family + vtec oil pressure relearn"
git push origin add-honda-acura-support
```

---

## Code Style

- Python 3.11+
- Type hints on all public methods
- Docstrings on all public classes and methods
- `black` for formatting — run `black .` before committing
- No dependencies added without discussion — keep the install lightweight

---

## PR Process

1. Open an issue first for anything non-trivial — coordinate before you build
2. One concern per PR — protocol additions, make support, and UI changes are separate PRs
3. Include test output or session logs that demonstrate the change working
4. Knowledge file PRs don't need code review — they go through a faster merge process

---

## What We Don't Want

- Anything that violates the DMCA or circumvents access controls in ways that expose the project legally — be thoughtful about how you document reverse-engineered protocols
- Dependencies that phone home or collect data without disclosure
- Features that require a proprietary service to function — everything must have a free path

---

## The Bigger Picture

OpenTune is the beginning of something.

The knowledge base that gets built here — procedure by procedure, outcome by outcome, protocol by protocol — is a public good. It is the accumulated diagnostic intelligence of every mechanic and developer who contributed. It cannot be bought, cannot be locked, cannot be taken away.

Every contribution you make is permanent. Every protocol you crack makes that calibration free for every independent shop that comes after you.

That's the point. That's why this exists.

**Welcome.**
