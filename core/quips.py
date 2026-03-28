"""
OpenTune — Quips Engine
Post-action sarcasm. Every line is mental to the cause.
"""
from __future__ import annotations
import random
from rich.console import Console
from rich.text import Text

console = Console()

QUIPS: dict[str, list[str]] = {
    "dtc_scan": [
        "That took 4 seconds. Snap-on would've charged you $180 for the privilege.",
        "Two codes found. Dealer would've told you to come back Monday.",
        "Full ECU sweep done. Your independent mechanic just saved $400 in diagnostic fees.",
        "Codes pulled. Autel's $5,000 box just got out-read by a Python script.",
        "Scan complete. The dealer's proprietary tool is crying somewhere.",
    ],
    "ai_engineer": [
        "Procedure engineered from first principles. Bosch charges $2,500 for a tool that can't do that.",
        "AI just thought its way through a problem no menu ever could. Menus don't think.",
        "Solution written. Added to the global knowledge base. Dealers added it to their price list.",
        "That procedure didn't exist anywhere. Now it does. Forever. For free.",
        "First principles engineering complete. The $80k dealer terminal is still loading its startup screen.",
    ],
    "knowledge_write": [
        "Written to the knowledge base. One more entry they can't delete, paywalled, or lock down.",
        "Saved. The database grows. The monopoly shrinks.",
        "Procedure logged. The next mechanic who faces this won't start from zero.",
        "Knowledge committed. The community just got a little smarter.",
        "Filed. Verified. Free. Forever. The way it should've always been.",
    ],
    "sim_mode": [
        "Running simulation. No OBD2 adapter required to see what $80k tools see.",
        "Sim mode active. Snap-on's dongle is $3,500. This flag is free.",
        "Fake car, real software. The dealer doesn't know the difference either.",
        "Simulation complete. Everything worked. The mechanic wins again.",
        "Sim passed. You just diagnosed a Lexus with a Python script and a USB cable.",
    ],
    "export": [
        "Report exported. Keep it. Share it. They can't send you a bill for it.",
        "Session saved. Your data, your records. Not locked in a dealer portal.",
        "Exported. The paper trail they never wanted you to have.",
        "Done. Print it, email it, frame it — it's yours.",
    ],
    "chat": [
        "AI response delivered. No booking fee. No appointment. No BS.",
        "Problem understood. The dealer's service advisor would've said 'let me check with the tech.'",
        "Conversation logged. First principles applied. Zero upsell.",
        "Diagnosis complete. The flat-rate clock wasn't running on your dime.",
    ],
    "kb_search": [
        "Knowledge base searched. Built by mechanics who actually touched the car.",
        "Results from the community. Verified by real hands on real vehicles.",
        "Found it. No subscription. No paywall. No login.",
        "Community knowledge retrieved. The OEM hates this one weird trick.",
    ],
    "component_test": [
        "Component test complete. OEMs spend millions making this cost $10,000 to access.",
        "Actuator test done. The dealer just calls this 'diagnostics' and charges $150/hr.",
        "Test passed. Another wall knocked down.",
    ],
    "live_scan": [
        "Live data streaming. Real-time. No refresh fee.",
        "Monitoring active. The engine talks. OpenTune listens. The dealer charges $200 to eavesdrop.",
        "Live scan running. Every sensor, every millisecond. Snap-on charges per-module for this.",
    ],
    "generic": [
        "Done. The knowledge is free and so are you.",
        "Complete. One less reason to set foot in a dealership.",
        "Finished. The tool is free. The knowledge is free. The future is open.",
        "Another win for the independent mechanic.",
        "Job done. The monopoly loses again.",
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

