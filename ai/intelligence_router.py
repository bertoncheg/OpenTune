"""
OpenTune Intelligence Router
Routes diagnostic requests to the appropriate AI tier based on complexity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Tier model maps
# ---------------------------------------------------------------------------

TIER2_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-3-5",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openrouter/auto",
}

TIER3_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-1.5-pro",
    "openrouter": "openrouter/auto",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ComplexityScore:
    dtc_count: int
    multi_system: bool
    anomaly_count: int
    procedure_trust: str        # "validated" | "research" | "unknown"
    score: float                # 0.0-1.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class TierRecommendation:
    tier: int                   # 1, 2, or 3
    model_name: str
    provider: str
    estimated_cost: str         # "$0.00", "~$0.002", "~$0.08"
    reason: str
    can_escalate: bool


# ---------------------------------------------------------------------------
# IntelligenceRouter
# ---------------------------------------------------------------------------

class IntelligenceRouter:
    """
    Routes diagnostic requests to the appropriate AI tier.

    Tier 1 — Local Ollama (free, private, fast for simple tasks)
    Tier 2 — Cloud efficient model (cheap, good for moderate complexity)
    Tier 3 — Cloud power model (best quality for complex multi-system faults)
    """

    def __init__(
        self,
        api_key: str | None = None,
        ollama_model: str = "llama3.2:3b",
    ) -> None:
        self._ollama_model = ollama_model
        self._ollama_available = False
        self._provider_config = None
        self._completion_fn: Callable | None = None
        self._provider_name: str = ""
        self._tier2_model: str = ""
        self._tier3_model: str = ""

        # Check Ollama
        try:
            from ai.ollama_setup import is_ollama_running
            self._ollama_available = is_ollama_running()
        except Exception:
            self._ollama_available = False

        # Set up cloud provider
        if api_key:
            try:
                from ai.key_resolver import get_litellm_client
                config, completion_fn = get_litellm_client(api_key)
                self._provider_config = config
                self._completion_fn = completion_fn
                self._provider_name = config.name
                self._tier2_model = TIER2_MODELS.get(config.name, config.default_model)
                self._tier3_model = TIER3_MODELS.get(config.name, config.default_model)
            except Exception as exc:
                console.print(f"[dim yellow][Router] Could not init cloud provider: {exc}[/dim yellow]")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ollama_available(self) -> bool:
        return self._ollama_available

    @property
    def cloud_available(self) -> bool:
        return self._completion_fn is not None

    @property
    def available_tiers(self) -> list[int]:
        tiers: list[int] = []
        if self._ollama_available:
            tiers.append(1)
        if self._completion_fn is not None:
            tiers.append(2)
            tiers.append(3)
        return tiers

    # ------------------------------------------------------------------
    # Complexity assessment
    # ------------------------------------------------------------------

    def assess_complexity(
        self,
        dtcs: list,
        live_data=None,
        procedure_trust: str = "unknown",
    ) -> ComplexityScore:
        """Score diagnostic complexity on a 0.0–1.0 scale."""
        score = 0.0
        reasons: list[str] = []

        # DTC count scoring
        dtc_count = len(dtcs) if dtcs else 0
        dtc_score_map = {0: 0.0, 1: 0.1, 2: 0.3, 3: 0.5}
        dtc_score = dtc_score_map.get(dtc_count, 0.8)
        score += dtc_score
        if dtc_count > 0:
            reasons.append(f"{dtc_count} DTC(s) → +{dtc_score:.1f}")

        # Multi-system check (DTC prefixes spanning P/C/B/U)
        multi_system = False
        if dtcs:
            prefixes = set()
            for dtc in dtcs:
                code = getattr(dtc, "code", str(dtc))
                if code and len(code) > 0:
                    prefixes.add(code[0].upper())
            relevant = prefixes & {"P", "C", "B", "U"}
            if len(relevant) > 1:
                multi_system = True
                score += 0.2
                reasons.append(f"Multi-system DTCs ({', '.join(sorted(relevant))}) → +0.2")

        # Anomaly count from live data
        anomaly_count = 0
        if live_data is not None:
            try:
                if hasattr(live_data, "anomalies"):
                    anomaly_count = len(live_data.anomalies)
                elif hasattr(live_data, "snapshot"):
                    snap = live_data.snapshot()
                    anomaly_count = sum(
                        1 for v in snap.values()
                        if v is not None and isinstance(v, (int, float)) and (v < 0 or v > 1000)
                    )
            except Exception:
                pass
            if anomaly_count > 2:
                score += 0.15
                reasons.append(f"{anomaly_count} live data anomalies → +0.15")

        # Procedure trust
        trust_delta = {"unknown": 0.2, "research": 0.1, "validated": 0.0}.get(
            procedure_trust, 0.2
        )
        score += trust_delta
        if trust_delta > 0:
            reasons.append(f"Procedure trust '{procedure_trust}' → +{trust_delta:.1f}")

        score = min(1.0, score)

        return ComplexityScore(
            dtc_count=dtc_count,
            multi_system=multi_system,
            anomaly_count=anomaly_count,
            procedure_trust=procedure_trust,
            score=round(score, 3),
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Tier recommendation
    # ------------------------------------------------------------------

    def recommend_tier(self, score: ComplexityScore) -> TierRecommendation:
        """Recommend a tier based on complexity score, falling back if unavailable."""
        if score.score < 0.4:
            preferred = 1
            reason = f"Low complexity (score={score.score:.2f}) — local model sufficient"
        elif score.score <= 0.7:
            preferred = 2
            reason = f"Moderate complexity (score={score.score:.2f}) — efficient cloud model"
        else:
            preferred = 3
            reason = f"High complexity (score={score.score:.2f}) — power model needed"

        available = self.available_tiers
        if not available:
            return TierRecommendation(
                tier=0, model_name="none", provider="none",
                estimated_cost="$0.00",
                reason="No AI tiers available — fallback mode",
                can_escalate=False,
            )

        # Fall back to highest available if preferred not available
        tier = preferred if preferred in available else max(available)

        model_name, provider, cost = self._tier_meta(tier)
        can_escalate = any(t > tier for t in available)

        return TierRecommendation(
            tier=tier,
            model_name=model_name,
            provider=provider,
            estimated_cost=cost,
            reason=reason,
            can_escalate=can_escalate,
        )

    def _tier_meta(self, tier: int) -> tuple[str, str, str]:
        if tier == 1:
            return self._ollama_model, "ollama", "$0.00"
        if tier == 2:
            return self._tier2_model, self._provider_name, "~$0.002"
        if tier == 3:
            return self._tier3_model, self._provider_name, "~$0.08"
        return "unknown", "unknown", "$0.00"

    # ------------------------------------------------------------------
    # Cost estimate
    # ------------------------------------------------------------------

    def estimate_cost(self, tier: int, context_tokens: int = 2000) -> str:
        if tier == 1:
            return "$0.00"
        # Very rough token-based estimates (input + output combined)
        tokens_k = context_tokens / 1000
        if tier == 2:
            # ~$0.0005/1K tokens for efficient models
            cost = tokens_k * 0.0005
            return f"~${cost:.4f}"
        if tier == 3:
            # ~$0.005/1K tokens for power models
            cost = tokens_k * 0.005
            return f"~${cost:.4f}"
        return "$0.00"

    # ------------------------------------------------------------------
    # Completion function access
    # ------------------------------------------------------------------

    def get_completion_fn(self, tier: int) -> tuple[str, Callable]:
        """Return (model_name, callable) for the requested tier."""
        if tier == 1:
            model_name = f"ollama/{self._ollama_model}"

            # Prefer litellm with ollama/ prefix
            try:
                import litellm  # type: ignore

                def _ollama_litellm(
                    messages: list[dict],
                    *,
                    system: str | None = None,
                    max_tokens: int = 1024,
                    **kwargs: Any,
                ) -> Any:
                    full_messages = messages
                    if system:
                        full_messages = [{"role": "system", "content": system}] + messages
                    return litellm.completion(
                        model=model_name,
                        messages=full_messages,
                        max_tokens=max_tokens,
                        **kwargs,
                    )

                return model_name, _ollama_litellm
            except ImportError:
                pass

            # Direct HTTP fallback
            def _ollama_http(
                messages: list[dict],
                *,
                system: str | None = None,
                max_tokens: int = 1024,
                **kwargs: Any,
            ) -> Any:
                import requests as _req
                full_messages = messages
                if system:
                    full_messages = [{"role": "system", "content": system}] + messages
                resp = _req.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": self._ollama_model,
                        "messages": full_messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                    timeout=120,
                )
                return resp.json()

            return self._ollama_model, _ollama_http

        if tier in (2, 3) and self._completion_fn is not None:
            target_model = self._tier2_model if tier == 2 else self._tier3_model
            provider_name = self._provider_name

            def _cloud_fn(
                messages: list[dict],
                *,
                system: str | None = None,
                max_tokens: int = 1024,
                **kwargs: Any,
            ) -> Any:
                try:
                    import litellm  # type: ignore
                    import os as _os
                    full_messages = messages
                    if system:
                        full_messages = [{"role": "system", "content": system}] + messages
                    # Resolve provider prefix for litellm
                    prefix_map = {
                        "anthropic": "anthropic/",
                        "openai": "openai/",
                        "groq": "groq/",
                        "gemini": "gemini/",
                        "openrouter": "",
                    }
                    prefix = prefix_map.get(provider_name, "")
                    model = target_model if target_model.startswith(prefix) else f"{prefix}{target_model}"
                    return litellm.completion(
                        model=model,
                        messages=full_messages,
                        max_tokens=max_tokens,
                        **kwargs,
                    )
                except ImportError:
                    # Fall through to stored completion_fn (may use different model)
                    return self._completion_fn(  # type: ignore[misc]
                        messages, system=system, max_tokens=max_tokens, **kwargs
                    )

            return target_model, _cloud_fn

        raise RuntimeError(f"Tier {tier} not available.")

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        messages: list[dict],
        system: str,
        tier: int,
        max_tokens: int = 1024,
    ) -> str:
        """Call the appropriate tier and return response text."""
        try:
            model_name, fn = self.get_completion_fn(tier)
            response = fn(messages, system=system, max_tokens=max_tokens)
            return self._extract_text(response)
        except Exception as exc:
            console.print(f"[dim red][Router] Tier {tier} execution failed: {exc}[/dim red]")
            raise

    def _extract_text(self, response: Any) -> str:
        """Normalize response shape from litellm / anthropic / openai / ollama HTTP."""
        if response is None:
            return ""
        # litellm / openai SDK
        if hasattr(response, "choices"):
            return response.choices[0].message.content.strip()
        # anthropic SDK
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, list) and content:
                return content[0].text.strip()
            return str(content).strip()
        # ollama direct HTTP (dict with message.content)
        if isinstance(response, dict):
            msg = response.get("message", {})
            if isinstance(msg, dict):
                return msg.get("content", "").strip()
            # fallback
            return str(response).strip()
        return str(response).strip()
