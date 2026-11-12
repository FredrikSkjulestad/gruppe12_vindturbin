"""Shared BEM functions for the TEP4175 blade study.

Sources quoted in the comments:
  [A1]  Assignment 1 (polars, 360 deg extrapolation with the Viterna method)
  [A3]  Assignment 3 (BEM design, flow charts in sections 4.3 and 4.4)
  [A4]  Assignment 4 (hub, root cut, tip section, constraints, performance with/without Prandtl)
  [MN]  BEM_metodenotat (method note, docs/BEM_metodenotat.pdf, sections 3 to 5)
  [H]   M.O.L. Hansen, Aerodynamics of Wind Turbines, ch. 6 (off-design BEM, Prandtl F).
        Not in the course documents: Assignment 4 did this step in QBlade.
  [B]   Buhl (2005), NREL/TP-500-36834, high-induction correction (a > 0.4). Not in course documents.
  [VC]  Viterna and Corrigan (1982), formulas behind the Viterna method named in [A1].
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path: Path | None = None) -> dict:
    """Read config.yaml, or the file named in the environment variable WIND_BLADE_CONFIG
    (set by run_sweep.bat to config_sweep.yaml). Relative paths are taken from this folder."""
    if path is None:
        env = os.environ.get("WIND_BLADE_CONFIG")
        path = (ROOT / env) if env else ROOT / "config.yaml"
    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    for k, v in cfg["paths"].items():
        cfg["paths"][k] = (ROOT / v) if not Path(v).is_absolute() else Path(v)
    return cfg


# =================================================================== polars
def alpha_opt_props(df: pd.DataFrame, offset: float = 0.0) -> dict | None:
    """alpha_opt = angle of max CL/CD in the (non-extrapolated) XFOIL polar [MN s.2, A3 s.3].
    alpha_des = alpha_opt + offset; CL, CD at alpha_des by linear interpolation between converged points.
    Only the pre-stall part (alpha <= alpha at CL_max) is searched."""
    if df is None or len(df) < 5:
        return None
    d = df.sort_values("alpha")
    pre = d[d.alpha <= d.alpha.iloc[int(np.argmax(d.CL.values))]]
    if len(pre) < 3:
        return None
    ld = pre.CL.values / pre.CD.values
    i = int(np.argmax(ld))
    a_opt = float(pre.alpha.values[i])
    a_des = a_opt + offset
    al = d.alpha.values
    if a_des < al.min() or a_des > al.max():
        return None
    # refuse to interpolate across a gap (non-converged stretch > 1 deg) around alpha_des
    j = np.searchsorted(al, a_des)
    if 0 < j < len(al) and al[j] - al[j - 1] > 1.0 + 1e-9 and al[j] != a_des:
        return None
    cl = float(np.interp(a_des, al, d.CL.values))
    cd = float(np.interp(a_des, al, d.CD.values))
    return dict(alpha_opt=a_opt, alpha_des=a_des, CL=cl, CD=cd, LD=cl / cd, LDmax=float(ld[i]))


def viterna_360(df: pd.DataFrame, cd_max: float, k_neg: float, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Extend a converged XFOIL polar to -180..180 deg [A1 s.2.8].
    Viterna and Corrigan [VC], attached at the last converged angle on each side:
        CD = B1 sin^2(a) + B2 cos(a),             B1 = CD_max, B2 = (CD_s - CD_max sin^2 a_s)/cos a_s
        CL = A1 sin(2a) + A2 cos^2(a)/sin(a),     A1 = B1/2,   A2 = (CL_s - CD_max sin a_s cos a_s) sin a_s / cos^2 a_s
    Back side (|a| > 90): CL = -k_neg * CL(180 - |a|), CD mirrored; linear to CL = 0 and CD = CD_0 at +-180.
    The positive and negative sides use their own stall point (last / first converged angle)."""
    d = df.sort_values("alpha")
    a, cl, cd = d.alpha.values, d.CL.values, d.CD.values
    cd0 = float(cd.min())

    def vit(x_deg, a_s, cl_s, cd_s):
        x, s = np.radians(x_deg), np.radians(a_s)
        B1 = cd_max
        B2 = (cd_s - cd_max * np.sin(s) ** 2) / np.cos(s)
        A1 = B1 / 2
        A2 = (cl_s - cd_max * np.sin(s) * np.cos(s)) * np.sin(s) / np.cos(s) ** 2
        return A1 * np.sin(2 * x) + A2 * np.cos(x) ** 2 / np.sin(x), B1 * np.sin(x) ** 2 + B2 * np.cos(x)

    def side(x, a_s, cl_s, cd_s):
        """x = |alpha| measured on this side, a_s = |stall angle| on this side, cl_s signed so that the
        side looks like a positive-alpha polar."""
        CL, CD = np.empty_like(x), np.empty_like(x)
        m1 = x <= 90
        CL[m1], CD[m1] = vit(np.maximum(x[m1], a_s), a_s, cl_s, cd_s)
        m2 = (x > 90) & (x < 180 - a_s)
        c2, d2 = vit(180 - x[m2], a_s, cl_s, cd_s)
        CL[m2], CD[m2] = -k_neg * c2, d2
        m3 = x >= 180 - a_s
        f = (180 - x[m3]) / a_s                       # 1 at 180 - a_s, 0 at 180
        CL[m3] = -k_neg * cl_s * f
        CD[m3] = cd0 + (cd_s - cd0) * f
        return CL, CD

    CLg, CDg = np.empty_like(grid), np.empty_like(grid)
    inside = (grid >= a[0]) & (grid <= a[-1])
    CLg[inside] = np.interp(grid[inside], a, cl)
    CDg[inside] = np.interp(grid[inside], a, cd)
    pos = grid > a[-1]
    CLg[pos], CDg[pos] = side(grid[pos], a[-1], cl[-1], cd[-1])
    neg = grid < a[0]
    # mirror the negative side: alpha -> -alpha, CL -> -CL
    c_n, d_n = side(-grid[neg], -a[0], -cl[0], cd[0])
    CLg[neg], CDg[neg] = -c_n, d_n
    return CLg, CDg


@dataclass
class PolarSet:
    """Re-dependent 360 deg polar of one airfoil on a uniform alpha grid, bilinear lookup in (alpha, Re)."""
    name: str
    re: np.ndarray                      # sorted Re values
    alpha: np.ndarray                   # uniform grid -180..180
    CL: np.ndarray                      # shape (n_re, n_alpha)
    CD: np.ndarray
    raw: dict = field(default_factory=dict)   # Re -> converged XFOIL DataFrame (for design)

    @classmethod
    def from_raw(cls, name: str, raw: dict, cfg: dict):
        step = cfg["viterna"]["grid_step"]
        grid = np.arange(-180, 180 + step / 2, step)
        cd_max = 1.11 + 0.018 * cfg["viterna"]["aspect_ratio"]            # [VC]
        res = sorted(raw)
        CL = np.zeros((len(res), len(grid)))
        CD = np.zeros_like(CL)
        for i, r in enumerate(res):
            CL[i], CD[i] = viterna_360(raw[r], cd_max, cfg["viterna"]["neg_cl_factor"], grid)
        return cls(name, np.array(res, float), grid, CL, CD, raw)

    def lookup(self, alpha_deg: np.ndarray, re: np.ndarray):
        a = (np.asarray(alpha_deg) + 180.0) % 360.0 - 180.0
        step = self.alpha[1] - self.alpha[0]
        x = (a - self.alpha[0]) / step
        i0 = np.clip(np.floor(x).astype(int), 0, len(self.alpha) - 2)
        wa = np.clip(x - i0, 0, 1)
        r = np.clip(np.asarray(re, float), self.re[0], self.re[-1])   # outside the grid: nearest polar
        if len(self.re) == 1:
            j0 = np.zeros_like(i0); wr = np.zeros_like(wa); j1 = j0
        else:
            j0 = np.clip(np.searchsorted(self.re, r) - 1, 0, len(self.re) - 2)
            j1 = j0 + 1
            wr = (r - self.re[j0]) / (self.re[j1] - self.re[j0])

        def bil(T):
            lo = T[j0, i0] * (1 - wa) + T[j0, i0 + 1] * wa
            hi = T[j1, i0] * (1 - wa) + T[j1, i0 + 1] * wa
            return lo * (1 - wr) + hi * wr
        return bil(self.CL), bil(self.CD)

    def design_props(self, re: float, offset: float) -> dict | None:
        """alpha_des, CL, CD at a given Re: evaluated in each XFOIL polar, then linear in Re
        (same approach as Ass3.py). Outside the Re grid the nearest polar is used."""
        rows = [(r, alpha_opt_props(self.raw[r], offset)) for r in self.re]
        rows = [(r, p) for r, p in rows if p is not None]
        if not rows:
            return None
        rs = np.array([r for r, _ in rows])
        out = {k: float(np.interp(re, rs, [p[k] for _, p in rows]))
               for k in ["alpha_opt", "alpha_des", "CL", "CD", "LDmax"]}
        out["LD"] = out["CL"] / out["CD"]
        return out


# =================================================================== design (Assignment 3)
def solve_a(lr: float) -> float:
    """16a^3 - 24a^2 + a(9 - 3 lr^2) - 1 + lr^2 = 0; physical root in (0.25, 1/3] [A3 flow chart, MN s.5]."""
    roots = np.roots([16.0, -24.0, 9.0 - 3.0 * lr**2, -1.0 + lr**2])
    real = roots[np.abs(roots.imag) < 1e-9].real
    ok = real[(real > 0.25 - 1e-12) & (real <= 1 / 3 + 1e-9)]
    if len(ok) == 0:
        raise ValueError(f"no physical root for lambda_r = {lr}")
    return float(ok[0])


def design_element(r: float, lam: float, CL: float, CD: float, alpha_des: float, rot: dict) -> dict:
    """One blade element with locked CL, CD, alpha_des [A3 s.4.4 flow chart, MN s.5]."""
    R, V1, Z = rot["R"], rot["V1"], rot["Z"]
    omega = lam * V1 / R                                        # [MN s.3]
    lr = r * lam / R                                            # lambda_r = r lambda / R
    a = solve_a(lr)                                             # cubic [A3]
    ap = (1 - 3 * a) / (4 * a - 1)                              # a' = (1 - 3a)/(4a - 1) [A3]
    phi = np.arctan2(1 - a, (1 + ap) * lr)                      # phi = atan((1-a)/((1+a') lr)), atan2 [MN s.5]
    Ca = CL * np.cos(phi) + CD * np.sin(phi)                    # C_a = CL cos(phi) + CD sin(phi) [A3]
    Lc = R * 8 * np.pi * a * lr * np.sin(phi) ** 2 / ((1 - a) * Z * Ca * lam)   # Lc/R [A3, MN s.5.1]
    theta = np.degrees(phi) - alpha_des                         # theta = phi - alpha [A3]
    W = np.sqrt(((1 - a) * V1) ** 2 + ((1 + ap) * omega * r) ** 2)             # [A3 s.4.3]
    Re = rot["rho"] * W * Lc / rot["mu"]                        # Re = rho W Lc / mu [A3]
    return dict(r=r, r_R=r / R, lambda_r=lr, a=a, a_prime=ap, phi_deg=np.degrees(phi),
                chord=Lc, Lc_R=Lc / R, theta_deg=theta, W=W, Re=Re)


def element_radii(rot: dict) -> np.ndarray:
    dr = rot["R"] / rot["N"]
    return (np.arange(1, rot["N"] + 1) - 0.5) * dr              # r_i = (i - 1/2) dr [A3 s.4.1]


def converge_re(polar: PolarSet, lam: float, offset: float, cfg: dict) -> dict | None:
    """Step 1 + Step 2 [A3 s.4.2-4.3, MN s.3-4]: iterate Re at the element closest to r/R = 0.7."""
    rot, des = cfg["rotor"], cfg["design"]
    r_el = element_radii(rot)
    r07 = r_el[np.argmin(np.abs(r_el / rot["R"] - 0.7))]
    omega = lam * rot["V1"] / rot["R"]
    W0 = np.sqrt(((1 - 1 / 3) * rot["V1"]) ** 2 + (omega * r07) ** 2)          # a = 1/3, a' = 0 [A3 Table 2]
    re_first = rot["rho"] * W0 * des["chord_first"] / rot["mu"]
    re, hist = re_first, [re_first]
    for _ in range(des["re_maxiter"]):
        p = polar.design_props(re, offset)
        if p is None:
            return None
        el = design_element(r07, lam, p["CL"], p["CD"], p["alpha_des"], rot)
        hist.append(el["Re"])
        if abs(el["Re"] - re) <= des["re_tol"]:                 # |Re_new - Re_old| <= tol [A3, MN s.4]
            # A3 flow chart: on convergence the CL, CD, alpha of the current pass are locked
            # (they were looked up at Re_old, which is within tol of Re_new)
            return dict(re_first=re_first, re_conv=el["Re"], n_iter=len(hist) - 1, re_hist=hist, **p)
        re = el["Re"]
    return None


def design_blade(lam: float, props: dict, cfg: dict) -> pd.DataFrame:
    """Step 3 [A3 s.4.4] with locked alpha_des, CL, CD; forces and design-point performance [MN s.6, A3 s.5.3]."""
    rot = cfg["rotor"]
    R, V1, Z, rho = rot["R"], rot["V1"], rot["Z"], rot["rho"]
    dr = R / rot["N"]
    rows = [design_element(r, lam, props["CL"], props["CD"], props["alpha_des"], rot) for r in element_radii(rot)]
    df = pd.DataFrame(rows)
    phi = np.radians(df.phi_deg)
    Ca = props["CL"] * np.cos(phi) + props["CD"] * np.sin(phi)
    Ct = props["CL"] * np.sin(phi) - props["CD"] * np.cos(phi)             # C_t = CL sin(phi) - CD cos(phi)
    q = 0.5 * rho * df.W ** 2 * df.chord
    df["ZdT"] = Z * q * Ca * dr                                            # Z dT' [MN s.6]
    df["ZdM"] = Z * q * Ct * dr                                            # Z dM'
    return df


def design_point_perf(df: pd.DataFrame, lam: float, cfg: dict) -> dict:
    rot = cfg["rotor"]
    R, V1, rho = rot["R"], rot["V1"], rot["rho"]
    omega = lam * V1 / R
    T = df.ZdT.sum()
    Q = (df.ZdM * df.r).sum()                                   # Q = sum Z dM' r [MN s.6]
    P = omega * Q
    A = np.pi * R**2
    return dict(P_design=P, Cp_design=P / (0.5 * rho * V1**3 * A), Ct_design=T / (0.5 * rho * V1**2 * A),
                T_design=T, Q_design=Q)


# =================================================================== realistic blade (Assignment 4)
def realistic_blade(design: pd.DataFrame, tc: float, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """[A4 s.2.1, Table 3]: remove sections with r - r_hub < 0, add cylinder at r_hub (48 mm, theta = 0),
    add tip section at r = R copying the last chord and twist. Chord clamped to [chord_min, chord_max]
    with twist kept from BEM (as specified for this study). Thickness t = (t/c) c checked [A4 Table 4]."""
    rot, con, rl = cfg["rotor"], cfg["constraints"], cfg["realistic"]
    keep = design[design.r - rot["r_hub"] >= 0].copy()
    st = [dict(r=rot["r_hub"], chord_bem=np.nan, chord=rl["cyl_diameter"], theta_deg=0.0, foil="cyl")]
    for _, e in keep.iterrows():
        c = float(np.clip(e.chord, con["chord_min"], con["chord_max"]))
        st.append(dict(r=e.r, chord_bem=e.chord, chord=c, theta_deg=e.theta_deg, foil="airfoil"))
    last = st[-1]
    st.append(dict(r=rot["R"], chord_bem=last["chord_bem"], chord=last["chord"], theta_deg=last["theta_deg"], foil="airfoil"))
    b = pd.DataFrame(st)
    b["r_minus_rhub"] = b.r - rot["r_hub"]
    b["clamped"] = (b.foil == "airfoil") & ~np.isclose(b.chord, b.chord_bem)
    b["clamp_delta_mm"] = np.where(b.clamped, (b.chord - b.chord_bem) * 1000, 0.0)
    b["t_max_mm"] = np.where(b.foil == "cyl", rl["cyl_diameter"] * 1000, tc * b.chord * 1000)
    b["t_ok"] = b.t_max_mm >= con["t_min"] * 1000 - 1e-9
    b["chord_ok"] = (b.chord >= con["chord_min"] - 1e-12) & (b.chord <= con["chord_max"] + 1e-12)
    el = b[(b.foil == "airfoil")].iloc[:-1]                      # BEM elements only (not the tip copy)
    info = dict(n_elements=len(el), n_clamped=int(el.clamped.sum()),
                clamped_fraction=float(el.clamped.mean()),
                n_clamped_min=int((el.clamped & (el.chord_bem < con["chord_min"])).sum()),
                n_clamped_max=int((el.clamped & (el.chord_bem > con["chord_max"])).sum()),
                max_clamp_mm=float(np.abs(el.clamp_delta_mm).max()),
                chord_bem_tip_mm=float(el.chord_bem.iloc[-1] * 1000),
                t_min_mm=float(b.t_max_mm.min()),
                constraints_ok=bool(b.t_ok.all() and b.chord_ok.all()))
    return b, info


# =================================================================== off-design BEM
def panels(blade: pd.DataFrame, n: int, R: float, r_hub: float) -> dict:
    """Cosine-spaced panels between r_hub and R (fine at root and tip, like QBlade). Chord and twist
    interpolated linearly between stations; w = share of airfoil polar (0 in the cylinder, blended
    linearly between the cylinder station and the first airfoil station, as QBlade blends polars)."""
    e = r_hub + (R - r_hub) * (1 - np.cos(np.linspace(0, np.pi, n + 1))) / 2
    rm, dr = 0.5 * (e[1:] + e[:-1]), np.diff(e)
    rs = blade.r.values
    w_st = (blade.foil != "cyl").astype(float).values
    return dict(r=rm, dr=dr,
                c=np.interp(rm, rs, blade.chord.values),
                theta=np.interp(rm, rs, blade.theta_deg.values),
                w=np.interp(rm, rs, w_st))


def bem_sweep(pan: dict, polar: PolarSet, lambdas: np.ndarray, cfg: dict, tip_loss: bool) -> dict:
    """Steady BEM over lambda, vectorised as (n_lambda, n_panels). Local Re from local W and chord.
    Iteration after [H] ch.6:
        phi = atan2((1-a) V1, (1+a') omega r),  alpha = phi - theta
        Cn = CL cos(phi) + CD sin(phi),  Ct = CL sin(phi) - CD cos(phi),  sigma = Z c / (2 pi r)
        F  = 2/pi acos(exp(-Z (R - r) / (2 r sin(phi))))    (Prandtl tip loss, F = 1 when off) [H eq. 6.35]
        a  = 1 / (4 F sin^2(phi) / (sigma Cn) + 1)          for a <= 0.4
             Buhl [B] from CT_loc = sigma (1-a)^2 Cn / sin^2(phi) for a > 0.4
        a' = 1 / (4 F sin(phi) cos(phi) / (sigma Ct) - 1)
    Forces and power as in [MN s.6]: dT = Z 1/2 rho W^2 c Cn dr, dQ = Z 1/2 rho W^2 c Ct r dr, P = omega Q."""
    rot, pf, rl = cfg["rotor"], cfg["performance"], cfg["realistic"]
    R, V1, Z, rho, mu = rot["R"], rot["V1"], rot["Z"], rot["rho"], rot["mu"]
    lam = np.asarray(lambdas, float)[:, None]
    omega = lam * V1 / R
    r, c, dr, w = pan["r"][None, :], pan["c"][None, :], pan["dr"][None, :], pan["w"][None, :]
    th = np.radians(pan["theta"])[None, :]
    sigma = Z * c / (2 * np.pi * r)
    shape = (lam.shape[0], r.shape[1])
    a, ap = np.full(shape, 0.3), np.zeros(shape)
    for it in range(pf["maxiter"]):
        phi = np.arctan2((1 - a) * V1, (1 + ap) * omega * r)
        W = np.sqrt(((1 - a) * V1) ** 2 + ((1 + ap) * omega * r) ** 2)
        Re = rho * W * c / mu
        alpha = np.degrees(phi - th)
        clf, cdf = polar.lookup(alpha, Re)
        CL = w * clf + (1 - w) * rl["cyl_CL"]
        CD = w * cdf + (1 - w) * rl["cyl_CD"]
        sphi, cphi = np.sin(phi), np.cos(phi)
        sphi_s = np.where(np.abs(sphi) < 1e-6, 1e-6, sphi)
        Cn = CL * cphi + CD * sphi
        Ct = CL * sphi - CD * cphi
        if tip_loss:
            f = Z * (R - r) / (2 * r * np.abs(sphi_s))
            F = np.clip(2 / np.pi * np.arccos(np.clip(np.exp(-f), 0, 1)), 1e-3, 1)
        else:
            F = np.ones(shape)
        a_mom = 1.0 / (4 * F * sphi_s**2 / (sigma * Cn) + 1)
        CTl = sigma * (1 - a) ** 2 * Cn / sphi_s**2
        disc = np.maximum(CTl * (50 - 36 * F) + 12 * F * (3 * F - 4), 0)
        a_buhl = (18 * F - 20 - 3 * np.sqrt(disc)) / (36 * F - 50)
        a_new = np.where(a_mom > 0.4, a_buhl, a_mom)
        ap_new = 1.0 / (4 * F * sphi_s * cphi / (sigma * Ct) - 1)
        a_new = np.clip(a_new, -0.5, 0.95)
        ap_new = np.clip(ap_new, -0.5, 1.0)
        da = np.abs(a_new - a).max() + np.abs(ap_new - ap).max()
        a += pf["relax"] * (a_new - a)
        ap += pf["relax"] * (ap_new - ap)
        if da < pf["tol"]:
            break
    q = 0.5 * rho * W**2 * c
    dT = Z * q * Cn * dr
    dQ = Z * q * Ct * r * dr
    A = np.pi * R**2
    P = omega[:, 0] * dQ.sum(1)
    return dict(lam=lam[:, 0], Cp=P / (0.5 * rho * V1**3 * A), Ct=dT.sum(1) / (0.5 * rho * V1**2 * A),
                P=P, Q=dQ.sum(1), T=dT.sum(1), a=a, ap=ap, alpha=alpha, Re=Re, W=W, F=F,
                rot_ratio=((1 + ap) * omega * r) / ((1 - a) * V1), converged_iter=it + 1, residual=da)


def summarise(res: dict, frac: float) -> dict:
    lam, cp = res["lam"], res["Cp"]
    i = int(np.argmax(cp))
    ok = lam[cp >= frac * cp[i]]
    return dict(Cp_max=float(cp[i]), lam_at_Cp_max=float(lam[i]), Ct_at_Cp_max=float(res["Ct"][i]),
                plateau_lo=float(ok.min()), plateau_hi=float(ok.max()), plateau_width=float(ok.max() - ok.min()))


def load_polarset(name: str, cfg: dict) -> PolarSet:
    """Rebuild the Re-dependent 360 deg polar of one airfoil from Step 2's raw CSV files."""
    d = cfg["paths"]["results"] / "polars" / name
    raw = {}
    for f in sorted(d.glob("raw_Re*.csv")):
        df = pd.read_csv(f)
        if len(df) >= 5:
            raw[float(f.stem.split("Re")[1])] = df
    if not raw:
        raise FileNotFoundError(f"no polars for {name} in {d}; run 01_polars.py first")
    return PolarSet.from_raw(name, raw, cfg)
