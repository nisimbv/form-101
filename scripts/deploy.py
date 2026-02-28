"""
Push updated src/ files to Google Apps Script and bump the deployment.

Usage:
    python -m scripts.deploy
    python -m scripts.deploy --push-only   # skip deploy (keep old version active)
"""
import subprocess, sys, os

PROJECT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_DEP_ID    = "AKfycbzw4Pq6XiaaO2U7ZGrIWySljXhpyQIbKAnTppSNRHIQFVsAQZ9ddQJnbMK8y7z0fXfs"


def _run(cmd: str) -> str:
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_DIR
    )
    out = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(f"Command failed:\n  $ {cmd}\n  {out}")
    return out


def push() -> None:
    print("  → clasp push …")
    out = _run("clasp push --force")
    print(f"    {out}")


def deploy_new_version() -> None:
    print("  → clasp deploy (new version) …")
    out = _run(
        f'clasp deploy --deploymentId {PROD_DEP_ID} --description "auto-deploy"'
    )
    print(f"    {out}")


def run(push_only: bool = False) -> None:
    print("\n[DEPLOY]")
    push()
    if not push_only:
        deploy_new_version()
    print("  ✅ Deploy done.")


if __name__ == "__main__":
    run(push_only="--push-only" in sys.argv)
