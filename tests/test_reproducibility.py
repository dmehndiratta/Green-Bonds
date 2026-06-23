"""Determinism: the synthetic data and the NSS fit are seed-stable, and the
embedded greenium signal is recovered with the right sign and term-structure shape.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from nss import fit_nss, curve_value

ROOT = Path(__file__).resolve().parents[1]


def _load_demo():
    spec = importlib.util.spec_from_file_location(
        "demo", ROOT / "pipeline" / "01_fetch" / "make_demo_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cfg():
    import yaml
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def test_demo_is_deterministic():
    demo = _load_demo()
    a = demo.build(20260615, _cfg())[0]
    b = demo.build(20260615, _cfg())[0]
    pd.testing.assert_frame_equal(a, b)


def test_demo_changes_with_seed():
    demo = _load_demo()
    a = demo.build(1, _cfg())[0]
    b = demo.build(2, _cfg())[0]
    assert not a.equals(b)


def test_embedded_greenium_is_positive_and_downward_sloping():
    """Sanity on the synthetic signal: short-tenor greenium exceeds long-tenor."""
    demo = _load_demo()
    short = demo.greenium_bp(3.0, 0.0)
    long = demo.greenium_bp(30.0, 0.0)
    assert short > long > 0


def test_nss_fit_is_stable():
    rng = np.random.default_rng(0)
    tau = np.array([1, 2, 3, 5, 7, 10, 15, 20, 30], float)
    y = 2.0 + 0.8 * (1 - np.exp(-tau / 6.0)) + rng.standard_normal(len(tau)) * 0.01
    f1 = fit_nss(tau, y)
    f2 = fit_nss(tau, y)
    assert abs(curve_value(f1, 10.0) - curve_value(f2, 10.0)) < 1e-6
    assert f1["rmse"] < 0.05  # fits the smooth curve tightly
