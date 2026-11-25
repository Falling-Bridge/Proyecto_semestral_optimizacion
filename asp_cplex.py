
import argparse
from docplex.mp.model import Model
from ASP_instancias import (
    generate_instance,
    parse_orlib,
    SOLVER_SETTINGS
)
from validacion import validar_solucion


def resolver_cplex(datos, limite_tiempo=3600, mostrar=True):
    """Resuelve el problema ASP de pista unica mediante CPLEX."""

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
    modelo = Model(name="ASP_Carriel_Sur")

    # Variables de decision continuas
    t = modelo.continuous_var_dict(N, lb=0, name="t")
    e = modelo.continuous_var_dict(N, lb=0, name="e")
    d = modelo.continuous_var_dict(N, lb=0, name="d")

    # Variables binarias de precedencia
    x = modelo.binary_var_dict(
        [(i, j) for i in N for j in N if i != j],
        name="x"
    )

    # Funcion objetivo
    modelo.minimize(
        modelo.sum(g[i] * e[i] + h[i] * d[i] for i in N)
    )

    # Restricciones de ventanas temporales
    modelo.add_constraints(
        (t[i] >= E[i] for i in N),
        names="tiempo_minimo"
    )

    modelo.add_constraints(
        (t[i] <= L[i] for i in N),
        names="tiempo_maximo"
    )

    # Balance entre tiempos asignados y objetivos
    modelo.add_constraints(
        (t[i] - T[i] == d[i] - e[i] for i in N),
        names="desviacion_temporal"
    )

    # Consistencia de las relaciones de precedencia
    modelo.add_constraints(
        (x[i, j] + x[j, i] == 1
         for i in N for j in N if i < j),
        names="precedencia"
    )

    # Constantes Big-M ajustadas a las ventanas temporales
    M = {
        (i, j): max(0, L[i] + S[i][j] - E[j])
        for i in N for j in N if i != j
    }

    # Restricciones de separacion temporal
    modelo.add_constraints(
        (t[j] - t[i] + M[i, j] * (1 - x[i, j]) >= S[i][j]
         for i in N for j in N if i != j),
        names="separacion"
    )

    # Configuracion del solver (identica para ambos solvers)
    modelo.parameters.timelimit = limite_tiempo
    modelo.parameters.threads = SOLVER_SETTINGS["threads"]
    modelo.parameters.mip.tolerances.mipgap = SOLVER_SETTINGS["mip_gap"]

    # Tolerancia de integralidad de las variables discretas
    modelo.parameters.mip.tolerances.integrality = 1e-9

    # Resolucion del modelo
    solucion = modelo.solve(log_output=mostrar)

    # Recuperacion de las metricas del solver
    detalles = modelo.solve_details
    es_mip = datos["n"] > 1

    # Registro de metricas computacionales
    resultado = {
        "solver": "CPLEX",
        "aeronaves": datos["n"],
        "variables": modelo.number_of_variables,
        "restricciones": modelo.number_of_constraints,
        "estado": detalles.status_code,
        "estado_texto": detalles.status,
        "tiempo": detalles.time,
        "nodos": detalles.nb_nodes_processed if es_mip else 0,
        "objetivo": None,
        "gap": None,
        "factible": None,
        "adelanto_total": None,
        "retraso_total": None,
        "secuencia": [],
        "errores": []
    }

    # Recuperacion de la solucion
    if solucion is not None:
        tiempos = [solucion.get_value(t[i]) for i in N]
        adelantos = [solucion.get_value(e[i]) for i in N]
        retrasos = [solucion.get_value(d[i]) for i in N]

        # Validacion de la factibilidad de la solucion
        errores = validar_solucion(
            datos, tiempos, adelantos, retrasos
        )

        resultado["objetivo"] = solucion.objective_value
        resultado["gap"] = (
            detalles.mip_relative_gap * 100 if es_mip else None
        )
        resultado["factible"] = not errores
        resultado["adelanto_total"] = sum(adelantos)
        resultado["retraso_total"] = sum(retrasos)
        resultado["errores"] = errores

        # Ordenamiento de aeronaves por tiempo de aterrizaje
        secuencia = sorted(N, key=lambda i: tiempos[i])

        # Registro de la secuencia de aterrizaje
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
    modelo.end()

    return resultado


def mostrar_resultados(resultado):
    """Presenta las metricas y la secuencia de aterrizaje."""

    # Informacion general del modelo
    print("\nRESULTADOS DE OPTIMIZACION")
    print("Solver:", resultado["solver"])
    print("Cantidad de aeronaves:", resultado["aeronaves"])
    print("Cantidad de variables:", resultado["variables"])
    print("Cantidad de restricciones:", resultado["restricciones"])
    print("Estado del solver:", resultado["estado"])
    print("Descripcion del estado:", resultado["estado_texto"])
    print(f"Tiempo de computo: {resultado['tiempo']:.4f} segundos")

    # Reporte de metricas de la solucion
    if resultado["objetivo"] is not None:
        print(f"Funcion objetivo: {resultado['objetivo']:.2f}")

        if resultado["gap"] is not None:
            print(f"MIPGap: {resultado['gap']:.4f}%")
        else:
            print("MIPGap: No aplica")

        print(f"Nodos explorados: {resultado['nodos']:.0f}")
        print(f"Adelanto total: {resultado['adelanto_total']:.2f} s")
        print(f"Retraso total: {resultado['retraso_total']:.2f} s")

        # Reporte de la secuencia de aterrizaje
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

        # Reporte de la validacion de factibilidad
        print("\nVALIDACION DE LA SOLUCION")

        if resultado["factible"]:
            print("Solucion factible.")
            print("Todas las restricciones verificadas se cumplen.")
        else:
            for error in resultado["errores"]:
                print(error)

    else:
        print("No se encontro una solucion.")
        print("Motivo:", resultado["estado_texto"])


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

    # Ejecucion del modelo
    resultado = resolver_cplex(
        datos,
        limite_tiempo=args.tiempo
    )

    # Presentacion de resultados
    mostrar_resultados(resultado)
