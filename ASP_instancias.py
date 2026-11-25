"""
Herramientas para instancias ASP (problema de aterrizaje de aeronaves en una pista única)

1. download_orlib()    -> descarga airland1..13 de OR-Library (Beasley)
2. parse_orlib()       -> las lee en un diccionario de Python (igual para Gurobi y CPLEX)
3. generate_instance() -> genera instancias sintéticas con categorías Pesada/Media/Ligera
4. build_experiments() -> diseño experimental completo (tamaños x mezclas x réplicas)

Estructura del diccionario de instancia:
  n, freeze, appear[], earliest[], target[], latest[], pen_early[], pen_late[],
  sep[i][j] (segundos; i aterriza inmediatamente antes que j), cat[] (H/M/L, solo generadas)

Ejecución: python ASP_instancias_traducido.py
            (descarga OR-Library si hay conexion y genera todas las instancias)
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
            print("Descargado:", dst)

def parse_orlib(path):
    """Formato: 'p freeze' y luego, por avión: appear earliest target latest,
    pen_early pen_late, seguidos de p valores de separación (pueden ocupar varias líneas)."""
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

# ---------------------------------------------------------------- 2. Matriz de separacion
# Separación temporal mínima en SEGUNDOS; fila = líder, columna = seguidor.
# Perfil "literature": valores de la literatura sobre ASP (Ernst et al. / Bianco et al.),
#   mínimos de distancia de radar convertidos a segundos según las velocidades de aproximación.
# Perfil "dap11_hybrid": máximo elemento a elemento entre el valor bibliográfico y los mínimos
#   temporales de aterrizaje de ICAO/DAP 11 00 (sec. 5.8.2, verificados en el texto DAP proporcionado):
#   Media detrás de Pesada: 120 s; Ligera detrás de Pesada o Media: 180 s.
#   (La DAP también incluye la categoría SUPER, p. ej., A380, que no se modela: no hay Super en CCP.)
#   Esos mínimos no cubren todos los pares; los pares no cubiertos conservan el valor bibliográfico.
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

# Mezclas de aeronaves (probabilidades de H, M, L). Las mezclas de Biobío son ESCENARIOS basados en:
#  - Flightradar24 CCP: ~45 movimientos comerciales/día (todos Medium) -- no es una cifra oficial
#  - Gráfico DGAC 2026 (trabajos aéreos/aviación ligera filtrados): 8.913 operaciones en 273 días = 32,65/día
#  => proporción de ligeras ~ 32,65 / (45 + 32,65) = 42 % de los movimientos. ADVERTENCIAS: promedio
#     inflado por el pico de enero de 2026 (>200 operaciones/día, probablemente por incendios forestales);
#     muchos días registran casi 0; los recuentos incluyen despegues; la categoría ICAO depende de la masa
#     máxima de despegue (MTOW), no del tipo de actividad; la proporción de pesadas es una estimación.
MIXES = {
    "biobio_comercial": {"H": 0.01, "M": 0.94, "L": 0.05},  # aviacion comercial y taxis aereos
    "biobio_prom2026":  {"H": 0.01, "M": 0.57, "L": 0.42},  # promedio 2026, incluye aeronaves ligeras
    "balanced":  {"H": 0.25, "M": 0.50, "L": 0.25},
    "heavy_mix": {"H": 0.40, "M": 0.40, "L": 0.20},  # prueba de estres para efectos de estela
}

def sep_matrix(cats, profile="literature", lvp_factor=1.0):
    """lvp_factor > 1 aumenta las separaciones (procedimientos de baja visibilidad:
    se debe informar que la pista está despejada). Supuesto por calibrar; 1.0 = operaciones normales."""
    T = SEP_PROFILES[profile]
    return [[0 if i == j else T[(cats[i], cats[j])] * lvp_factor
             for j in range(len(cats))] for i in range(len(cats))]

# ---------------------------------------------------------------- 3. Generador de instancias
def generate_instance(n, mix="biobio_comercial", congestion=1.0, window=600, seed=0,
                      profile="literature", lvp_factor=1.0):
    """congestion: horizonte = n * separación media * congestion (un valor menor implica más congestión).
    window: semiancho (s) de la ventana temporal alrededor del objetivo."""
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
    # Penalización por segundo: las aeronaves más pesadas cuestan más; el retraso cuesta más que el adelanto.
    base = {"H": 30, "M": 20, "L": 10}
    pen_early = [base[c] for c in cats]
    pen_late = [base[c] * 1.5 for c in cats]
    # Reparación de factibilidad: orden voraz por objetivo; ampliar 'latest' si es necesario.
    order = sorted(range(n), key=lambda i: target[i]); prev, t_prev = None, 0
    for i in order:
        t = earliest[i] if prev is None else max(earliest[i], t_prev + sep[prev][i])
        if t > latest[i]:
            latest[i] = t + 60
        prev, t_prev = i, t
    return dict(n=n, freeze=0, appear=appear, earliest=earliest, target=target,
                latest=latest, pen_early=pen_early, pen_late=pen_late, sep=sep, cat=cats)

# ---------------------------------------------------------------- 4. Diseño experimental
SIZES = {"small": [10, 15, 20, 30],     # validación: Gurobi == CPLEX, se alcanza el óptimo
         "medium": [50, 100],           # óptimo frente al límite de tiempo
         "large": [150, 200, 250]}      # comportamiento de la brecha bajo límite de tiempo
MIXES_USED = ["biobio_comercial", "biobio_prom2026", "balanced", "heavy_mix"]
PROFILES_USED = ["literature", "dap11_hybrid"]
REPLICAS = 5                            # semillas por (tamaño, mezcla)
SOLVER_SETTINGS = dict(mip_gap=1e-4, threads=1)  # configuración idéntica para ambos solvers
# NOTA: el límite de tiempo se define por modo experimental en experimentos.py

# NOTA: n cuenta solo ATERRIZAJES. Los tamanos >= 100 son pruebas de estres computacional:
# se comprimen en un horizonte breve, no son ventanas operativas realistas en Carriel Sur.

def build_experiments(folder="instances/generated"):
    rows = []
    for profile in PROFILES_USED:
        out = os.path.join(folder, profile); os.makedirs(out, exist_ok=True)
        for group, sizes in SIZES.items():
            for n in sizes:
                for mix in MIXES_USED:
                    for r in range(REPLICAS):
                        name = f"asp_{mix}_n{n}_r{r}"
                        seed = n * 1000 + MIXES_USED.index(mix) * 100 + r  # misma semilla para ambos perfiles
                        d = generate_instance(n, mix, seed=seed, profile=profile)
                        write_orlib(d, os.path.join(out, name + ".txt"))
                        with open(os.path.join(out, name + "_cat.txt"), "w") as f:
                            f.write(" ".join(d["cat"]))
                        rows.append(dict(name=name, profile=profile, group=group,
                                         n=n, mix=mix, replica=r))
    with open(os.path.join(folder, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "profile", "group", "n", "mix", "replica"])
        w.writeheader(); w.writerows(rows)
    print(len(rows), "instancias generadas ->", folder)

if __name__ == "__main__":
    try:
        download_orlib()
    except Exception as e:
        print("Falló la descarga de OR-Library (descargue airland1-13.txt manualmente):", e)
    build_experiments()
