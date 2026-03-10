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


def sync_template() -> None:
    """Copy PDFTemplate_v6.html → src/PDFTemplate.html before pushing."""
    import shutil
    src = os.path.join(PROJECT_DIR, "PDFTemplate_v6.html")
    dst = os.path.join(PROJECT_DIR, "src", "PDFTemplate.html")
    shutil.copy2(src, dst)
    print(f"  → Synced PDFTemplate_v6.html → src/PDFTemplate.html")


def validate_mapping() -> None:
    """Run pre-deploy mapping validation (build-breaking checks)."""
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "validate_mapping",
        pathlib.Path(PROJECT_DIR) / "scripts" / "validate_mapping.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()
    if rc != 0:
        raise RuntimeError("Pre-deploy validation FAILED — aborting deploy. Run: python -m scripts.validate_mapping")


def run(push_only: bool = False, skip_validate: bool = False) -> None:
    print("\n[DEPLOY]")
    if not skip_validate:
        validate_mapping()
    sync_template()
    push()
    if not push_only:
        deploy_new_version()
    print("  ✅ Deploy done.")


if __name__ == "__main__":
    run(push_only="--push-only" in sys.argv,
        skip_validate="--skip-validate" in sys.argv)
