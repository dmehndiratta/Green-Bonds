"""Green-Bond-Greenium pipeline orchestrator.

Stages:
  1  fetch     Bundesbank green/conventional twin yields; demo-synthetic fallback
  2  clean     align twins, harmonise conventions, liquidity vars, entry dates
  3  analysis  twin spread, FE panel (liquidity-adjusted), dynamics, refutation
  4  export    assemble site/data/*.json

Flags:
  --offline       rebuild from last-good cache / committed artefacts (no network)
  --export-only   run only stage 4
  --stage N       run a single stage (1..4)
  --demo          force the synthetic data (skip live fetch)

Examples:
  python run_pipeline.py
  python run_pipeline.py --offline
  python run_pipeline.py --stage 3
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPE = ROOT / "pipeline"
sys.path.insert(0, str(PIPE))


def _run(rel: str, **kwargs):
    path = PIPE / rel
    name = rel.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    print(f"\n>>> {rel}")
    spec.loader.exec_module(mod)
    mod.main(**kwargs)


def stage_fetch(offline: bool, demo: bool):
    if demo:
        _run("01_fetch/make_demo_data.py")
        return
    _run("01_fetch/fetch_bundesbank.py", offline=offline)
    # Fall back to synthetic data if the live German fetch produced nothing.
    latest = ROOT / "data" / "raw" / "bundesbank" / "bundesbank_yields_latest.csv"
    if not latest.exists():
        print("\n[fallback] live Bundesbank panel empty -> generating synthetic demo data")
        _run("01_fetch/make_demo_data.py")


def stage_clean(offline: bool):
    _run("02_clean/build_pairs_panel.py", offline=offline)


def stage_analysis(offline: bool):
    _run("03_analysis/twin_spread.py", offline=offline)
    _run("03_analysis/panel_greenium.py", offline=offline)
    _run("03_analysis/dynamics.py", offline=offline)
    _run("03_analysis/refutation.py", offline=offline)


def stage_export(offline: bool):
    _run("04_export/export_json.py", offline=offline)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--stage", type=int, choices=[1, 2, 3, 4])
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.export_only:
        stage_export(args.offline)
        return
    if args.stage:
        {1: lambda: stage_fetch(args.offline, args.demo),
         2: lambda: stage_clean(args.offline),
         3: lambda: stage_analysis(args.offline),
         4: lambda: stage_export(args.offline)}[args.stage]()
        return

    stage_fetch(args.offline, args.demo)
    stage_clean(args.offline)
    stage_analysis(args.offline)
    stage_export(args.offline)
    print("\nPipeline complete. See site/data/*.json and site/dashboard.html")


if __name__ == "__main__":
    main()
