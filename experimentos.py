import argparse
import csv
import json
from pathlib import Path
from itertools import product

from ASP_instancias import (
    generate_instance,
    parse_orlib,
    SIZES,
    MIXES_USED,
    PROFILES_USED,
    REPLICAS
)

# Directorios del proyecto
BASE = Path(__file__).resolve().parent
INSTANCIAS = BASE / "instances" / "compartidas"
RESULTADOS = BASE / "resultados"

# Campos del registro experimental
CAMPOS = [
    "instancia",
    "solver",
    "origen",
    "aeronaves",
    "mezcla",
    "perfil",
    "replica",
    "semilla",
    "limite_tiempo",
    "variables",
    "restricciones",
    "estado",
    "objetivo",
    "tiempo",
    "gap",
    "nodos",
    "factible",
    "adelanto_total",
    "retraso_total",
    "errores"
]


def obtener_instancia(n, mezcla, perfil, replica):
    """Genera o recupera una instancia experimental reproducible."""

    # Identificacion de la instancia y semilla reproducible
    semilla = n * 1000 + MIXES_USED.index(mezcla) * 100 + replica
    nombre = f"asp_{mezcla}_n{n}_r{replica}"

    # Organizacion de las instancias segun el perfil de separacion
    carpeta = INSTANCIAS / perfil
    carpeta.mkdir(parents=True, exist_ok=True)

    ruta = carpeta / f"{nombre}.json"

    # Recuperacion de instancias previamente generadas
    if ruta.exists():
        with ruta.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    else:
        # Generacion de una instancia con los parametros seleccionados
        datos = generate_instance(
            n=n,
            mix=mezcla,
            seed=semilla,
            profile=perfil
        )

        # Almacenamiento de los parametros para su reutilizacion
        with ruta.open("w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=2)

    return nombre, semilla, datos


def cargar_registros(ruta):
    """Identifica los experimentos previamente registrados."""

    # Verificacion de la existencia de resultados anteriores
    if not ruta.exists() or ruta.stat().st_size == 0:
        return set()

    # Recuperacion de identificadores para evitar registros duplicados
    with ruta.open("r", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")

        return {
            (fila["instancia"], fila["perfil"])
            for fila in lector
        }


def registrar_resultado(writer, archivo, resultado, metadata):
    """Almacena las metricas computacionales y de factibilidad."""

    # Seleccion de las metricas incluidas en el archivo CSV
    fila = {
        campo: resultado.get(campo)
        for campo in CAMPOS
    }

    # Incorporacion de errores de validacion y parametros experimentales
    fila["errores"] = " | ".join(resultado["errores"])
    fila.update(metadata)

    # Escritura y almacenamiento inmediato del registro
    writer.writerow(fila)
    archivo.flush()


def procesar_instancia(datos, metadata, writer, archivo, limite, resolver):
    """Resuelve una instancia y registra sus resultados."""

    print(f"\nProcesando: {metadata['instancia']}")
    print("Perfil:", metadata["perfil"])

    # Resolucion del modelo con el limite de tiempo establecido
    resultado = resolver(
        datos,
        limite_tiempo=limite,
        mostrar=False
    )

    # Registro de resultados de la instancia
    registrar_resultado(
        writer, archivo, resultado, metadata
    )

    # Reporte resumido de las metricas de optimizacion
    print("Estado:", resultado["estado"])
    print("Objetivo:", resultado["objetivo"])
    print("Tiempo:", resultado["tiempo"])
    print("MIPGap (%):", resultado["gap"])
    print("Factibilidad:", resultado["factible"])


def obtener_solver(solver):
    """Recupera la funcion de resolucion del solver seleccionado."""

    # Importacion exclusiva del motor de optimizacion requerido
    if solver == "gurobi":
        from gurobi import resolver_gurobi
        return resolver_gurobi
    if solver == "cplex":
        from asp_cplex import resolver_cplex
        return resolver_cplex
    raise ValueError(f"Solver no reconocido: {solver}")


def ejecutar_experimentos(modo, solver):
    """Ejecuta el diseno experimental con el solver seleccionado."""

    # Seleccion del motor de optimizacion
    resolver = obtener_solver(solver)
    print(f"\nSOLVER: {solver.upper()} | MODO: {modo}")

    # Configuracion de la experimentacion preliminar
    if modo == "prueba":
        tamanos = [10, 15, 20]
        mezclas = ["balanced"]
        perfiles = ["literature"]
        replicas = 3
        limite = 30
    else:
        # Configuracion del diseno experimental completo
        tamanos = [
            n for grupo in SIZES.values()
            for n in grupo
        ]
        mezclas = MIXES_USED
        perfiles = PROFILES_USED
        replicas = REPLICAS
        limite = 3600

    # Preparacion del directorio y archivo de resultados
    RESULTADOS.mkdir(parents=True, exist_ok=True)

    ruta_csv = RESULTADOS / f"{solver}_{modo}.csv"

    # Recuperacion de los experimentos ejecutados anteriormente
    procesados = cargar_registros(ruta_csv)

    # Determinacion de la necesidad de escribir el encabezado
    nuevo_archivo = (
        not ruta_csv.exists() or ruta_csv.stat().st_size == 0
    )

    # Apertura en modo de adicion para conservar los registros existentes
    with ruta_csv.open(
        "a", newline="", encoding="utf-8-sig"
    ) as archivo:

        writer = csv.DictWriter(
            archivo,
            fieldnames=CAMPOS,
            delimiter=";"
        )

        if nuevo_archivo:
            writer.writeheader()

        # Evaluacion de la instancia de referencia
        if ("airland1", "referencia") not in procesados:

            datos = parse_orlib(
                BASE / "instances" / "orlib" / "airland1.txt"
            )

            # Identificacion de la instancia de referencia
            metadata = {
                "instancia": "airland1",
                "origen": "OR-Library",
                "perfil": "referencia",
                "limite_tiempo": limite
            }

            procesar_instancia(
                datos, metadata, writer, archivo, limite, resolver
            )

        # Combinaciones de perfiles, tamanos, mezclas y replicas
        combinaciones = product(
            perfiles, tamanos, mezclas, range(replicas)
        )

        # Evaluacion de las instancias sinteticas
        for perfil, n, mezcla, replica in combinaciones:

            nombre, semilla, datos = obtener_instancia(
                n, mezcla, perfil, replica
            )

            # Omision de instancias registradas en ejecuciones anteriores
            if (nombre, perfil) in procesados:
                print(f"Instancia registrada: {nombre} | {perfil}")
                continue

            # Registro de los parametros del escenario experimental
            metadata = {
                "instancia": nombre,
                "origen": "Sintetica",
                "mezcla": mezcla,
                "perfil": perfil,
                "replica": replica,
                "semilla": semilla,
                "limite_tiempo": limite
            }

            # Resolucion y almacenamiento de resultados
            procesar_instancia(
                datos, metadata, writer, archivo, limite, resolver
            )

    print("\nExperimentacion finalizada.")
    print("Resultados almacenados en:", ruta_csv)


if __name__ == "__main__":
    # Configuracion de argumentos de ejecucion
    parser = argparse.ArgumentParser(
        description="Experimentacion computacional del modelo ASP"
    )

    # Seleccion del modo de experimentacion
    parser.add_argument(
        "--modo",
        choices=["prueba", "definitivo"],
        default="prueba"
    )

    # Seleccion del solver para la experimentacion
    parser.add_argument(
        "--solver",
        choices=["gurobi", "cplex", "ambos"],
        default="gurobi"
    )

    args = parser.parse_args()

    # Ejecucion secuencial de los solvers seleccionados
    solvers = ("gurobi", "cplex") if args.solver == "ambos" else (args.solver,)
    for solver in solvers:
        ejecutar_experimentos(args.modo, solver)
