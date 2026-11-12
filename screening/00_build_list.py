"""Step 0a: build the candidate list from the UIUC airfoil database.

This is the first filter of the study. It goes through every airfoil in the UIUC coordinate set that
ships with AeroSandbox 4.2.10 (2174 airfoils) and keeps the ones that can be built and that can reach
the 40 mm tip chord:

  1. Thickness: 12.5 % <= t/c <= 25 % (t/c rounded to 0.1 %, as in the original list). 12.5 % is the
     5 mm minimum thickness at the 40 mm tip chord.
  2. For each design tip speed ratio in LAMBDAS, NeuralFoil polars (model "large", Ncrit 5) at the
     tip Reynolds number of that lambda, alpha -5..15 deg in 0.25 deg steps. Points with a NeuralFoil
     analysis confidence below MIN_CONFIDENCE are not used.
  3. The optimum-rotor chord scales as 1/(Cl lambda^2), so the 40 mm minimum tip chord gives a maximum
     design Cl for each lambda (CL_CEILING). An airfoil is kept if its Cl at max L/D is at or below the
     ceiling for at least one lambda, and it is listed under the highest such lambda.

The constants below are the values the original candidate list (reference/foil_list_676.txt) was made with.
This script rebuilds that list from the database: the same 676 airfoils with the same t/c. Only the
lambda block of 11 borderline airfoils (Cl within 0.01 of a ceiling) can differ; the screening does
not use the block, only the names and t/c.

Run from the repository folder (needs aerosandbox==4.2.10 and neuralfoil==0.3.3):
    .venv\\Scripts\\python screening\\00_build_list.py

Writes: screening/results/candidates_uiuc.txt   the list, same text format as foil_list_676.txt
        screening/results/candidates_uiuc.csv   the same as a table
and prints a comparison with the original list, screening/reference/foil_list_676.txt.
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from parse_list import read_list  # noqa: E402

# ---------------------------------------------------------------- settings of the original list
TC_MIN, TC_MAX = 12.5, 25.0                              # t/c in %, rounded to 0.1 %
LAMBDAS = [6.5, 6.0, 5.5, 5.0, 4.5]                      # design tip speed ratios, highest first
CL_CEILING = [0.76, 0.88, 1.05, 1.26, 1.54]              # max design Cl for a 40 mm tip chord
RE_TIP = [249_000, 230_000, 212_000, 193_000, 175_000]   # tip Reynolds number for each lambda
ALPHA = np.arange(-5.0, 15.0001, 0.25)                   # deg
NCRIT = 5
MODEL_SIZE = "large"
MIN_CONFIDENCE = 0.6                                     # NeuralFoil analysis_confidence

OUT = HERE / "results"
REFERENCE = HERE / "reference" / "foil_list_676.txt"


def uiuc_names() -> list[str]:
    import aerosandbox as asb
    db = Path(asb.__file__).parent / "geometry" / "airfoil" / "airfoil_database"
    return sorted(f.stem for f in db.glob("*.dat"))


def classify(name: str) -> dict | None:
    import aerosandbox as asb
    import neuralfoil as nf
    af = asb.Airfoil(name)
    try:
        tc = round(100 * float(af.max_thickness()), 1)
    except Exception:
        return None                                      # no usable coordinates
    if not (TC_MIN <= tc <= TC_MAX):
        return None
    for lam, ceil, re in zip(LAMBDAS, CL_CEILING, RE_TIP):
        a = nf.get_aero_from_airfoil(af, alpha=ALPHA, Re=float(re), n_crit=NCRIT, model_size=MODEL_SIZE)
        cl, cd, conf = (np.asarray(a[k]) for k in ("CL", "CD", "analysis_confidence"))
        i = int(np.argmax(cl / cd))
        if conf[i] < MIN_CONFIDENCE:
            continue
        if cl[i] <= ceil:
            return dict(name=name, list_lambda=lam, Cl_ceiling=ceil, Re_tip=re, tc=tc,
                        LDmax=round(float(cl[i] / cd[i])), Cl_LDmax=round(float(cl[i]), 2),
                        alpha_opt=float(ALPHA[i]))
    return None


def write_txt(df: pd.DataFrame, path: Path) -> None:
    head = (f"Candidate airfoils built by screening/00_build_list.py from the UIUC set in AeroSandbox 4.2.10.\n"
            f"Filter: {TC_MIN}% <= t/c <= {TC_MAX}%. Polars: NeuralFoil {MODEL_SIZE}, Ncrit = {NCRIT}, "
            f"Re = tip Re for each λ, points with confidence < {MIN_CONFIDENCE} not used. Each airfoil is "
            f"listed once, under the highest λ where its Cl at max L/D is at or below that λ's Cl ceiling. "
            f"Sorted by L/D max.\nFormat: name t/c%/LDmax/Cl_at_LDmax/alpha_opt_deg\n")
    blocks = []
    for lam, ceil, re in zip(LAMBDAS, CL_CEILING, RE_TIP):
        g = df[df.list_lambda == lam].sort_values(["LDmax", "name"], ascending=[False, True])
        items = "; ".join(f"{r.name} {r.tc:.1f}/{r.LDmax:.0f}/{r.Cl_LDmax:.2f}/{r.alpha_opt:g}" for r in g.itertuples())
        blocks.append(f"λ={lam} (Cl≤{ceil}, Re≈{re // 1000}k), {len(g)} airfoils:\n{items}")
    path.write_text(head + "\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")


def main():
    warnings.filterwarnings("ignore")
    OUT.mkdir(parents=True, exist_ok=True)
    names = uiuc_names()
    print(f"{len(names)} airfoils in the UIUC set (AeroSandbox)", flush=True)
    t0, rows = time.time(), []
    for k, n in enumerate(names, 1):
        r = classify(n)
        if r:
            rows.append(r)
        if k % 500 == 0 or k == len(names):
            print(f"  {k}/{len(names)}  kept {len(rows)}  ({time.time() - t0:.0f} s)", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "candidates_uiuc.csv", index=False)
    write_txt(df, OUT / "candidates_uiuc.txt")
    print(f"{len(df)} candidates -> {OUT / 'candidates_uiuc.txt'}")
    print(df.groupby("list_lambda").size().sort_index(ascending=False).to_string())

    if REFERENCE.exists():                                # check against the original list
        ref = read_list(REFERENCE).set_index("name")
        mine = df.set_index("name")
        only_new, only_ref = sorted(set(mine.index) - set(ref.index)), sorted(set(ref.index) - set(mine.index))
        both = sorted(set(mine.index) & set(ref.index))
        tc_diff = int((mine.loc[both, "tc"] - ref.loc[both, "tc"]).abs().gt(1e-9).sum())
        block = int((mine.loc[both, "list_lambda"] != ref.loc[both, "list_lambda"]).sum())
        same = not only_new and not only_ref and tc_diff == 0
        print(f"\nCompared with {REFERENCE.name}: {'SAME airfoils and t/c' if same else 'DIFFERENT'}"
              f" ({len(both)} in both, {len(only_new)} only here, {len(only_ref)} only in the original,"
              f" {tc_diff} t/c differences; {block} listed under another λ block, not used by the screening)")
        if only_new or only_ref:
            print("  only here:", ", ".join(only_new) or "-", "| only in the original:", ", ".join(only_ref) or "-")


if __name__ == "__main__":
    main()
