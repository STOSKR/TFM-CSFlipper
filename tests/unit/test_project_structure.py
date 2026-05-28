from pathlib import Path


def test_project_structure_exists() -> None:
    root = Path(__file__).resolve().parents[2]

    expected_paths = [
        root / "apps" / "agents",
        root / "apps" / "acquisition",
        root / "packages" / "contracts",
        root / "packages" / "domain",
        root / "packages" / "persistence",
        root / "packages" / "vision",
        root / "packages" / "prediction",
        root / "packages" / "decision",
        root / "packages" / "simulation",
        root / "docs" / "architecture.md",
        root / "docs" / "data-model.md",
        root / "docs" / "agent-protocols.md",
        root / "docs" / "ocr-pipeline.md",
        root / "docs" / "simulation-model.md",
        root / "docs" / "tfm-proposal-summary.md",
        root / "backlog" / "en_progreso",
        root / "backlog" / "pendientes",
        root / "backlog" / "realizadas",
    ]

    missing_paths = [path for path in expected_paths if not path.exists()]

    assert missing_paths == []
