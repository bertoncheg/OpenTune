#!/bin/bash
# Manually rebuild the Windows zip anytime
python3 -c "
import zipfile
from pathlib import Path

source = Path('/Users/newowner/Desktop/OpenTune')
output = Path('/Users/newowner/Desktop/OpenTune-Windows.zip')
exclude = {'.git', '__pycache__', '.env'}

with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
    for file in source.rglob('*'):
        if file.is_file() and not any(x in file.parts for x in exclude) and not file.suffix == '.pyc':
            arcname = 'OpenTune/' + str(file.relative_to(source))
            zf.write(file, arcname)
print(f'Built: {output} ({output.stat().st_size // 1024}KB)')
"
