"""Publish an explicit source allowlist to the zero-GPU Hugging Face Space.

Install deployment tooling separately: pip install huggingface_hub
Authentication is read from the existing Hugging Face credential store.
This script never uploads .env, runtime databases, credentials, or recordings.
"""
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parents[1]
REPO = "Jemsbhai/releaseproof"
api = HfApi()
api.create_repo(REPO, repo_type="space", space_sdk="docker", space_hardware="cpu-basic", private=False, exist_ok=True)
paths = [ROOT / name for name in ("Dockerfile", "requirements.txt", "requirements.lock", "LICENSE")]
for folder in ("releaseproof", "data", "web"):
    paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
readme = """---
title: ReleaseProof
emoji: \U0001f9ed
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Evidence-bound releases for budgeted Nemotron agents
---

# ReleaseProof

Qualify an issue-triage agent, approve the exact tested configuration, and hold future actions when its contract or observed behavior changes.

Start with the labelled fixture mode. Live NVIDIA Nemotron inference runs through Nebius Token Factory when enabled. Every visitor gets an isolated demo board. Export evidence before leaving; demo sessions may reset when this free host restarts. The shared live spending ledger survives restarts separately.

Source and setup: https://github.com/jemsbhai/releaseproof

No real issues, messages, or external project resources are changed. Synthetic cases and injected faults are labelled explicitly.
""".encode("utf-8")
operations = [CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=readme)]
operations += [CommitOperationAdd(path_in_repo=str(p.relative_to(ROOT)).replace("\\", "/"), path_or_fileobj=p) for p in paths]
result = api.create_commit(REPO, repo_type="space", operations=operations, commit_message="Deploy verified ReleaseProof application")
print(f"Published {len(paths)} source files: {result.commit_url}")
