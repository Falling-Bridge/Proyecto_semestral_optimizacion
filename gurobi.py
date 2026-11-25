
import argparse
import gurobipy as gp
from gurobipy import GRB
from ASP_instancias import (
    generate_instance,
    parse_orlib,
    SOLVER_SETTINGS
)
from validacion import validar_solucion

# Descripcion legible de los codigos de estado de Gurobi
ESTADOS_GUROBI = {
    1: "LOADED",
    2: "OPTIMAL",
    3: "INFEASIBLE",
    4: "INF_OR_UNBD",
    5: "UNBOUNDED",
    6: "CUTOFF",
    7: "ITERATION_LIMIT",
    8: "NODE_LIMIT",
    9: "TIME_LIMIT",
    10: "SOLUTION_LIMIT",
    11: "INTERRUPTED",
    12: "NUMERIC",
    13: "SUBOPTIMAL",
    14: "INPROGRESS",
    15: "USER_OBJ_LIMIT",
    16: "WORK_LIMIT",
    17: "MEM_LIMIT",
}


def resolver_gurobi(datos, limite_tiempo=3600, mostrar=True):
    """Resuelve el problema ASP de pista unica mediante Gurobi."""

    # Conjunto de aeronaves
    N = range(datos["n"])

    # Parametros del modelo
    E = datos["earliest"]
    T = datos["target"]
    L = datos["latest"]
    g = datos["pen_early"]
    h = datos["pen_late"]
    S = datos["sep"]

    # Inicializacion del modelo
    modelo = gp.Model("ASP_Carriel_Sur")

    # Variables de decision continuas
    t = modelo.addVars(N, lb=0, vtype=GRB.CONTINUOUS, name="t")
    e = modelo.addVars(N, lb=0, vtype=GRB.CONTINUOUS, name="e")
    d = modelo.addVars(N, lb=0, vtype=GRB.CONTINUOUS, name="d")

    # Variables binarias de precedencia
    x = modelo.addVars(
        [(i, j) for i in N for j in N if i != j],
        vtype=GRB.BINARY,
        name="x"
    )

    # Funcion objetivo
    modelo.setObjective(
        gp.quicksum(g[i] * e[i] + h[i] * d[i] for i in N),
        GRB.MINIMIZE
    )

    # Restricciones de ventanas temporales
    modelo.addConstrs(
        (t[i] >= E[i] for i in N),
        name="tiempo_minimo"
    )

    modelo.addConstrs(
        (t[i] <= L[i] for i in N),
        name="tiempo_maximo"
    )

    # Balance entre tiempos asignados y objetivos
    modelo.addConstrs(
        (t[i] - T[i] == d[i] - e[i] for i in N),
        name="desviacion_temporal"
    )

    # Consistencia de las relaciones de precedencia
    modelo.addConstrs(
        (x[i, j] + x[j, i] == 1
         for i in N for j in N if i < j),
        name="precedencia"
    )

    # Constantes Big-M ajustadas a las ventanas temporales
    M = {
        (i, j): max(0, L[i] + S[i][j] - E[j])
        for i in N for j in N if i != j
    }

    # Restricciones de separacion temporal
    modelo.addConstrs(
        (t[j] - t[i] + M[i, j] * (1 - x[i, j]) >= S[i][j]
         for i in N for j in N if i != j),
        name="separacion"
    )

    modelo.update()

    # Configuracion del solver (identica para ambos solvers)
    modelo.Params.OutputFlag = int(mostrar)
    modelo.Params.TimeLimit = limite_tiempo
    modelo.Params.Threads = SOLVER_SETTINGS["threads"]
    modelo.Params.MIPGap = SOLVER_SETTINGS["mip_gap"]
    modelo.Params.IntFeasTol = 1e-9

    # Resolucion del modelo
    modelo.optimize()

    # Registro de metricas computacionales
    resultado = {
        "solver": "Gurobi",
        "aeronaves": datos["n"],
        "variables": modelo.NumVars,
        "restricciones": modelo.NumConstrs,
        "estado": modelo.Status,
        "estado_texto": ESTADOS_GUROBI.get(
            modelo.Status, str(modelo.Status)
        ),
        "tiempo": modelo.Runtime,
        "nodos": modelo.NodeCount if modelo.IsMIP else 0,
        "objetivo": None,
        "gap": None,
        "factible": None,
        "adelanto_total": None,
        "retraso_total": None,
        "secuencia": [],
        "errores": []
    }

    # Recuperacion de la solucion
    if modelo.SolCount > 0:
        tiempos = [t[i].X for i in N]
        adelantos = [e[i].X for i in N]
        retrasos = [d[i].X for i in N]

        errores = validar_solucion(
            datos, tiempos, adelantos, retrasos
        )

        resultado["objetivo"] = modelo.ObjVal
        resultado["gap"] = modelo.MIPGap * 100 if modelo.IsMIP else None
        resultado["factible"] = not errores
        resultado["adelanto_total"] = sum(adelantos)
        resultado["retraso_total"] = sum(retrasos)
        resultado["errores"] = errores

        # Registro de la secuencia de aterrizaje
        secuencia = sorted(N, key=lambda i: tiempos[i])

        for posicion, i in enumerate(secuencia, start=1):
            resultado["secuencia"].append({
                "posicion": posicion,
                "aeronave": i + 1,
                "objetivo": T[i],
                "aterrizaje": tiempos[i],
                "adelanto": adelantos[i],
                "retraso": retrasos[i]
            })

    # Liberacion de recursos del solver
    modelo.dispose()

    return resultado


def mostrar_resultados(resultado):
    """Presenta las metricas y la secuencia de aterrizaje."""

    print("\nRESULTADOS DE OPTIMIZACION")
    print("Solver:", resultado["solver"])
    print("Cantidad de aeronaves:", resultado["aeronaves"])
    print("Cantidad de variables:", resultado["variables"])
    print("Cantidad de restricciones:", resultado["restricciones"])
    print("Estado del solver:", resultado["estado"])
    print("Descripcion del estado:", resultado["estado_texto"])
    print(f"Tiempo de computo: {resultado['tiempo']:.4f} segundos")

    if resultado["objetivo"] is not None:
        print(f"Funcion objetivo: {resultado['objetivo']:.2f}")
        if resultado["gap"] is not None:
            print(f"MIPGap: {resultado['gap']:.4f}%")
        else:
            print("MIPGap: No aplica")
        print(f"Nodos explorados: {resultado['nodos']:.0f}")
        print(f"Adelanto total: {resultado['adelanto_total']:.2f} s")
        print(f"Retraso total: {resultado['retraso_total']:.2f} s")

        print("\nSECUENCIA DE ATERRIZAJE")

        for avion in resultado["secuencia"]:
            print(
                f"Posicion: {avion['posicion']} | "
                f"Aeronave: {avion['aeronave']} | "
                f"Objetivo: {avion['objetivo']:.2f} s | "
                f"Aterrizaje: {avion['aterrizaje']:.2f} s | "
                f"Adelanto: {avion['adelanto']:.2f} s | "
                f"Retraso: {avion['retraso']:.2f} s"
            )

        print("\nVALIDACION DE LA SOLUCION")

        if resultado["factible"]:
            print("Solucion factible.")
            print("Todas las restricciones verificadas se cumplen.")
        else:
            for error in resultado["errores"]:
                print(error)

    elif resultado["estado"] == GRB.INFEASIBLE:
        print("El modelo no tiene soluciones factibles.")

    else:
        print("No se encontro una solucion.")


if __name__ == "__main__":
    # Configuracion de argumentos de ejecucion
    parser = argparse.ArgumentParser(
        description="Optimizacion de secuencias de aterrizaje"
    )

    parser.add_argument("--archivo", type=str)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--mix", type=str, default="balanced")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", type=str, default="literature")
    parser.add_argument("--tiempo", type=int, default=3600)

    args = parser.parse_args()

    # Carga o generacion de la instancia
    if args.archivo:
        datos = parse_orlib(args.archivo)
    else:
        datos = generate_instance(
            n=args.n,
            mix=args.mix,
            seed=args.seed,
            profile=args.profile
        )

    # Ejecucion y reporte de resultados
    resultado = resolver_gurobi(
        datos,
        limite_tiempo=args.tiempo
    )

    mostrar_resultados(resultado)
