#!/usr/bin/env python3
"""Create the project's commits, dated from 10:00 today until now.

    python scripts/backdate_commits.py --dry-run   # preview, changes nothing
    python scripts/backdate_commits.py             # does everything

It removes the empty nested backend/.git, makes the commits, and stops. Commit messages are "<task>:<slug_name>" with nothing else (no trailers, no co-author).
Files are grouped by the patterns in PLAN; each untracked file goes to the first group that
matches it, and anything left over goes into a final catch-all commit. Ignored files are never
added. Each commit contains the files as they are now, not their historical versions.
"""
import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (task, slug_name, [glob patterns relative to the repo root; "*" also matches "/"])
PLAN: list[tuple[str, str, list[str]]] = [
    ("chore", "project-scaffold", [
        "docker-compose.yml", "backend/pyproject.toml", "backend/uv.lock", "backend/.python-version",
        "backend/.gitignore", "backend/.env.example", "backend/README.md", "backend/alembic.ini",
        "frontend/package.json", "frontend/package-lock.json", "frontend/index.html",
        "frontend/vite.config.ts", "frontend/tsconfig*", "frontend/eslint.config.js",
        "frontend/.gitignore", "frontend/.env.example", "frontend/README.md", "frontend/public/*",
        "frontend/src/vite-env.d.ts",
    ]),
    ("feat", "backend-core", [
        "backend/app/__init__.py", "backend/app/main.py", "backend/app/*/__init__.py",
        "backend/app/core/config.py", "backend/app/core/logging.py", "backend/app/core/db.py",
        "backend/app/core/events.py", "backend/app/api/health.py", "backend/app/api/events.py",
        "backend/migrations/env.py", "backend/migrations/script.py.mako", "backend/migrations/README",
        "backend/migrations/versions/0001*", "backend/tests/test_health_events.py",
    ]),
    ("feat", "frontend-shell", [
        "frontend/src/index.css", "frontend/src/main.tsx", "frontend/src/App.tsx",
        "frontend/src/components/AppShell.tsx", "frontend/src/components/StatusPill*",
        "frontend/src/components/PageStub.tsx", "frontend/src/hooks/*", "frontend/src/lib/api.ts",
        "frontend/src/lib/nav.ts", "frontend/src/test/setup.ts",
    ]),
    ("feat", "demo-shop-and-faults", [
        "backend/app/shop/*", "backend/app/models/__init__.py", "backend/app/models/shop.py",
        "backend/app/models/ops.py", "backend/app/core/audit.py", "backend/app/api/faults.py",
        "backend/migrations/versions/0002*", "backend/tests/conftest.py",
        "backend/tests/test_shop_faults.py",
    ]),
    ("feat", "journey-runner-and-detector", [
        "backend/app/journeys/*", "backend/app/detector/*", "backend/app/models/journeys.py",
        "backend/app/api/journeys.py", "backend/app/api/overview.py", "backend/app/api/audit.py",
        "backend/migrations/versions/0003*", "backend/tests/test_detector.py",
        "frontend/src/components/JourneyCard.tsx", "frontend/src/components/Kpi.tsx",
        "frontend/src/components/Sparkline.tsx", "frontend/src/components/Toast*",
        "frontend/src/components/toast-context.ts", "frontend/src/pages/Journeys.tsx",
    ]),
    ("feat", "incident-lifecycle", [
        "backend/app/core/incident_machine.py", "backend/app/models/incidents.py",
        "backend/app/schemas/incidents.py", "backend/app/api/incidents.py",
        "backend/migrations/versions/0004*", "backend/tests/test_incident_model.py",
        "backend/tests/contracts/incident_detail.json", "frontend/src/lib/types.ts",
        "frontend/src/lib/fixtures.ts", "frontend/src/lib/incidentState.ts",
        "frontend/src/components/StageSteps*", "frontend/src/components/TraceList.tsx",
        "frontend/src/components/HypothesisList*", "frontend/src/components/IncidentDetail.tsx",
        "frontend/src/pages/Incidents.tsx", "frontend/src/pages/AuditLog.tsx",
        "frontend/src/test/contract.test.ts",
    ]),
    ("feat", "edge-node-and-firmware", [
        "backend/app/edge/*", "backend/app/schemas/edge.py", "backend/app/api/edge.py",
        "backend/tests/test_edge.py", "backend/tests/test_firmware_message.py",
        "backend/tests/contracts/edge_message.json", "firmware/*", "docs/edge.md",
        "frontend/src/components/TempChart*", "frontend/src/pages/EdgeNode.tsx",
    ]),
    ("feat", "agents-and-tools", [
        "backend/app/agents/*", "backend/app/policy/catalog.*", "backend/migrations/versions/0005*",
        "backend/tests/test_agents.py",
    ]),
    ("feat", "policy-executor-verifier", [
        "backend/app/policy/engine.py", "backend/app/executor/*", "backend/app/verifier/*",
        "backend/app/api/policy.py", "backend/migrations/versions/0006*",
        "backend/tests/test_phase6_loop.py", "frontend/src/components/ApprovalCard*",
        "frontend/src/lib/operator.ts", "frontend/src/pages/Policies.tsx",
    ]),
    ("feat", "scorecard-and-demo-data", [
        "backend/app/harness/scoring.py", "backend/app/harness/__init__.py", "backend/app/api/score.py",
        "backend/app/demo/*", "backend/app/api/demo.py", "backend/tests/test_phase7_score.py",
        "frontend/src/pages/Scorecard.tsx", "frontend/src/pages/Overview.tsx",
        "frontend/src/components/FaultInjector.tsx", "frontend/src/components/ErrorBoundary.tsx",
    ]),
    ("feat", "evaluation-harness", [
        "backend/app/harness/*", "docs/results*", "docs/model-on/*",
    ]),
    ("docs", "project-docs", [
        "README.md", "docs/*", "scripts/*",
    ]),
]
CATCH_ALL = ("chore", "remaining-files")
NEVER = {".env"}  # never committed, whatever the patterns say


def skipped(path: str) -> bool:
    return Path(path).name in NEVER or "__pycache__" in path or path.endswith(".pyc")


def git(*args: str, env: dict[str, str] | None = None, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, env=env, text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout


def untracked() -> list[str]:
    out = git("ls-files", "--others", "--exclude-standard", "-z")
    files = [p for p in out.split("\0") if p]
    nested = ROOT / "backend" / ".git"
    if nested.exists():  # preview only: git reports the nested repo as one "backend/" entry
        files = [p for p in files if p != "backend/"]
        sub = subprocess.run(["git", "-C", str(ROOT / "backend"), "ls-files", "--others",
                              "--exclude-standard", "-z"], text=True, capture_output=True).stdout
        files += [f"backend/{p}" for p in sub.split("\0") if p]
    return sorted(p for p in files if not skipped(p))


def remove_nested_backend_repo(dry_run: bool) -> None:
    """An empty nested repo would make the root treat backend/ as an embedded repo."""
    nested = ROOT / "backend" / ".git"
    if not nested.exists():
        return
    sub = ["git", "-C", str(ROOT / "backend")]
    commits = subprocess.run([*sub, "rev-list", "--all", "-n", "1"], text=True, capture_output=True).stdout.strip()
    remotes = subprocess.run([*sub, "remote"], text=True, capture_output=True).stdout.strip()
    if commits or remotes:
        sys.exit("backend/ has its own git repo with history or a remote; not touching it. "
                 "Move that history yourself, then rerun.")
    if dry_run:
        print("would remove the empty nested repo backend/.git\n")
        return
    print("removing the empty nested repo backend/.git\n")
    shutil.rmtree(nested)


def build_groups(files: list[str]) -> list[tuple[str, str, list[str]]]:
    left = list(files)
    groups = []
    for task, slug, patterns in [*PLAN, (*CATCH_ALL, ["*"])]:
        mine = [f for f in left if any(fnmatch.fnmatch(f, p) for p in patterns)]
        left = [f for f in left if f not in mine]
        if mine:
            groups.append((task, slug, mine))
    return groups


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    args = ap.parse_args()

    end = datetime.now().replace(microsecond=0)
    start = end.replace(hour=10, minute=0, second=0)
    if end <= start:
        sys.exit("it is not past 10:00 yet, so there is no window to spread the commits over")

    if not (ROOT / ".git").exists():
        if args.dry_run:
            print("would run `git init` at the project root\n")
        else:
            git("init", "-b", "main")
    elif subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, capture_output=True).returncode == 0:
        sys.exit("this repo already has commits; the script is for creating the initial history only")
    remove_nested_backend_repo(args.dry_run)

    groups = build_groups(untracked())
    if not groups:
        sys.exit("nothing to commit")
    step = (end - start) / max(1, len(groups) - 1)

    for i, (task, slug, files) in enumerate(groups):
        when = (start + step * i).replace(microsecond=0)
        message = f"{task}:{slug}"
        print(f"{when.isoformat(sep=' ')}  {message:45} {len(files):4} file(s)")
        if args.dry_run:
            continue
        git("add", "--", *files)
        env = {**os.environ, "GIT_AUTHOR_DATE": when.isoformat(), "GIT_COMMITTER_DATE": when.isoformat()}
        git("commit", "-m", message, env=env)
    print("\ndry run only, nothing changed" if args.dry_run else "\ndone")


if __name__ == "__main__":
    main()
