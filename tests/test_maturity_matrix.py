"""The maturity test matrix (evaluations/maturity-test-matrix.md) cannot go stale, and the companion layers make no
model call. Neither test needs a database or a model."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "evaluations" / "maturity-test-matrix.md"
PACKAGE = ROOT / "src" / "membrain"
REFERENCE = re.compile(r"`tests/(test_\w+\.py)::(test_\w+)`")

# The companion layers (Phase C). Add P2's module here when it is merged.
LAYERS = ("affect", "mood", "persona", "persona_growth", "persona_presets", "relationship", "memory_map",
          "companion_map")
# Anything that can reach a model or the network, outside or inside the package.
NETWORK = {"httpx", "requests", "aiohttp", "urllib", "http", "socket", "openai", "anthropic"}
MODEL_MODULES = {"extraction", "semantic", "semantic_provider", "chat_provider", "recall_provider",
                 "answer_review_provider", "embeddings", "local_embeddings", "local_semantics", "cognition",
                 "reasoning", "learning", "outbound", "client", "runtime_client"}


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")}


def test_every_test_the_matrix_names_exists():
    references = REFERENCE.findall(MATRIX.read_text(encoding="utf-8"))
    assert len(references) >= 100, "the matrix should reference the local tests it relies on"
    names, missing = {}, []
    for file, name in sorted(set(references)):
        path = ROOT / "tests" / file
        if not path.is_file():
            missing.append(f"tests/{file} (no such file)")
            continue
        if file not in names:
            names[file] = _test_names(path)
        if name not in names[file]:
            missing.append(f"tests/{file}::{name}")
    assert missing == [], "the matrix names tests that do not exist:\n" + "\n".join(missing)


def _imports(module: str) -> tuple[set[str], set[str]]:
    """Every in-package module the given module reaches through imports (including imports inside functions), and
    every top-level outside package those modules import."""
    inside, outside, pending = set(), set(), [module]
    while pending:
        name = pending.pop()
        if name in inside:
            continue
        inside.add(name)
        path = PACKAGE / f"{name}.py"
        if not path.is_file():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    pending.extend([node.module.split(".")[0]] if node.module else [a.name for a in node.names])
                elif node.module and node.module.split(".")[0] == "membrain":
                    parts = node.module.split(".")
                    pending.extend([parts[1]] if len(parts) > 1 else [a.name for a in node.names])
                elif node.module:
                    outside.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == "membrain" and len(parts) > 1:
                        pending.append(parts[1])
                    else:
                        outside.add(parts[0])
    return inside, outside


def test_companion_layers_import_no_model_or_network_client():
    for layer in LAYERS:
        assert (PACKAGE / f"{layer}.py").is_file(), layer
        inside, outside = _imports(layer)
        assert not inside & MODEL_MODULES, (layer, sorted(inside & MODEL_MODULES))
        assert not outside & NETWORK, (layer, sorted(outside & NETWORK))
