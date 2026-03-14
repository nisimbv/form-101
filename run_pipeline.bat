@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  Form 101 Automation Pipeline
REM  Usage:
REM    run_pipeline.bat               → full pipeline (deploy+test+verify+make)
REM    run_pipeline.bat --no-deploy   → skip clasp push/deploy
REM    run_pipeline.bat --verify-only → verify only (needs prior state file)
REM    run_pipeline.bat --visible     → show browser window during test
REM    run_pipeline.bat --no-make     → skip Make webhook verification
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"
python -m scripts.pipeline %*
