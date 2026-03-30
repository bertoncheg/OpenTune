# Handoff to Bobby (BobMyClaw) — 2026-03-30

## What Just Landed on Your Desktop

The OpenTune folder at `C:\Users\berto\Desktop\OpenTune\` was just fully updated from Mac via Tailscale. This is a major UX overhaul — new welcome flow, AI tier selection, and OBD hot-plug detection.

---

## What's New

### 1. Welcome Wizard (first run only)
When you launch for the first time you'll see a 5-screen setup flow:
- **Screen 1** — OpenTune branding + value prop
- **Screen 2** — Ollama local AI install (free, runs on your machine, progress bar)
- **Screen 3** — Tier explanation: Free (local) / Standard $0.002 / Deep $0.08
- **Screen 4** — Optional API key entry (skip if you want to run free-only)
- **Screen 5** — Ready to launch

The wizard only runs once. After that it boots straight to the OBD interface.

### 2. AI Tier System
- **Tier 1 (Free):** Ollama local — llama3.2:3b, runs on your laptop, no API key needed
- **Tier 2 ($0.002):** Cloud efficient — Haiku/GPT-4o-mini (needs API key)
- **Tier 3 ($0.08):** Cloud power — Sonnet/GPT-4o (needs API key)
- OpenTune always tries free first. If low confidence, it asks before spending credits.

### 3. OBD Hot-Plug Detection
- App scans for ELM327 on all COM ports at startup
- If no adapter: drops to AI chat mode (still fully useful)
- Background polling every 10s — plug in the adapter anytime, banner appears: "🔌 OBD adapter detected! Press S to switch to Live Scan"

### 4. Settings Screen
Accessible from main menu — edit API key, check Ollama status, reset wizard.

---

## How to Run It

**First time (installs dependencies):**
```powershell
cd C:\Users\berto\Desktop\OpenTune
pip install -r requirements.txt
python main.py
```

**Every time after:**
```powershell
cd C:\Users\berto\Desktop\OpenTune
python main.py
```

**Dev/testing (skip wizard, simulation mode):**
```powershell
python main.py --skip-wizard --sim
```

---

## Important: Delete Old settings.json If It Exists

If you have a leftover `config\settings.json` from a previous version, delete it first so the wizard fires:
```powershell
del C:\Users\berto\Desktop\OpenTune\config\settings.json
```
(No file exists there right now — you're clean.)

---

## Ollama on Windows

The wizard will try to auto-install Ollama. If it fails:
1. Download manually: https://ollama.ai/download
2. Install and run it
3. Then: `ollama pull llama3.2:3b`
4. Relaunch OpenTune — it'll detect Ollama automatically

---

## Report Back

Once you've run the wizard and tested it, let Phoenix (Mac) know:
- Did the wizard complete cleanly?
- Did Ollama install or did you need to do it manually?
- Any errors on screen?
- Does `--sim` mode work after wizard completes?

Mac is standing by.
