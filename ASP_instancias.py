"""
ASP instance toolkit (single runway, aircraft landing problem)

1. download_orlib()    -> downloads OR-Library airland1..13 (Beasley)
2. parse_orlib()       -> reads them into a Python dict (same for Gurobi and CPLEX)
3. generate_instance() -> synthetic instances with Heavy/Medium/Light categories
4. build_experiments() -> full experimental design (sizes x mixes x replicas)

Instance dict:
  n, freeze, appear[], earliest[], target[], latest[], pen_early[], pen_late[],
  sep[i][j] (seconds, i lands immediately before j), cat[] (H/M/L, generated only)

Run:  python asp_instances.py   (downloads OR-Lib if internet, generates all instances)
"""
import os, random, csv, urllib.request

ORLIB_URL = "http://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/airland{}.txt"
ORLIB_SIZES = {1: 10, 2: 15, 3: 20, 4: 20, 5: 20, 6: 30, 7: 44,
               8: 50, 9: 100, 10: 150, 11: 200, 12: 250, 13: 500}

# ---------------------------------------------------------------- 1. OR-Library
def download_orlib(folder="instances/orlib", ids=range(1, 14)):
    os.makedirs(folder, exist_ok=True)
    for k in ids:
        dst = os.path.join(folder, f"airland{k}.txt")
        if not os.path.exists(dst):
            urllib.request.urlretrieve(ORLIB_URL.format(k), dst)
            print("downloaded", dst)

def parse_orlib(path):
    """Format: 'p freeze' then per plane: appear earliest target latest
    pen_early pen_late, followed by p separation values (may wrap lines)."""
    tok = open(path).read().split()
    n, freeze = int(tok[0]), float(tok[1]); pos = 2
    d = dict(n=n, freeze=freeze, appear=[], earliest=[], target=[], latest=[],
             pen_early=[], pen_late=[], sep=[], cat=None)
    for _ in range(n):
        a, e, t, l, pe, pl = map(float, tok[pos:pos + 6]); pos += 6
        d["appear"].append(a); d["earliest"].append(e); d["target"].append(t)
        d["latest"].append(l); d["pen_early"].append(pe); d["pen_late"].append(pl)
        d["sep"].append([float(x) for x in tok[pos:pos + n]]); pos += n
    return d

def write_orlib(d, path):
    with open(path, "w") as f:
        f.write(f"{d['n']} {int(d['freeze'])}\n")
        for i in range(d["n"]):
            f.write(f" {d['appear'][i]:g} {d['earliest'][i]:g} {d['target'][i]:g} "
                    f"{d['latest'][i]:g} {d['pen_early'][i]:g} {d['pen_late'][i]:g}\n")
            f.write(" ".join(f"{x:g}" for x in d["sep"][i]) + "\n")

# ---------------------------------------------------------------- 2. Separation matrix
# Minimum time separation in SECONDS, row = leader, column = follower.
# Profile "literature": values from the ASP literature (Ernst et al. / Bianco et al.),
#   radar distance minima converted to seconds at approach speeds.
# Profile "dap11_hybrid": element-wise max of the literature value and the ICAO/DAP 11 00
#   time-based minima for landings (sec. 5.8.2, VERIFIED from the DAP text provided):
#   Medium behind Heavy 120 s, Light behind Heavy or Medium 180 s.
#   (The DAP also has a SUPER category, e.g. A380, not modelled: no Super at CCP.)
#   Those minima do not cover every pair, so uncovered pairs keep the literature value.
SEP_LITERATURE = {
    ("H", "H"): 96, ("H", "M"): 157, ("H", "L"): 196,
    ("M", "H"): 60, ("M", "M"): 69,  ("M", "L"): 131,
    ("L", "H"): 60, ("L", "M"): 69,  ("L", "L"): 82,
}
DAP_TIME_MIN = {("H", "M"): 120, ("H", "L"): 180, ("M", "L"): 180}
SEP_PROFILES = {
    "literature": dict(SEP_LITERATURE),
    "dap11_hybrid": {k: max(v, DAP_TIME_MIN.get(k, 0)) for k, v in SEP_LITERATURE.items()},
}

# Aircraft mixes (probabilities of H, M, L). Biobio mixes are SCENARIOS built from:
#  - Flightradar24 CCP: ~45 commercial movements/day (all Medium) -- not official
#  - DGAC chart 2026 (filtered aerial work/light aviation): 8,913 ops in 273 days = 32.65/day
#  => light share ~ 32.65 / (45 + 32.65) = 42% of movements. CAVEATS: average inflated by
#  the Jan-2026 spike (>200 ops/day, likely wildfires); many days near 0; counts include
#  departures; ICAO category depends on MTOW, not on activity type; Heavy share is a guess.
MIXES = {
    "biobio_comercial": {"H": 0.01, "M": 0.94, "L": 0.05},  # commercial + air taxi only
    "biobio_prom2026":  {"H": 0.01, "M": 0.57, "L": 0.42},  # 2026 average incl. light aircraft
    "balanced":  {"H": 0.25, "M": 0.50, "L": 0.25},
    "heavy_mix": {"H": 0.40, "M": 0.40, "L": 0.20},          # stress test for wake effects
}

def sep_matrix(cats, profile="literature", lvp_factor=1.0):
    """lvp_factor > 1 inflates separations (low-visibility procedures: runway must be
    reported clear). ASSUMPTION to calibrate; 1.0 = normal operations."""
    T = SEP_PROFILES[profile]
    return [[0 if i == j else T[(cats[i], cats[j])] * lvp_factor
             for j in range(len(cats))] for i in range(len(cats))]

# ---------------------------------------------------------------- 3. Generator
def generate_instance(n, mix="biobio_comercial", congestion=1.0, window=600, seed=0,
                      profile="literature", lvp_factor=1.0):
    """congestion: horizon = n * mean_sep * congestion (smaller = more congested).
    window: half-width (s) of the time window around the target."""
    rng = random.Random(seed)
    p = MIXES[mix]
    cats = rng.choices(list(p), weights=list(p.values()), k=n)
    sep = sep_matrix(cats, profile, lvp_factor)
    mean_sep = sum(sep[i][j] for i in range(n) for j in range(n) if i != j) / max(1, n * (n - 1))
    horizon = n * mean_sep * congestion
    target = sorted(rng.uniform(window, window + horizon) for _ in range(n))
    appear = [max(0, t - window - rng.uniform(0, 600)) for t in target]
    earliest = [max(a, t - rng.uniform(0.3, 1.0) * window) for a, t in zip(appear, target)]
    latest = [t + rng.uniform(0.3, 1.0) * window for t in target]
    # penalties per second: heavier aircraft cost more; delay costs more than earliness
    base = {"H": 30, "M": 20, "L": 10}
    pen_early = [base[c] for c in cats]
    pen_late = [base[c] * 1.5 for c in cats]
    # feasibility repair: greedy in target order, widen 'latest' if needed
    order = sorted(range(n), key=lambda i: target[i]); prev, t_prev = None, 0
    for i in order:
        t = earliest[i] if prev is None else max(earliest[i], t_prev + sep[prev][i])
        if t > latest[i]:
            latest[i] = t + 60
        prev, t_prev = i, t
    return dict(n=n, freeze=0, appear=appear, earliest=earliest, target=target,
                latest=latest, pen_early=pen_early, pen_late=pen_late, sep=sep, cat=cats)

# ---------------------------------------------------------------- 4. Experimental design
SIZES = {"small": [10, 15, 20, 30],     # validation: Gurobi == CPLEX, reaches optimum
         "medium": [50, 100],           # optimum vs time-limit boundary
         "large": [150, 200, 250]}      # gap behaviour under time limit
MIXES_USED = ["biobio_comercial", "biobio_prom2026", "balanced", "heavy_mix"]
PROFILES_USED = ["literature", "dap11_hybrid"]
REPLICAS = 5                            # seeds per (size, mix)
SOLVER_SETTINGS = dict(time_limit=600, mip_gap=1e-4, threads=1)  # identical for both solvers
# NOTE: n counts LANDINGS only. Sizes >= 100 are computational stress tests (they are
# compressed into a short horizon), not realistic operational windows at Carriel Sur.

def build_experiments(folder="instances/generated"):
    rows = []
    for profile in PROFILES_USED:
        out = os.path.join(folder, profile); os.makedirs(out, exist_ok=True)
        for group, sizes in SIZES.items():
            for n in sizes:
                for mix in MIXES_USED:
                    for r in range(REPLICAS):
                        name = f"asp_{mix}_n{n}_r{r}"
                        seed = n * 1000 + MIXES_USED.index(mix) * 100 + r   # same seed for both profiles
                        d = generate_instance(n, mix, seed=seed, profile=profile)
                        write_orlib(d, os.path.join(out, name + ".txt"))
                        with open(os.path.join(out, name + "_cat.txt"), "w") as f:
                            f.write(" ".join(d["cat"]))
                        rows.append(dict(name=name, profile=profile, group=group,
                                         n=n, mix=mix, replica=r))
    with open(os.path.join(folder, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "profile", "group", "n", "mix", "replica"])
        w.writeheader(); w.writerows(rows)
    print(len(rows), "generated instances ->", folder)

if __name__ == "__main__":
    try:
        download_orlib()
    except Exception as e:
        print("OR-Library download failed (download airland1-13.txt manually):", e)
    build_experiments()