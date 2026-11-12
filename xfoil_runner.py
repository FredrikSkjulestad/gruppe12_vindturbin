"""Shared XFOIL functions: airfoil geometry, batch runs with timeout, polar cache.

XFOIL is driven through a batch input file piped to stdin. Each call runs in its own
short-named work folder (XFOIL has short filename buffers, Windows paths can be long).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ geometry
def read_coords(path: Path) -> tuple[str, np.ndarray]:
    """Read a Selig or Lednicer .dat file. Returns (name, Nx2 array TE->upper->LE->lower->TE)."""
    lines = Path(path).read_text(errors="ignore").splitlines()
    name = lines[0].strip() if lines else Path(path).stem
    pts = []
    for line in lines:
        p = line.replace(",", " ").split()
        if len(p) == 2:                      # coordinate rows only (skips header / plot-range rows)
            try:
                pts.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    pts = np.array(pts)
    if len(pts) and pts[0, 0] > 1.5 and pts[0, 1] > 1.5:   # Lednicer: first row = point counts
        nu, nl = int(pts[0, 0]), int(pts[0, 1])
        up, lo = pts[1:1 + nu], pts[1 + nu:1 + nu + nl]
        pts = np.vstack([up[::-1], lo[1:]])
    return name, pts


def normalise(pts: np.ndarray) -> np.ndarray:
    """Scale/shift to unit chord with the leading edge (min x) at the origin."""
    ile = int(np.argmin(pts[:, 0]))
    c = pts[:, 0].max() - pts[:, 0].min()
    return (pts - [pts[ile, 0], pts[ile, 1]]) / c


def thickness(pts: np.ndarray) -> dict:
    """Max t/c (vertical distance between surfaces on a common x grid, XFOIL definition) and camber."""
    p = normalise(pts)
    ile = int(np.argmin(p[:, 0]))
    up, lo = p[:ile + 1][::-1], p[ile:]
    xs = (1 - np.cos(np.linspace(0, np.pi, 401))) / 2
    yu = np.interp(xs, *np.array(sorted(map(tuple, up))).T)
    yl = np.interp(xs, *np.array(sorted(map(tuple, lo))).T)
    th = yu - yl
    i = int(np.argmax(th))
    return {"tc": float(th[i]), "x_tc": float(xs[i]), "camber": float(((yu + yl) / 2).max())}


def write_clean_dat(src: Path, dst: Path, name: str | None = None) -> Path:
    """Write a clean Selig file (name line + unit-chord coordinates). Readable by XFOIL and QBlade."""
    nm, pts = read_coords(src)
    p = normalise(pts)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", newline="\n", encoding="utf-8") as f:
        f.write(f"{name or Path(src).stem}\n")
        for x, y in p:
            f.write(f"{x:10.6f} {y:10.6f}\n")
    return dst


# ------------------------------------------------------------------ XFOIL
def _batch(dat: str, re: float, ncrit: float, it: int, npan: int, a0: float, a1: float, da: float, pol: str) -> str:
    return "\n".join([
        "PLOP", "G F", "",                    # graphics off (no window on Windows)
        f"LOAD {dat}",
        "PPAR", f"N {npan}", "", "",          # repanel with npan nodes
        "OPER",
        f"VISC {re:.0f}",
        "VPAR", f"N {ncrit}", "",
        f"ITER {it}",
        "PACC", pol, "",
        f"ASEQ {a0} {a1} {da}",
        "PACC", "",
        "QUIT", ""])


def _read_pol(path: Path) -> pd.DataFrame:
    rows = []
    if path.exists():
        started = False
        for line in path.read_text(errors="ignore").splitlines():
            if line.strip().startswith("------"):
                started = True
                continue
            if started:
                p = line.split()
                if len(p) >= 5:
                    try:
                        rows.append([float(v) for v in p[:5]])
                    except ValueError:
                        pass
    return pd.DataFrame(rows, columns=["alpha", "CL", "CD", "CDp", "CM"])


def run_xfoil_polar(xfoil: str, dat: Path, re: float, s: dict) -> pd.DataFrame:
    """One Re: sweep 0 -> alpha_max, then (fresh boundary layer) 0 -> alpha_min.
    With xfoil.retry_half_step, a sweep that stops more than 1 deg short is redone with half the step.
    Each sweep is its own XFOIL call with a timeout, so one hanging case cannot stop the run.
    Non-converged angles are simply absent from the output (XFOIL skips them)."""
    frames = []
    with tempfile.TemporaryDirectory(prefix="xf") as tmp:
        tmp = Path(tmp)
        shutil.copy(dat, tmp / "af.dat")
        def sweep(pol, a0, a1, da):
            inp = _batch("af.dat", re, s["ncrit"], s["iter"], s["n_panels"], a0, a1, da, pol)
            try:
                subprocess.run([xfoil], input=inp, text=True, capture_output=True,
                               cwd=tmp, timeout=s["timeout_s"])
            except subprocess.TimeoutExpired:
                pass                                   # keep the points written before the hang
            return _read_pol(tmp / pol)

        for tag, a0, a1, da in [("up", 0.0, s["alpha_max"], s["alpha_step"]),
                                ("dn", -s["alpha_step"], s["alpha_min"], -s["alpha_step"])]:
            df = sweep(f"{tag}.pol", a0, a1, da)
            reached = (df.alpha.abs().max() if len(df) else 0.0)
            if s.get("retry_half_step") and reached < abs(a1) - 1.0 - 1e-9:
                # the sweep stopped early (XFOIL hang or crash): redo it with half the step, which
                # gives a better start for each new angle, and keep only the points on the original grid
                r2 = sweep(f"{tag}2.pol", a0, a1, da / 2)
                r2 = r2[np.isclose((r2.alpha / s["alpha_step"]) % 1.0, 0) | np.isclose((r2.alpha / s["alpha_step"]) % 1.0, 1)]
                if len(r2) > len(df):
                    df = r2
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df
    df = df[(df.CD > 0)].drop_duplicates("alpha").sort_values("alpha").reset_index(drop=True)
    return df


def settings_hash(dat: Path, s: dict) -> str:
    keys = ["ncrit", "alpha_min", "alpha_max", "alpha_step", "iter", "n_panels"]
    if s.get("retry_half_step"):                   # only in the hash when switched on, so older caches stay valid
        keys.append("retry_half_step")
    blob = json.dumps({k: s[k] for k in keys}, sort_keys=True) + Path(dat).read_text()
    return hashlib.md5(blob.encode()).hexdigest()[:10]


def cached_polar(xfoil: str, dat: Path, airfoil: str, re: float, s: dict, cache: Path) -> tuple[pd.DataFrame, bool]:
    """Return (polar, from_cache). A polar is only recomputed if the settings or coordinates change."""
    f = cache / "polars" / airfoil / f"Re{int(re):06d}_{settings_hash(dat, s)}.csv"
    if f.exists():
        return pd.read_csv(f), True
    df = run_xfoil_polar(xfoil, dat, re, s)
    f.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(f, index=False)
    return df, False
