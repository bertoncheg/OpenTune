"""
Component Test — Mode 08 / UDS 0x2F actuator activation.
Safety-guarded activation of on-board components for diagnostic purposes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from core.connection import OBDConnection


@dataclass
class ComponentTest:
    name: str
    description: str
    component_id: int
    action_on: int
    action_off: int
    safety_warning: str
    category: str


COMPONENT_TESTS: list[ComponentTest] = [
    ComponentTest(
        name="Fuel Pump Relay",
        description="Activate fuel pump to verify pressure build-up",
        component_id=0x01,
        action_on=0x01,
        action_off=0x00,
        safety_warning="Engine must be OFF. Fire hazard if fuel line is disconnected.",
        category="fuel",
    ),
    ComponentTest(
        name="Cooling Fan — Low Speed",
        description="Activate radiator fan at low speed",
        component_id=0x04,
        action_on=0x01,
        action_off=0x00,
        safety_warning="Keep clear of fan blades. Engine bay access may be required.",
        category="cooling",
    ),
    ComponentTest(
        name="Cooling Fan — High Speed",
        description="Activate radiator fan at high speed",
        component_id=0x04,
        action_on=0x02,
        action_off=0x00,
        safety_warning="Keep clear of fan blades. High speed — loud. Fingers away.",
        category="cooling",
    ),
    ComponentTest(
        name="EVAP Purge Solenoid",
        description="Open EVAP purge solenoid to test vapor recovery circuit",
        component_id=0x0A,
        action_on=0x01,
        action_off=0x00,
        safety_warning="Ensure no fuel vapors are present in work area. EVAP system must be intact.",
        category="evap",
    ),
    ComponentTest(
        name="MIL (Check Engine Light)",
        description="Illuminate MIL to verify bulb and wiring circuit",
        component_id=0x0B,
        action_on=0x01,
        action_off=0x00,
        safety_warning="For circuit verification only — MIL will illuminate briefly.",
        category="electrical",
    ),
]


@dataclass
class ComponentTestResult:
    component_name: str
    success: bool
    message: str
    duration_seconds: float


class ComponentTester:
    """Wraps Mode 08 component activation with safety confirmation."""

    def __init__(self, connection: OBDConnection) -> None:
        self.conn = connection

    def get_available_tests(self) -> list[ComponentTest]:
        return list(COMPONENT_TESTS)

    def run_test(self, test: ComponentTest) -> ComponentTestResult:
        start = time.time()
        try:
            success = self.conn.activate_component(test.component_id, test.action_on)
            if success:
                time.sleep(2.0)  # hold activated for 2 s
                self.conn.activate_component(test.component_id, test.action_off)
                return ComponentTestResult(
                    component_name=test.name,
                    success=True,
                    message="Component activated successfully",
                    duration_seconds=time.time() - start,
                )
            return ComponentTestResult(
                component_name=test.name,
                success=False,
                message="No response from ECU — component may not be supported on this vehicle",
                duration_seconds=time.time() - start,
            )
        except Exception as exc:
            return ComponentTestResult(
                component_name=test.name,
                success=False,
                message=f"Error: {exc}",
                duration_seconds=time.time() - start,
            )
