"""Example target file."""

from __future__ import annotations

import json

RequestEnvelope = dict[str, object]
ResultEnvelope = dict[str, object]

COMPONENT_SPEC: dict[str, object] = {
    "component_id": "placeholder",
    "component_kind": "function",
    "domain": "general_algorithm",
    "interface_signature": "def solve(data: list[int]) -> list[int]",
    "name": "solve",
    "single_component_policy": True,
    "source": "workspace_init",
}


def solve(data: list[int]) -> list[int]:
    """Return data unchanged until pythalab-agent updates the implementation."""
    return list(data)


def build_demo_request() -> RequestEnvelope:
    """Build a deterministic smoke request for direct execution."""
    return {
        "inputs": {"data": [3, 1, 2]},
        "parameters": {},
        "config": {},
        "metadata": {},
    }


def run_component(request: RequestEnvelope | None = None) -> ResultEnvelope:
    """Run the placeholder component through the generated-code result envelope."""
    payload = build_demo_request() if request is None else dict(request)
    inputs = payload.get("inputs")
    data = inputs.get("data") if isinstance(inputs, dict) else [3, 1, 2]
    if isinstance(data, list):
        int_data = [item for item in data if isinstance(item, int)]
    else:
        int_data = [3, 1, 2]
    result = solve(int_data)
    return {
        "outputs": result,
        "metrics": {"count": float(len(result))},
        "artifacts": {"component": "solve"},
        "diagnostics": {"status": "ok", "placeholder": True},
    }


def main() -> int:
    """Run the placeholder demo and print a JSON result envelope."""
    print(json.dumps(run_component(), sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
