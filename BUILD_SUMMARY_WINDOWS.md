# OpenTune — Windows Port Summary

**Date:** 2026-03-28
**Base version:** v0.1.0
**Status:** Complete

---

## Changes Made

### core/connection.py
- Added `detect_serial_port()` function using `platform.system()` and `serial.tools.list_ports.comports()`
- Windows: scans COM ports reported by pyserial, returns first match
- macOS/Linux: globs `/dev/tty.usbserial-*` and `/dev/ttyUSB*`
- Clear error if none found: `"Connect ELM327, check Device Manager → Ports (COM & LPT)"`
- `_connect_real()` now calls `detect_serial_port()` automatically when no explicit port was provided

### config.py
- Added `from pathlib import Path`
- `load_dotenv()` → `load_dotenv(Path(__file__).parent / ".env")` — loads .env from script directory, not CWD
- `SESSION_LOG_DIR` default now uses `str(Path(__file__).parent / "sessions")` — absolute, portable
- `DEFAULT_PORT` now platform-aware: `"COM3"` on Windows, `"/dev/ttyUSB0"` otherwise

### main.py
- Added `import colorama; colorama.init()` at module top, before any Rich output
- Required for ANSI escape code support on Windows terminals

### requirements.txt
- Added `colorama>=0.4.6`

### core/scanner.py
- `LiveMonitor` thread already had `daemon=True` — no change needed

### New Files
| File | Purpose |
|------|---------|
| `opentune.bat` | `@echo off / python main.py %*` — CMD launcher |
| `opentune.ps1` | `python main.py @args` — PowerShell launcher |
| `install_windows.bat` | One-click setup: pip install, .env copy, usage hint |

### README.md
- Added **Windows** section: install, .env setup, sim run, COM port lookup, launcher usage

---

## Windows Quick Start

```cmd
install_windows.bat
python main.py --sim
python main.py --real --port COM4
```

---

## Files NOT Changed (platform-agnostic)
- `ai/engineer.py`
- `ai/monitor.py`
- `core/session_logger.py` (already used pathlib throughout)
- Rich UI styling, JSONL format, conversation logic

---

## Verification

```
python -c "import main; print('Windows port OK')"
```
