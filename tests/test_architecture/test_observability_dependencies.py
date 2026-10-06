import ast
from pathlib import Path


def test_monitoring_contracts_and_service_do_not_import_technical_adapters() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "app/application/models/observability.py",
        "app/application/ports/observability.py",
        "app/services/monitoring_service.py",
    ):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(
                name.startswith(
                    (
                        "app.infrastructure",
                        "app.api",
                        "langchain",
                        "langgraph",
                        "fastapi",
                    )
                )
                for name in names
            ), relative
