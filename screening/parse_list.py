import re, sys, pandas as pd
txt = open(sys.argv[1]).read()
rows = []
for blk in re.finditer(r"λ=([\d.]+) \(Cl≤([\d.]+), Re≈(\d+)k\), (\d+) airfoils:\n(.+)", txt):
    lam, clmax, re_k, n, body = blk.groups()
    items = [s.strip() for s in body.split(";") if s.strip()]
    assert len(items) == int(n), (lam, len(items), n)
    for it in items:
        name, vals = it.rsplit(" ", 1)
        tc, ld, cl, a = map(float, vals.split("/"))
        rows.append(dict(name=name, list_lambda=float(lam), Cl_ceiling=float(clmax), Re_tip=int(re_k)*1000,
                         tc=tc, LDmax=ld, Cl_LDmax=cl, alpha_opt=a))
df = pd.DataFrame(rows)
df.to_csv("foil_list_676.csv", index=False)
print(len(df), "airfoils,", df.name.nunique(), "unique")
print(df.groupby("list_lambda").size())
