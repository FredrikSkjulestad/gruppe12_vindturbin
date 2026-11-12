"""Read an airfoil candidate list for the screening (00_screen.py).

Three formats are accepted:

1. The NeuralFoil list format of foil_list_676.txt (one block per lambda):
       λ=6.5 (Cl≤0.76, Re≈249k), 57 airfoils:
       goe600 13.1/67/0.75/4.75; l188root 14.0/67/0.73/4.5; ...
   Each item is: name t/c%/LDmax/Cl_at_LDmax/alpha_opt_deg. Text outside the blocks
   (the description at the top) is ignored.

2. A plain text file with one UIUC name per line, optionally followed by t/c in %:
       mh114
       e396 13.1
   Empty lines and lines starting with # are ignored.

3. A CSV file with at least a column "name" (and optionally "tc", t/c in %).

When t/c is not given it is measured from the AeroSandbox UIUC geometry (asb.Airfoil(name)).
Names must match the UIUC file names bundled with AeroSandbox 4.2.10 (as on airfoiltools.com,
without the "-il" ending).

From the command line this converts a list to CSV (written next to the input file):
    .venv\\Scripts\\python screening\\parse_list.py screening\\foil_list_676.txt
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

BLOCK = re.compile(r"λ\s*=\s*([\d.]+)\s*\(Cl\s*≤\s*([\d.]+),\s*Re\s*≈\s*(\d+)k\),\s*(\d+)\s+airfoils:[ \t]*\n(.+)")


def _parse_blocks(txt: str) -> pd.DataFrame:
    rows = []
    for blk in BLOCK.finditer(txt):
        lam, clmax, re_k, n, body = blk.groups()
        items = [s.strip() for s in body.split(";") if s.strip()]
        if len(items) != int(n):
            raise ValueError(f"block λ={lam} says {n} airfoils but lists {len(items)}")
        for it in items:
            name, vals = it.rsplit(" ", 1)
            tc, ld, cl, a = map(float, vals.split("/"))
            rows.append(dict(name=name.strip(), list_lambda=float(lam), Cl_ceiling=float(clmax),
                             Re_tip=int(re_k) * 1000, tc=tc, LDmax=ld, Cl_LDmax=cl, alpha_opt=a))
    return pd.DataFrame(rows)


def _parse_plain(txt: str) -> pd.DataFrame:
    rows = []
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.replace(",", " ").split()
        rows.append(dict(name=parts[0], tc=float(parts[1]) if len(parts) > 1 else float("nan")))
    return pd.DataFrame(rows, columns=["name", "tc"])


def _check_names(names) -> None:
    import aerosandbox as asb
    unknown = []
    for n in names:
        try:
            if asb.Airfoil(n).coordinates is None:
                unknown.append(n)
        except Exception:
            unknown.append(n)
    if unknown:
        raise ValueError("not in the AeroSandbox UIUC set (check the spelling): " + ", ".join(unknown))


def _fill_tc(df: pd.DataFrame) -> pd.DataFrame:
    if "tc" not in df:
        df["tc"] = float("nan")
    missing = df.tc.isna()
    if missing.any():
        import aerosandbox as asb
        df.loc[missing, "tc"] = [round(100 * asb.Airfoil(n).max_thickness(), 1) for n in df.name[missing]]
    return df


def read_list(path) -> pd.DataFrame:
    """Return a DataFrame with at least the columns name and tc (t/c in %), one row per airfoil."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if "name" not in df:
            raise ValueError(f"{path} needs a column 'name'")
    else:
        txt = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        df = _parse_blocks(txt) if BLOCK.search(txt) else _parse_plain(txt)
    if df.empty:
        raise ValueError(f"no airfoils found in {path}")
    dup = sorted(set(df.name[df.name.duplicated()]))
    if dup:
        raise ValueError(f"airfoils listed more than once in {path}: {', '.join(dup)}")
    _check_names(df.name)
    return _fill_tc(df).reset_index(drop=True)


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "foil_list_676.txt"
    df = read_list(src)
    out = src.with_suffix(".csv")
    df.to_csv(out, index=False)
    print(len(df), "airfoils ->", out)
    if "list_lambda" in df:
        print(df.groupby("list_lambda").size().to_string())
