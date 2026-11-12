"""Reproduce the whole blade selection, from the UIUC airfoil database to the final blade.

    Windows: double click reproduce.bat (or: py reproduce.py)
    Linux/Mac: python3 reproduce.py   (needs xfoil on the PATH, or XFOIL_EXE=/path/to/xfoil)

What it does:
  setup  creates .venv, installs the pinned packages (requirements.txt) and, on Windows, downloads
         XFOIL 6.99 from MIT into bin/ (checked against its SHA256)
  1      screening/00_build_list.py   UIUC set (AeroSandbox) -> 676 candidate airfoils
  2      screening/00_screen.py       NeuralFoil + BEM screening at lambda 5.4 -> ranking
  3      screening/plot_screen.py     screening figures
  4      01_polars.py .. 05_plots.py  XFOIL check of the top 5 from step 2 -> final blade
  5      validation/validate_goe227.py  code check against Assignments 3 and 4
  check  compares the result with expected_results.yaml (the numbers in the report)

Options:
  --xfoil-only     only the XFOIL study (step 4), with the screening ranking already in the folder
                   (this is what run_all.bat does)
  --sweep          also rerun the earlier lambda 5.0..6.5 sweep (config_sweep.yaml, results/)
  --sweep-only     only the sweep (this is what run_sweep.bat does)
  --clean-cache    delete the polar caches first, so every polar is computed again
  --no-setup       use the current Python as it is (no venv, no installs)

The virtual environment is .venv in this folder. On Windows, when the folder path is so long that
some package files would pass the 260 character path limit (and long paths are not enabled), it goes
to %LOCALAPPDATA%\\gruppe12_vindturbin\\venv-<id> instead; the script prints which one it uses.
Runtime: about 10 to 15 minutes on a normal laptop, most of it the screening.
"""
from __future__ import annotations

import hashlib
import io
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _long_paths_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
            return winreg.QueryValueEx(k, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


def venv_dir() -> Path:
    if os.environ.get("WIND_BLADE_VENV"):
        return Path(os.environ["WIND_BLADE_VENV"])
    local = ROOT / ".venv"
    # the deepest package file (in AeroSandbox) adds about 150 characters to the venv path
    if os.name == "nt" and len(str(local)) > 100 and not _long_paths_enabled():
        tag = hashlib.md5(str(ROOT).lower().encode()).hexdigest()[:6]
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "gruppe12_vindturbin" / f"venv-{tag}"
    return local


VENV = venv_dir()
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
XFOIL_URL = "https://web.mit.edu/drela/Public/web/xfoil/XFOIL6.99.zip"
XFOIL_SHA256 = "C17342F84AE260C2B11A74CD0E2FB8189A5F8954C6BB7A8467A0F27055C7FAEA"
XFOIL_WIN = ROOT / "bin" / "xfoil.exe"

SCREENING = [
    ("1 candidate list from the UIUC database", ["screening/00_build_list.py"]),
    ("2 NeuralFoil screening at lambda 5.4", ["screening/00_screen.py"]),
    ("3 screening figures", ["screening/plot_screen.py"]),
]
XFOIL_STUDY = [
    ("4a XFOIL polars of the top 5", ["01_polars.py"]),
    ("4b BEM design", ["02_design.py"]),
    ("4c realistic blade and performance", ["03_performance.py"]),
    ("4d report tables and QBlade export", ["04_report.py"]),
    ("4e plots", ["05_plots.py", "--no-show"]),
]
VALIDATION = [("5 code check against Assignments 3 and 4", ["validation/validate_goe227.py"])]
SWEEP = [(f"sweep {s}", [s] + (["--no-show"] if s == "05_plots.py" else []))
         for s in ["01_polars.py", "02_design.py", "03_performance.py", "04_report.py", "05_plots.py"]]


def say(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- setup
def in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def setup_and_restart() -> None:
    if VENV != ROOT / ".venv":
        say(f"The folder path is long, so the virtual environment goes to {VENV}")
    if not VENV_PY.exists():
        say(f"Creating {VENV} with Python {platform.python_version()} ...")
        VENV.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    say("Installing the pinned packages (requirements.txt) ...")
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                    "-r", str(ROOT / "requirements.txt")], check=True)
    sys.exit(subprocess.run([str(VENV_PY), str(Path(__file__).resolve()), "--no-setup", *sys.argv[1:]]).returncode)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def ensure_xfoil(env: dict) -> None:
    if env.get("XFOIL_EXE"):
        say(f"XFOIL: {env['XFOIL_EXE']} (from XFOIL_EXE)")
        return
    if os.name == "nt":
        if not XFOIL_WIN.exists():
            say(f"Downloading XFOIL 6.99 from {XFOIL_URL} ...")
            data = urllib.request.urlopen(XFOIL_URL, timeout=120).read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                member = next(m for m in z.namelist() if m.lower().endswith("xfoil.exe"))
                exe = z.read(member)
            if sha256(exe) != XFOIL_SHA256:
                sys.exit(f"xfoil.exe from {XFOIL_URL} has SHA256 {sha256(exe)}, expected {XFOIL_SHA256}. "
                         f"Stopping, because a different XFOIL can give different results.")
            XFOIL_WIN.parent.mkdir(exist_ok=True)
            XFOIL_WIN.write_bytes(exe)
        h = sha256(XFOIL_WIN.read_bytes())
        say(f"XFOIL: {XFOIL_WIN.relative_to(ROOT)}  SHA256 {'OK' if h == XFOIL_SHA256 else 'DIFFERENT: ' + h}")
    else:
        exe = shutil.which("xfoil")
        if not exe:
            sys.exit("XFOIL not found. Install XFOIL 6.99 and put it on the PATH, or set XFOIL_EXE=/path/to/xfoil.")
        env["XFOIL_EXE"] = exe
        say(f"XFOIL: {exe}  (not the Windows build used for the report: expect small differences, "
            f"about 0.001 in Cp)")


# ---------------------------------------------------------------- run
def run(steps, env) -> None:
    for title, cmd in steps:
        say(f"\n===== {title}: {' '.join(cmd)}")
        t0 = time.time()
        r = subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env)
        if r.returncode:
            sys.exit(f"\nStep '{title}' failed (exit code {r.returncode}). See the output above.")
        say(f"----- done in {time.time() - t0:.0f} s")


# ---------------------------------------------------------------- check
def current_results() -> dict:
    import pandas as pd
    sys.path.insert(0, str(ROOT / "screening"))
    from parse_list import read_list
    cand = read_list(ROOT / "screening/results/candidates_uiuc.txt")
    ref = read_list(ROOT / "screening/reference/foil_list_676.txt")
    scr = pd.read_csv(ROOT / "screening/results/screen_ranking.csv").sort_values("rank")
    perf = pd.read_csv(ROOT / "results_lambda54/03_performance_summary.csv")
    ok = perf[perf.constraints_ok].sort_values("rank")
    best = ok.drop_duplicates("airfoil")
    w = ok.iloc[0]
    return {
        "candidates": len(cand),
        "candidates_same_as_original_list": bool(set(cand.name) == set(ref.name)
                                                  and (cand.set_index("name").tc.sort_index()
                                                       == ref.set_index("name").tc.sort_index()).all()),
        "screening_top5": [str(a) for a in scr.airfoil.head(5)],
        "screening_Cp_top5": [round(float(c), 4) for c in scr.Cp_at_lam_des_TL.head(5)],
        "xfoil_order": [str(a) for a in best.airfoil],
        "winner": str(w.design_id),
        "winner_alpha_des": round(float(w.alpha_des), 2),
        "winner_Cp_at_5.4": round(float(w.Cp_at_lam_des_TL), 4),
        "winner_Cp_max": round(float(w.Cp_max_TL), 4),
        "winner_lambda_Cp_max": round(float(w.lam_Cp_max_TL), 2),
        "winner_CL": round(float(w.CL), 3),
        "winner_t_min_mm": round(float(w.t_min_mm), 2),
    }


def check() -> bool:
    import yaml
    got = current_results()
    if not (ROOT / "expected_results.yaml").exists():
        say("\nexpected_results.yaml not found. Result of this run:")
        for k, v in got.items():
            say(f"  {k:34s} {v}")
        return True
    exp = yaml.safe_load(open(ROOT / "expected_results.yaml", encoding="utf-8"))
    tol = {"screening_Cp_top5": 2e-4, "winner_Cp_at_5.4": 1e-3, "winner_Cp_max": 1e-3, "winner_CL": 0.01,
           "winner_t_min_mm": 0.05, "winner_alpha_des": 0.01, "winner_lambda_Cp_max": 0.11}
    say("\n===== Check against expected_results.yaml (the numbers in the report)")
    all_ok = True
    for k, e in exp.items():
        if k.startswith("_"):
            continue
        g = got.get(k)
        if k in tol:
            ok = (all(abs(a - b) <= tol[k] for a, b in zip(g, e)) and len(g) == len(e)) if isinstance(e, list) \
                else abs(g - e) <= tol[k]
        else:
            ok = g == e
        all_ok &= ok
        say(f"  {'OK  ' if ok else 'DIFF'}  {k:34s} expected {e}   got {g}")
    say("\nRESULT: " + ("same result as the report." if all_ok else "differences found, see DIFF lines above."))
    return all_ok


def write_expected() -> None:
    import yaml
    got = current_results()
    got = {"_note": "Result of reproduce.py on Windows, XFOIL 6.99 (bin/xfoil.exe), the run used in the report.",
           **got}
    (ROOT / "expected_results.yaml").write_text(yaml.safe_dump(got, sort_keys=False, allow_unicode=True),
                                                 encoding="utf-8")
    say("wrote expected_results.yaml")


def main():
    args = sys.argv[1:]
    if "--write-expected" in args:
        write_expected()
        return
    if "--check" in args:
        sys.exit(0 if check() else 1)
    if "--no-setup" not in args and not in_venv():
        setup_and_restart()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
    env.pop("WIND_BLADE_CONFIG", None)
    ensure_xfoil(env)
    if "--clean-cache" in args:
        for d in [ROOT / "cache", ROOT / "screening/results/polars"]:
            shutil.rmtree(d, ignore_errors=True)
        say("polar caches deleted")
    t0 = time.time()
    if "--sweep-only" in args:
        run(SWEEP, dict(env, WIND_BLADE_CONFIG="config_sweep.yaml"))
        say(f"\nSweep done in {(time.time() - t0) / 60:.1f} min. Results are in results/.")
        return
    if "--xfoil-only" in args:
        run(XFOIL_STUDY, env)
    else:
        run(SCREENING + XFOIL_STUDY + VALIDATION, env)
        if "--sweep" in args:
            run(SWEEP, dict(env, WIND_BLADE_CONFIG="config_sweep.yaml"))
    say(f"\nAll steps done in {(time.time() - t0) / 60:.1f} min.")
    sys.exit(0 if check() else 1)


if __name__ == "__main__":
    main()
