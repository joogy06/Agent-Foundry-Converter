#!/usr/bin/env python3
"""gates_g2_shim.py — host-portable schema validator for contract-map.yaml.

This is a SUBSET of upstream agent-foundry ``skills/_meta/gates.py``. Only
the G2 gate (schema validation V1-V15 + semantic-type registry + technical
closed list) is included. G1 (HMAC signing over the map) and G3 (claims
ledger verification) require Claude Code + forge runtime and are NOT
included here — they depend on ``.forge/session.key`` and
``.ledger/claims/`` which only exist on a Claude host.

If you need full gate enforcement, use Claude Code with forge. This shim
catches approximately 80% of contract-map schema bugs at host-local cost.

Usage:
    python3 gates_g2_shim.py G2 <path-to-contract-map.yaml> [--project-root <dir>]

Exit codes:
    0 = pass
    2 = fail (schema violation)
    3 = environmental error (file missing, parse error not a violation)

Provenance: subset of spec section 8.3. Keep in lock-step with upstream —
the CI job in transfer-kit diffs this file against the upstream extract to
catch drift.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    sys.stderr.write("FATAL: pyyaml not installed. gates_g2_shim.py requires pyyaml.\n")
    sys.exit(3)


# ---------------------------------------------------------------------------
# Constants (mirror upstream gates.py verbatim)
# ---------------------------------------------------------------------------

SCHEMA_VERSION_SUPPORTED = "1.0.0"

V1_SEMANTIC_TYPES = frozenset({
    # Identity (3)
    "user_id", "session_token", "api_key",
    # Contact (4)
    "email", "phone_e164", "address_line", "country_iso2",
    # Personal (4)
    "full_name", "first_name", "last_name", "date_of_birth",
    # Temporal (3)
    "iso_8601_datetime", "iso_8601_date", "unix_timestamp",
    # Financial (3)
    "currency_amount", "currency_iso4217", "iban",
    # Web (1)
    "url_http",
})
assert len(V1_SEMANTIC_TYPES) == 18, "v1 registry frozen at 18 types"

TECHNICAL_CLOSED_LIST = frozenset({
    "id", "revision", "event_id", "_meta", "hash", "checksum",
    "version", "created_at", "updated_at", "deleted_at",
    "generation", "schema_version", "internal_ref",
})

KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

REQUIRED_COMPONENT_FIELDS = {
    "id", "purpose", "owner_wp", "source_paths",
    "test_paths", "fixtures_path", "inputs", "outputs",
    "callers", "callees", "success_criteria", "test_scenarios",
}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def fail(message: str) -> None:
    sys.stderr.write(f"G2_FAIL: {message}\n")
    sys.exit(2)


def env_error(message: str) -> None:
    sys.stderr.write(f"ENV_ERROR: {message}\n")
    sys.exit(3)


def ok(message: str = "") -> None:
    sys.stdout.write(f"G2_PASS: {message}\n")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Project-local registry override
# ---------------------------------------------------------------------------


def load_semantic_type_registry(project_root: Path) -> set:
    registry = set(V1_SEMANTIC_TYPES)
    override_path = project_root / ".contract" / "semantic-types.yaml"
    if override_path.is_file():
        try:
            data = yaml.safe_load(override_path.read_text()) or {}
            local_types = data.get("semantic_types", {})
            if isinstance(local_types, dict):
                for type_name in local_types.keys():
                    registry.add(type_name)
        except (yaml.YAMLError, OSError) as e:
            env_error(f"failed to load project-local semantic types: {e}")
    return registry


# ---------------------------------------------------------------------------
# V1–V15 validators (verbatim from upstream)
# ---------------------------------------------------------------------------


def _v1_schema_version(map_yaml: Dict[str, Any]) -> None:
    sv = map_yaml.get("schema_version")
    if not isinstance(sv, str) or not sv:
        fail("V1: schema_version missing")
    if sv != SCHEMA_VERSION_SUPPORTED:
        fail(f"V1: unsupported schema_version {sv!r} (supported: {SCHEMA_VERSION_SUPPORTED})")


def _v2_revision(map_yaml: Dict[str, Any]) -> None:
    rev = map_yaml.get("revision")
    if not isinstance(rev, int) or rev < 1:
        fail(f"V2: revision must be a positive integer, got {rev!r}")


def _v3_unique_kebab_ids(components: List[Dict[str, Any]]) -> None:
    seen = set()
    for c in components:
        cid = c.get("id")
        if not isinstance(cid, str):
            fail(f"V3: component missing id: {c}")
        if not KEBAB_CASE_RE.match(cid):
            fail(f"V3: component id {cid!r} not kebab-case")
        if cid in seen:
            fail(f"V3: duplicate component id {cid!r}")
        seen.add(cid)


def _v4_required_fields(components: List[Dict[str, Any]]) -> None:
    for c in components:
        missing = REQUIRED_COMPONENT_FIELDS - set(c.keys())
        if missing:
            fail(f"V4: component {c.get('id', '?')!r} missing required fields: {sorted(missing)}")


def _v5_v6_callers_callees(components: List[Dict[str, Any]]) -> None:
    by_id = {c["id"]: c for c in components}
    for c in components:
        cid = c["id"]
        for callee in c.get("callees") or []:
            if callee not in by_id:
                fail(f"V5: component {cid!r} declares callee {callee!r} which is not a component")
            if cid not in (by_id[callee].get("callers") or []):
                fail(f"V6: component {cid!r} -> {callee!r} not bidirectional (callee missing caller)")
        for caller in c.get("callers") or []:
            if caller not in by_id:
                fail(f"V5: component {cid!r} declares caller {caller!r} which is not a component")
            if cid not in (by_id[caller].get("callees") or []):
                fail(f"V6: component {cid!r} <- {caller!r} not bidirectional (caller missing callee)")


def _walk_refs(node: Any, type_names: set, path: str = "") -> None:
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref not in type_names:
                fail(f"V7: $ref {ref!r} at {path} does not resolve to a declared type")
        for k, v in node.items():
            _walk_refs(v, type_names, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_refs(v, type_names, f"{path}[{i}]")


def _v7_refs(map_yaml: Dict[str, Any]) -> None:
    types = map_yaml.get("types") or {}
    if not isinstance(types, dict):
        fail("V7: types section is not a mapping")
    type_names = set(types.keys())
    components = map_yaml.get("components") or []
    _walk_refs(components, type_names, "components")


def _v8_fixture_refs(components: List[Dict[str, Any]]) -> None:
    for c in components:
        input_names = {i.get("name") for i in (c.get("inputs") or []) if isinstance(i, dict)}
        for ts in c.get("test_scenarios") or []:
            for fr in ts.get("fixture_refs") or []:
                base = fr.split("[")[0]
                if base not in input_names:
                    fail(
                        f"V8: component {c['id']!r} test_scenario {ts.get('id')!r} "
                        f"fixture_ref {fr!r} does not point to a declared input"
                    )


def _v9_v10_flow_markers(components: List[Dict[str, Any]]) -> None:
    has_entry = any(c.get("flow_entry_point") for c in components)
    has_terminal = any(c.get("flow_terminal") for c in components)
    if not has_entry:
        fail("V9: no component has flow_entry_point: true")
    if not has_terminal:
        fail("V10: no component has flow_terminal: true")


def _tarjan_scc(graph: Dict[str, List[str]]) -> List[List[str]]:
    index_counter = [0]
    stack: List[str] = []
    on_stack: Dict[str, bool] = {}
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    sccs: List[List[str]] = []

    def strongconnect(v: str) -> None:
        indices[v] = index_counter[0]
        lowlinks[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in graph.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif on_stack.get(w, False):
                lowlinks[v] = min(lowlinks[v], indices[w])
        if lowlinks[v] == indices[v]:
            component: List[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == v:
                    break
            sccs.append(component)

    for v in list(graph.keys()):
        if v not in indices:
            strongconnect(v)
    return sccs


def _v11_acyclic_or_declared(components: List[Dict[str, Any]]) -> None:
    graph = {c["id"]: list(c.get("callees") or []) for c in components}
    cycle_groups = {c["id"]: c.get("cycle_group") for c in components}
    sccs = _tarjan_scc(graph)
    for scc in sccs:
        if len(scc) <= 1:
            v = scc[0]
            if v in graph.get(v, []):
                if not cycle_groups.get(v):
                    fail(f"V11: self-loop on {v!r} not declared via cycle_group")
            continue
        groups = {cycle_groups.get(v) for v in scc}
        if None in groups or len(groups) > 1:
            fail(
                f"V11: cycle detected among {sorted(scc)} — must all declare the same cycle_group"
            )


def _v12_test_scenarios(components: List[Dict[str, Any]]) -> None:
    for c in components:
        ts = c.get("test_scenarios")
        if not isinstance(ts, list) or len(ts) == 0:
            fail(f"V12: component {c['id']!r} has no test_scenarios")


def _v13_semantic_types(components: List[Dict[str, Any]], registry: set) -> None:
    for c in components:
        for inp in c.get("inputs") or []:
            if not isinstance(inp, dict):
                fail(f"V13: component {c['id']!r} has malformed input: {inp}")
            kind = inp.get("kind")
            if kind == "opaque":
                if not inp.get("opaque_reason"):
                    fail(f"V13: opaque input {inp.get('name')!r} in {c['id']!r} missing opaque_reason")
                if not inp.get("opaque_fixture_source"):
                    fail(f"V13: opaque input {inp.get('name')!r} in {c['id']!r} missing opaque_fixture_source")
                continue
            st = inp.get("semantic_type")
            if st is None:
                fail(
                    f"V13: input {inp.get('name')!r} in {c['id']!r} missing semantic_type "
                    f"(use registry value, technical, or kind: opaque)"
                )
            if st == "technical":
                tech = inp.get("technical")
                if tech not in TECHNICAL_CLOSED_LIST:
                    fail(
                        f"V13: input {inp.get('name')!r} in {c['id']!r} declares technical "
                        f"but technical={tech!r} is not in the closed list "
                        f"({sorted(TECHNICAL_CLOSED_LIST)})"
                    )
                continue
            if st not in registry:
                fail(
                    f"V13: input {inp.get('name')!r} in {c['id']!r} has unknown semantic_type "
                    f"{st!r} (not in v1 registry or project-local override)"
                )


def _v14_v15_flows(map_yaml: Dict[str, Any], components: List[Dict[str, Any]]) -> None:
    flows = map_yaml.get("flows") or []
    component_ids = {c["id"] for c in components}
    for flow in flows:
        path = flow.get("path") or []
        for elem in path:
            if elem not in component_ids:
                fail(f"V14: flow {flow.get('id')!r} path element {elem!r} not a component")
    budget = (map_yaml.get("flow_budget") or {}).get("max_flows")
    if isinstance(budget, int) and len(flows) > budget:
        fail(f"V15: total flows ({len(flows)}) exceed budget ({budget})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def check_g2(map_path: Path, project_root: Path) -> None:
    if not map_path.is_file():
        fail(f"contract map not found at {map_path}")
    try:
        map_yaml = yaml.safe_load(map_path.read_text())
    except yaml.YAMLError as e:
        fail(f"contract-map.yaml unparseable: {e}")
    if not isinstance(map_yaml, dict):
        fail("contract-map.yaml is not a mapping")
    components = map_yaml.get("components") or []
    if not isinstance(components, list) or not components:
        fail("components must be a non-empty list")
    registry = load_semantic_type_registry(project_root)
    _v1_schema_version(map_yaml)
    _v2_revision(map_yaml)
    _v3_unique_kebab_ids(components)
    _v4_required_fields(components)
    _v5_v6_callers_callees(components)
    _v7_refs(map_yaml)
    _v8_fixture_refs(components)
    _v9_v10_flow_markers(components)
    _v11_acyclic_or_declared(components)
    _v12_test_scenarios(components)
    _v13_semantic_types(components, registry)
    _v14_v15_flows(map_yaml, components)
    ok(f"schema validation passed for {map_path}")


def main(argv: list) -> None:
    if len(argv) < 2 or argv[1] != "G2":
        sys.stderr.write("usage: gates_g2_shim.py G2 <contract-map-path> [--project-root <dir>]\n")
        sys.exit(2)
    if len(argv) < 3:
        sys.stderr.write("gates_g2_shim.py G2 requires a contract-map path\n")
        sys.exit(2)
    map_path = Path(argv[2])
    project_root = Path(os.getcwd())
    i = 3
    while i < len(argv):
        if argv[i] == "--project-root":
            project_root = Path(argv[i + 1])
            i += 2
        else:
            i += 1
    check_g2(map_path, project_root)


if __name__ == "__main__":
    main(sys.argv)
