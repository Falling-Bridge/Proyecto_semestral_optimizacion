"""Experimentacion computacional del modelo ASP (pista unica, Carriel Sur).

Modos de ejecucion
------------------
prueba
    Instancias pequenas y 30 segundos por instancia. Sirve para verificar que
    la tuberia completa (generacion, resolucion, validacion y registro) funciona.
definitivo
    Diseno experimental completo definido en ASP_instancias.py
    (SIZES x MIXES_USED x PROFILES_USED x REPLICAS) con 3600 segundos por
    instancia y la configuracion de solver de SOLVER_SETTINGS.

Caracteristicas
---------------
* Las instancias se generan una sola vez y se comparten entre ambos solvers.
* Los resultados se escriben de forma incremental (CSV con delimitador ';').
* La ejecucion es reanudable: las instancias ya registradas se omiten.
* Un error en una instancia se registra como fila y no detiene la campana.
"""

import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime
from itertools import product
from pathlib import Path

from ASP_instancias import (
    generate_instance,
    parse_orlib,
    download_orlib,
    SIZES,
    MIXES_USED,
    PROFILES_USED,
    REPLICAS,
    SOLVER_SETTINGS,
)

# Directorios del proyecto
BASE = Path(__file__).resolve().parent
INSTANCIAS = BASE / "instances" / "compartidas"
ORLIB = BASE / "instances" / "orlib"
RESULTADOS = BASE / "resultados"

# Campos del registro experimental (identicos para Gurobi y CPLEX)
CAMPOS = [
    "instancia",
    "solver",
    "origen",
    "grupo",
    "aeronaves",
    "mezcla",
    "perfil",
    "replica",
    "semilla",
    "limite_tiempo",
    "variables",
    "restricciones",
    "estado",
    "estado_texto",
    "objetivo",
    "tiempo",
    "gap",
    "nodos",
    "factible",
    "adelanto_total",
    "retraso_total",
    "errores",
]

# Configuracion de cada modo experimental
CONFIG_MODOS = {
    "prueba": {
        "tamanos": [10, 15, 20],
        "mezclas": ["balanced"],
        "perfiles": ["literature"],
        "replicas": 3,
        "limite": 30,
    },
    "definitivo": {
        "tamanos": [
            n for grupo in SIZES.values()
            for n in grupo
        ],
        "mezclas": list(MIXES_USED),
        "perfiles": list(PROFILES_USED),
        "replicas": REPLICAS,
        "limite": 3600,
    },
}


# --------------------------------------------------------------- utilidades
def formatear_duracion(segundos):
    """Convierte segundos a un texto legible (h, m, s)."""

    segundos = int(round(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas:
        return f"{horas}h {minutos:02d}m {segundos:02d}s"
    if minutos:
        return f"{minutos}m {segundos:02d}s"
    return f"{segundos}s"


def grupo_de(n):
    """Devuelve el grupo experimental (small/medium/large) de un tamano."""

    for grupo, tamanos in SIZES.items():
        if n in tamanos:
            return grupo
    return "referencia"


def semilla_instancia(n, mezcla, replica):
    """Semilla reproducible, identica para ambos perfiles y solvers."""

    return n * 1000 + MIXES_USED.index(mezcla) * 100 + replica


def nombre_instancia(n, mezcla, replica):
    """Identificador de la instancia sintetica."""

    return f"asp_{mezcla}_n{n}_r{replica}"


# ------------------------------------------------------- instancias del diseno
def instancia_valida(datos, n):
    """Verifica que un JSON recuperado tenga la estructura esperada."""

    if not isinstance(datos, dict):
        return False

    claves = (
        "earliest", "target", "latest", "pen_early",
        "pen_late", "sep"
    )

    if any(clave not in datos for clave in claves):
        return False

    if datos.get("n") != n:
        return False

    if any(len(datos[clave]) != n for clave in claves[:-1]):
        return False

    return (
        len(datos["sep"]) == n
        and all(len(fila) == n for fila in datos["sep"])
    )


def obtener_instancia(n, mezcla, perfil, replica):
    """Genera o recupera una instancia experimental reproducible."""

    semilla = semilla_instancia(n, mezcla, replica)
    nombre = nombre_instancia(n, mezcla, replica)

    # Organizacion de las instancias segun el perfil de separacion
    carpeta = INSTANCIAS / perfil
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.json"

    datos = None

    # Recuperacion de instancias previamente generadas
    if ruta.exists():
        try:
            with ruta.open("r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, json.JSONDecodeError):
            datos = None

        if not instancia_valida(datos, n):
            print(f"Instancia incompleta, se regenera: {ruta.name}")
            datos = None

    # Generacion de una instancia con los parametros seleccionados
    if datos is None:
        datos = generate_instance(
            n=n,
            mix=mezcla,
            seed=semilla,
            profile=perfil
        )

        with ruta.open("w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=2)

    return nombre, semilla, datos


# ------------------------------------------------------------ registro en CSV
def leer_encabezado(ruta):
    """Devuelve el encabezado del CSV o None si no existe o esta vacio."""

    if not ruta.exists() or ruta.stat().st_size == 0:
        return None

    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        return next(csv.reader(archivo, delimiter=";"), None)


def cargar_registros(ruta):
    """Identifica los experimentos previamente registrados."""

    # Verificacion de la existencia de resultados anteriores
    if not ruta.exists() or ruta.stat().st_size == 0:
        return set()

    # El encabezado debe coincidir para no desalinear las columnas
    encabezado = leer_encabezado(ruta)

    if encabezado != CAMPOS:
        raise ValueError(
            f"El archivo {ruta} fue generado con otro formato de columnas.\n"
            "Mueva o elimine ese archivo, o ejecute con --reiniciar."
        )

    # Recuperacion de identificadores para evitar registros duplicados.
    # Las filas con estado ERROR no cuentan: se reintentan en la proxima ejecucion.
    with ruta.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")

        return {
            (fila["instancia"], fila["perfil"])
            for fila in lector
            if str(fila.get("estado", "")).strip().upper() != "ERROR"
        }


def archivar_resultados(ruta):
    """Renombra un CSV previo para comenzar una campana desde cero."""

    if not ruta.exists():
        return

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    respaldo = ruta.parent / f"{ruta.stem}_bak_{marca}.csv"
    ruta.replace(respaldo)
    print(f"Resultados anteriores archivados en: {respaldo.name}")


def registrar_resultado(writer, archivo, resultado, metadata):
    """Almacena las metricas computacionales y de factibilidad."""

    # Seleccion de las metricas incluidas en el archivo CSV
    fila = {
        campo: resultado.get(campo)
        for campo in CAMPOS
    }

    # Incorporacion de parametros experimentales del escenario
    fila.update({
        clave: valor
        for clave, valor in metadata.items()
        if clave in CAMPOS
    })

    # Errores de validacion en una unica celda
    fila["errores"] = " | ".join(resultado.get("errores") or [])

    # Escritura y almacenamiento inmediato del registro
    writer.writerow(fila)
    archivo.flush()


def procesar_instancia(datos, metadata, writer, archivo, limite, resolver):
    """Resuelve una instancia y registra sus resultados.

    Devuelve True si la resolucion termino sin excepciones.
    """

    print(f"\nProcesando: {metadata['instancia']} | {metadata['perfil']}")
    print(f"Limite de tiempo: {limite} s")

    # Resolucion del modelo con el limite de tiempo establecido
    try:
        resultado = resolver(
            datos,
            limite_tiempo=limite,
            mostrar=False
        )
        correcto = True
    except Exception as error:
        # Un fallo aislado no debe detener la campana experimental
        traceback.print_exc()
        resultado = {
            "solver": metadata["solver"],
            "estado": "ERROR",
            "estado_texto": f"{type(error).__name__}: {error}",
            "errores": ["Excepcion durante la resolucion del modelo."]
        }
        correcto = False

    # Registro de resultados de la instancia
    registrar_resultado(
        writer, archivo, resultado, metadata
    )

    # Reporte resumido de las metricas de optimizacion
    if resultado.get("objetivo") is None:
        print("Estado:", resultado.get("estado_texto") or resultado.get("estado"))
        print("Sin solucion incumbente registrada.")
    else:
        print("Estado:", resultado.get("estado_texto") or resultado.get("estado"))
        print(f"Objetivo: {resultado['objetivo']:.2f}")

        if resultado.get("tiempo") is not None:
            print(f"Tiempo: {resultado['tiempo']:.2f} s")

        if resultado.get("gap") is not None:
            print(f"MIPGap: {resultado['gap']:.4f} %")

        print("Factibilidad:", "si" if resultado.get("factible") else "no")

    return correcto


def guardar_metadatos(ruta, modo, solver, config, version):
    """Deja constancia de la configuracion usada en la campana."""

    contenido = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "modo": modo,
        "solver": solver,
        "version_solver": version,
        "python": sys.version.split()[0],
        "limite_tiempo": config["limite"],
        "replicas": config["replicas"],
        "tamanos": config["tamanos"],
        "mezclas": config["mezclas"],
        "perfiles": config["perfiles"],
        "settings": dict(SOLVER_SETTINGS),
    }

    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, indent=2)


# ------------------------------------------------------------------- solvers
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


def version_solver(solver):
    """Version instalada del motor de optimizacion (para trazabilidad)."""

    try:
        if solver == "gurobi":
            import gurobipy as gp
            return ".".join(str(x) for x in gp.gurobi.version())

        import docplex
        return docplex.__version__
    except Exception:
        return "desconocida"


def configuracion(modo, limite=None, replicas=None, tamanos=None):
    """Combina el diseno del modo con los sobreescritos de la linea de comandos."""

    config = {
        clave: (list(valor) if isinstance(valor, list) else valor)
        for clave, valor in CONFIG_MODOS[modo].items()
    }

    if limite is not None:
        if limite <= 0:
            raise SystemExit("El limite de tiempo debe ser positivo.")
        config["limite"] = limite

    if replicas is not None:
        if replicas <= 0:
            raise SystemExit("El numero de replicas debe ser positivo.")
        config["replicas"] = replicas

    if tamanos:
        invalidos = [n for n in tamanos if n not in config["tamanos"]]

        if invalidos:
            raise SystemExit(
                f"Tamanos no incluidos en el modo {modo}: {invalidos}.\n"
                f"Disponibles: {config['tamanos']}"
            )

        config["tamanos"] = [
            n for n in config["tamanos"] if n in set(tamanos)
        ]

    return config


# --------------------------------------------------------------- campana
def ejecutar_experimentos(modo, solver, limite=None, replicas=None,
                          tamanos=None, reiniciar=False):
    """Ejecuta el diseno experimental con el solver seleccionado."""

    # Seleccion del motor de optimizacion
    resolver = obtener_solver(solver)
    version = version_solver(solver)
    config = configuracion(modo, limite, replicas, tamanos)

    print(f"\nSOLVER: {solver.upper()} (version {version}) | MODO: {modo}")
    print(
        f"Limite por instancia: {config['limite']} s | "
        f"Replicas: {config['replicas']} | "
        f"Perfiles: {', '.join(config['perfiles'])}"
    )
    print(f"Tamanos: {', '.join(str(n) for n in config['tamanos'])}")

    # Preparacion del directorio y archivo de resultados
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta_csv = RESULTADOS / f"{solver}_{modo}.csv"
    ruta_meta = RESULTADOS / f"{solver}_{modo}_meta.json"

    if reiniciar:
        archivar_resultados(ruta_csv)

    guardar_metadatos(ruta_meta, modo, solver, config, version)

    # Recuperacion de los experimentos ejecutados anteriormente
    try:
        procesados = cargar_registros(ruta_csv)
    except ValueError as error:
        raise SystemExit(str(error))

    # Determinacion de la necesidad de escribir el encabezado
    nuevo_archivo = leer_encabezado(ruta_csv) is None

    # Instancia de referencia de OR-Library (si esta disponible)
    ruta_orlib = ORLIB / "airland1.txt"

    if not ruta_orlib.exists():
        try:
            download_orlib(folder=str(ORLIB), ids=[1])
        except Exception as error:
            print(f"Aviso: no se pudo descargar airland1 ({error}).")
            print("La instancia de referencia se omitira.")

    usar_referencia = ruta_orlib.exists()
    datos_referencia = None

    if usar_referencia:
        try:
            datos_referencia = parse_orlib(ruta_orlib)
        except Exception as error:
            print(f"Aviso: no se pudo leer {ruta_orlib.name} ({error}).")
            print("La instancia de referencia se omitira.")
            usar_referencia = False

    # Planificacion de todas las tareas de la campana
    tareas = list(product(
        config["tamanos"],
        config["perfiles"],
        config["mezclas"],
        range(config["replicas"])
    ))

    pendientes = []
    omitidas = 0

    for n, perfil, mezcla, replica in tareas:
        nombre = nombre_instancia(n, mezcla, replica)

        if (nombre, perfil) in procesados:
            omitidas += 1
            continue

        pendientes.append((n, perfil, mezcla, replica, nombre))

    referencia_pendiente = (
        usar_referencia
        and ("airland1", "referencia") not in procesados
    )

    # La instancia de referencia tambien cuenta como registrada si ya existe
    if usar_referencia and not referencia_pendiente:
        omitidas += 1

    total = len(pendientes) + (1 if referencia_pendiente else 0)

    print(f"\nInstancias pendientes: {total} | ya registradas: {omitidas}")
    print(f"Resultados: {ruta_csv}")
    print(f"Metadatos: {ruta_meta}")

    if total == 0:
        print("\nNo hay instancias pendientes. Nada que ejecutar.")
        return

    inicio_campana = time.perf_counter()
    hechas = 0
    errores = 0
    fallos_consecutivos = 0

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
        if referencia_pendiente:
            metadata = {
                "instancia": "airland1",
                "solver": solver,
                "origen": "OR-Library",
                "grupo": "referencia",
                "perfil": "referencia",
                "limite_tiempo": config["limite"]
            }

            correcto = procesar_instancia(
                datos_referencia, metadata, writer, archivo,
                config["limite"], resolver
            )

            hechas += 1

            if not correcto:
                errores += 1

            print(
                f"Progreso: {hechas}/{total} | "
                f"transcurrido: {formatear_duracion(time.perf_counter() - inicio_campana)}"
            )

        # Evaluacion de las instancias sinteticas
        for n, perfil, mezcla, replica, nombre in pendientes:

            nombre, semilla, datos = obtener_instancia(
                n, mezcla, perfil, replica
            )

            # Registro de los parametros del escenario experimental
            metadata = {
                "instancia": nombre,
                "solver": solver,
                "origen": "Sintetica",
                "grupo": grupo_de(n),
                "aeronaves": n,
                "mezcla": mezcla,
                "perfil": perfil,
                "replica": replica,
                "semilla": semilla,
                "limite_tiempo": config["limite"]
            }

            # Resolucion y almacenamiento de resultados
            correcto = procesar_instancia(
                datos, metadata, writer, archivo,
                config["limite"], resolver
            )

            hechas += 1

            if correcto:
                fallos_consecutivos = 0
            else:
                errores += 1
                fallos_consecutivos += 1

            # Estimacion de tiempo restante
            transcurrido = time.perf_counter() - inicio_campana
            promedio = transcurrido / hechas
            restante = promedio * (total - hechas)

            print(
                f"Progreso: {hechas}/{total} | "
                f"transcurrido: {formatear_duracion(transcurrido)} | "
                f"estimado restante: {formatear_duracion(restante)}"
            )

            # Proteccion ante fallos sistematicos (licencia, solver, etc.)
            if fallos_consecutivos >= 3:
                print(
                    "\nTres instancias consecutivas fallaron. "
                    "Se detiene la campana para no registrar errores en serie."
                )
                print("Corrija el problema y vuelva a ejecutar: la campana se reanuda.")
                break

    duracion = time.perf_counter() - inicio_campana

    print("\nExperimentacion finalizada.")
    print(f"Instancias procesadas en esta ejecucion: {hechas}")
    print(f"Instancias omitidas (ya registradas): {omitidas}")
    print(f"Errores registrados: {errores}")
    print(f"Duracion: {formatear_duracion(duracion)}")
    print("Resultados almacenados en:", ruta_csv)


# --------------------------------------------------------------------- CLI
def main():
    """Punto de entrada de la experimentacion."""

    # Configuracion de argumentos de ejecucion
    parser = argparse.ArgumentParser(
        description="Experimentacion computacional del modelo ASP"
    )

    # Seleccion del modo de experimentacion
    parser.add_argument(
        "--modo",
        choices=["prueba", "definitivo"],
        default="prueba",
        help="prueba: instancias pequenas (30 s). definitivo: diseno completo (3600 s)."
    )

    # Seleccion del solver para la experimentacion
    parser.add_argument(
        "--solver",
        choices=["gurobi", "cplex", "ambos"],
        default="gurobi",
        help="Motor de optimizacion a utilizar."
    )

    # Sobreescritura del limite de tiempo por instancia
    parser.add_argument(
        "--limite",
        type=int,
        help="Limite de tiempo por instancia en segundos (sobreescribe el modo)."
    )

    # Sobreescritura del numero de replicas
    parser.add_argument(
        "--replicas",
        type=int,
        help="Replicas por combinacion tamano-mezcla (sobreescribe el modo)."
    )

    # Restriccion opcional a un subconjunto de tamanos
    parser.add_argument(
        "--tamanos",
        type=str,
        help="Subconjunto de tamanos separados por coma, por ejemplo: 10,15,20"
    )

    # Reinicio controlado de la campana
    parser.add_argument(
        "--reiniciar",
        action="store_true",
        help="Archiva el CSV existente y comienza la campana desde cero."
    )

    args = parser.parse_args()

    tamanos = None

    if args.tamanos:
        try:
            tamanos = [int(x) for x in args.tamanos.split(",") if x.strip()]
        except ValueError:
            raise SystemExit("--tamanos debe ser una lista de enteros: 10,15,20")

    # Ejecucion secuencial de los solvers seleccionados
    solvers = (
        ("gurobi", "cplex") if args.solver == "ambos" else (args.solver,)
    )

    for solver in solvers:
        ejecutar_experimentos(
            args.modo,
            solver,
            limite=args.limite,
            replicas=args.replicas,
            tamanos=tamanos,
            reiniciar=args.reiniciar
        )


if __name__ == "__main__":
    main()
