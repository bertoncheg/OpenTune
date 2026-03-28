content = open(r'C:\Users\berto\OneDrive\OpenTune\ai\engineer.py', encoding='utf-8').read()
old = '_OBDAGENT_PROC_DIR = "/Users/newowner/Desktop/OBDAgent/obdagent-toyota/procedures"'
new = '''from pathlib import Path as _Path


def _resolve_obdagent_proc_dir() -> str:
    candidate = _Path(__file__).parent.parent.parent / "Desktop" / "obdagent-toyota" / "procedures"
    if candidate.exists():
        return str(candidate)
    fallback = _Path(r"C:\Users\berto\OneDrive\Desktop\obdagent-toyota\procedures")
    if fallback.exists():
        return str(fallback)
    return str(candidate)


_OBDAGENT_PROC_DIR = _resolve_obdagent_proc_dir()'''
assert old in content, 'not found: ' + repr(content[content.find('_OBDAGENT'):content.find('_OBDAGENT')+80])
content = content.replace(old, new)
open(r'C:\Users\berto\OneDrive\OpenTune\ai\engineer.py', 'w', encoding='utf-8').write(content)
print('OK')
