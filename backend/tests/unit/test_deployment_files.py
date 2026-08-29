from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_container_files_use_existing_entrypoint_and_persistent_path():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "uv sync --frozen" in dockerfile
    assert '"main:app"' in dockerfile
    assert "RESEARCH_DB_PATH=/data/research.db" in dockerfile
    assert "research-data:/data" in compose
    assert "redis" not in compose.lower()
    assert "postgres" not in compose.lower()
    assert "kafka" not in compose.lower()


def test_dockerignore_excludes_secrets_caches_and_local_state():
    backend_ignore = (ROOT / "backend" / ".dockerignore").read_text(
        encoding="utf-8"
    )
    frontend_ignore = (ROOT / "frontend" / ".dockerignore").read_text(
        encoding="utf-8"
    )

    for pattern in (".venv", "__pycache__", ".pytest_cache", ".env", "*.db"):
        assert pattern in backend_ignore
    for pattern in ("node_modules", "dist", ".env"):
        assert pattern in frontend_ignore
