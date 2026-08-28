"""
tests/test_sterile_env.py
Adversarial TDD Acceptance Suite for Canonical Sterile Environment Engine.
Verifies that all host secrets, user-site packages, and dirty variables are stripped
prior to any subprocess invocation in 10 SHADOWS.
"""

import os
from pathlib import Path
import pytest

from loop_engine.sterile_env import (
    ALLOWED_ENV_VARS,
    SECRET_PATTERN,
    build_sterile_environment,
    is_secret_env_var,
)


class TestSterileEnvironmentAllowlist:
    def test_sterile_env_contains_only_allowlisted_and_runtime_flags(self):
        env = build_sterile_environment()
        
        allowed_set = set(ALLOWED_ENV_VARS) | {
            "PYTHONPATH",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
            "PYTHONUNBUFFERED",
        }
        # Windows case-insensitivity check
        for k in env.keys():
            assert k.upper() in {a.upper() for a in allowed_set}

    def test_sterile_env_isolation_flags(self):
        env = build_sterile_environment()
        assert env.get("PYTHONNOUSERSITE") == "1"
        assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
        assert env.get("PYTHONUNBUFFERED") == "1"


class TestSterileEnvironmentSecretScrubbing:
    def test_is_secret_env_var_detection(self):
        assert is_secret_env_var("OPENAI_API_KEY") is True
        assert is_secret_env_var("GITHUB_TOKEN") is True
        assert is_secret_env_var("AWS_SECRET_ACCESS_KEY") is True
        assert is_secret_env_var("DB_PASSWORD") is True
        assert is_secret_env_var("AUTH_BEARER") is True
        assert is_secret_env_var("CLIENT_CREDENTIALS") is True
        assert is_secret_env_var("SSL_CERT_KEY") is True
        assert is_secret_env_var("PATH") is False
        assert is_secret_env_var("SYSTEMROOT") is False

    def test_sterile_env_strips_active_host_secrets(self, monkeypatch):
        # Inject adversarial host secrets into os.environ
        monkeypatch.setenv("TEST_API_KEY", "sk-secret-12345")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake_token")
        monkeypatch.setenv("DATABASE_PASSWORD", "super_secret_pw")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_secret")
        monkeypatch.setenv("MY_PRIVATE_CERT", "cert_payload")

        env = build_sterile_environment()

        assert "TEST_API_KEY" not in env
        assert "GITHUB_TOKEN" not in env
        assert "DATABASE_PASSWORD" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "MY_PRIVATE_CERT" not in env


class TestSterileEnvironmentAnchoring:
    def test_pythonpath_anchoring_to_worktree(self, tmp_path: Path):
        worktree = tmp_path / "custom_worktree"
        worktree.mkdir()
        
        env = build_sterile_environment(worktree_path=worktree)
        assert env.get("PYTHONPATH") == str(worktree.resolve())
