@echo off
echo Installing OpenTune...
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo Done. Edit .env -- add ANTHROPIC_API_KEY
echo Run: python main.py --sim
pause
