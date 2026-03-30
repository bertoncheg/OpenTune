"""
OpenTune - Quips Engine
Post-action sarcasm. Every line is mental to the cause.
"""
from __future__ import annotations
import random
from rich.console import Console
from rich.text import Text

console = Console()

QUIPS: dict[str, list[str]] = {
    "dtc_scan": [
        "Scan complete. That took seconds. Not a service appointment.",
        "Two codes found. The shop would've told you to come back Monday.",
        "Full ECU sweep done. No waiting room. No clipboard. No bill.",
        "Codes pulled. The proprietary tool just got out-read by an open script.",
        "Scan done. You now know exactly what you're dealing with.",
    ],
    "ai_engineer": [
        "Procedure engineered from first principles. No menu could've done that.",
        "AI just thought its way through a problem no dropdown ever could.",
        "Solution written. Added to the global knowledge base.",
        "That procedure didn't exist anywhere. Now it does. Forever. For free.",
        "First principles engineering complete. The walled garden just lost another brick.",
    ],
    "knowledge_write": [
        "Written to the knowledge base. One more entry that can't be paywalled or locked down.",
        "Saved. The database grows. The monopoly shrinks.",
        "Procedure logged. The next mechanic who faces this won't start from zero.",
        "Knowledge committed. The community just got a little smarter.",
        "Filed. Verified. Free. Forever. The way it should've always been.",
    ],
    "sim_mode": [
        "Running simulation. No adapter required to see what locked tools see.",
        "Sim mode active. The dongle is optional. The knowledge is not.",
        "Fake car, real software. The process is identical.",
        "Simulation complete. Everything worked. The mechanic wins again.",
        "Sim passed. Diagnosed with a Python script and a USB cable.",
    ],
    "export": [
        "Report exported. Keep it. Share it. Nobody can send you a bill for it.",
        "Session saved. Your data, your records. Not locked in a portal.",
        "Exported. The paper trail they never wanted you to have.",
        "Done. Print it, email it, frame it — it's yours.",
    ],
    "chat": [
        "AI response delivered. No booking fee. No appointment. No BS.",
        "Problem understood. The advisor would've said 'let me check with the tech.'",
        "Conversation logged. First principles applied. Zero upsell.",
        "Diagnosis complete. The clock wasn't running on your dime.",
    ],
    "kb_search": [
        "Knowledge base searched. Built by mechanics who actually touched the car.",
        "Results from the community. Verified by real hands on real vehicles.",
        "Found it. No subscription. No paywall. No login.",
        "Community knowledge retrieved. The closed system hates this.",
    ],
    "component_test": [
        "Component test complete. This capability was designed to be inaccessible. It isn't.",
        "Actuator test done. The shop calls this 'diagnostics' and bills by the hour.",
        "Test passed. Another wall knocked down.",
    ],
    "live_scan": [
        "Live data streaming. Real-time. No refresh fee.",
        "Monitoring active. The engine talks. OpenTune listens.",
        "Live scan running. Every sensor, every millisecond.",
    ],
    "generic": [
        "Done. The knowledge is free and so are you.",
        "Complete. One less reason to hand over the keys.",
        "Finished. The tool is free. The knowledge is free. The future is open.",
        "Another win for the independent mechanic.",
        "Job done. The closed system loses again.",
    ],
}


def quip(category: str = "generic") -> None:
    """Print a styled sarcastic quip tied to the OpenTune mission."""
    lines = QUIPS.get(category, QUIPS["generic"])
    text = random.choice(lines)

    styled = Text()
    styled.append("  >> ", style="bold yellow")
    styled.append(text, style="dim italic white")

    console.print()
    console.print(styled)
    console.print()
