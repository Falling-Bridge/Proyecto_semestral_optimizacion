# Proyecto Semestral - Optimización


_Luis Martinez_<br>
_2023427985_

_Lucas Morales_<br>
_2023441490_

_Diego Alday_<br>
_x_

_Valentina Serón_<br>
_x_

_Ignacio Soto_<br>
_2023447412_
# Sobre el entregable
Este proyecto escrito en Python implementa un modelo de optimización para el problema de programación de aterrizajes de aeronaves (Aircraft Scheduling Problem o ASP), considerando una única pista en el aeropuerto Carriel Sur.

El objetivo del modelo es minimizar las penalizaciones asociadas a los adelantos y retrasos de las aeronaves respecto a sus tiempos objetivos de aterrizaje, respetando las ventanas temporales y las restricciones de separación entre aeronaves.

El mismo modelo matemático fue implementado utilizando dos solvers: Gurobi y CPLEX.

## Archivos del proyecto

- **ASP_instancias.py:** Generación de instancias sintéticas (tamaños, mezclas de aeronaves y perfiles de separación), descarga y lectura de instancias de OR-Library, y definición del diseño experimental.
- **gurobi.py:** Implementación del modelo matemático utilizando Gurobi.
- **asp_cplex.py:** Implementación del modelo matemático utilizando CPLEX.
- **validacion.py:** Verificación del cumplimiento de las restricciones en las soluciones obtenidas.
- **experimentos.py:** Ejecución automática de la campaña experimental completa con uno o ambos solvers.


## Reglas para Ejecutar el Código

### 1. Instalación de dependencias

Para instalar las bibliotecas necesarias, ejecute en la terminal:

```bash
pip install -r requirements.txt
```

Gurobi y CPLEX requieren además una licencia válida instalada en el equipo. La licencia académica de Gurobi se activa con `grbgetkey`; CPLEX funciona con la edición Community incluida en el paquete `docplex`/`cplex` (con límite de tamaño de modelo).

### 2. Ejecución del modelo en Gurobi

Para ejecutar el modelo utilizando Gurobi con una instancia sintética:

```bash
python gurobi.py
```

También se pueden modificar los parámetros de la instancia, como la cantidad de aeronaves, la distribución de categorías, la semilla y el tiempo límite de ejecución.

```bash
python gurobi.py --n 20 --mix balanced --seed 42 --tiempo 60
```

### 3. Ejecución del modelo en CPLEX

Para ejecutar el modelo utilizando CPLEX:

```bash
python asp_cplex.py
```

Al igual que en Gurobi, se pueden modificar los parámetros de la instancia.

```bash
python asp_cplex.py --n 20 --mix balanced --seed 42 --tiempo 60
```

Ambos modelos mostrarán en la terminal el valor de la función objetivo, el tiempo de cómputo, el MIPGap, la secuencia de aterrizaje de las aeronaves y la validación de la solución obtenida.

### 4. Ejecución de instancias de OR-Library

Si desea utilizar una instancia de OR-Library previamente descargada, ejecute:

```bash
python gurobi.py --archivo instances/orlib/airland1.txt
```

O utilizando CPLEX:

```bash
python asp_cplex.py --archivo instances/orlib/airland1.txt
```

Para descargar automáticamente las 13 instancias de OR-Library (`airland1.txt` a `airland13.txt`) y generar el diseño experimental en formato de texto, ejecute:

```bash
python ASP_instancias.py
```

### 5. Experimentación: modo `prueba` y modo `definitivo`

El script `experimentos.py` ejecuta la campaña experimental de forma automática. Usa exactamente las mismas instancias para Gurobi y CPLEX, de modo que los resultados sean comparables.

#### 5.1 Modos disponibles

| Modo | Instancias | Límite por instancia | Uso |
| --- | --- | --- | --- |
| `prueba` | 3 tamaños (10, 15, 20) × mezcla `balanced` × perfil `literature` × 3 réplicas | 30 s | Verificar que toda la tubería funciona |
| `definitivo` | 9 tamaños (10 a 250) × 4 mezclas × 2 perfiles × 5 réplicas = 360 instancias | 3600 s | Campaña final del informe |

Ambos modos incluyen además la instancia de referencia `airland1` de OR-Library (si está disponible o se puede descargar).

#### 5.2 Ejecución del modo definitivo

Con Gurobi:

```bash
python experimentos.py --modo definitivo --solver gurobi
```

Con CPLEX:

```bash
python experimentos.py --modo definitivo --solver cplex
```

Con ambos solvers de forma secuencial (Gurobi y luego CPLEX):

```bash
python experimentos.py --modo definitivo --solver ambos
```

#### 5.3 Ejecución del modo de prueba

```bash
python experimentos.py --modo prueba --solver gurobi
python experimentos.py --modo prueba --solver cplex
python experimentos.py --modo prueba --solver ambos
```

#### 5.4 Opciones de línea de comandos

| Opción | Descripción |
| --- | --- |
| `--modo {prueba,definitivo}` | Modo experimental (por defecto `prueba`). |
| `--solver {gurobi,cplex,ambos}` | Motor de optimización (por defecto `gurobi`). |
| `--limite SEGUNDOS` | Sobreescribe el límite de tiempo por instancia del modo. |
| `--replicas N` | Sobreescribe el número de réplicas por combinación tamaño–mezcla. |
| `--tamanos 10,15,20` | Ejecuta solo un subconjunto de los tamaños del modo. |
| `--reiniciar` | Archiva el CSV existente (con marca de tiempo) y empieza de cero. |

#### 5.5 Reanudación y ejecución por tramos

La campaña definitiva puede durar muchas horas, por lo que la ejecución es **reanudable**: cada resultado se escribe inmediatamente en el CSV y, al volver a lanzar el mismo comando, las instancias ya registradas se omiten automáticamente.

Para repartir el trabajo en tramos (por ejemplo, primero los tamaños pequeños y luego los grandes):

```bash
python experimentos.py --modo definitivo --solver gurobi --tamanos 10,15,20,30
python experimentos.py --modo definitivo --solver gurobi --tamanos 50,100,150,200,250
```

Si desea repetir una campaña desde cero, use `--reiniciar` (el CSV anterior se conserva como `*_bak_AAAAMMDD_HHMMSS.csv`).

#### 5.6 Resultados generados

Los archivos se guardan en la carpeta `resultados/`:

- `resultados/<solver>_<modo>.csv`: una fila por instancia resuelta, con delimitador `;` y codificación UTF-8 con BOM (se abre directamente en Excel).
- `resultados/<solver>_<modo>_meta.json`: configuración usada en la última ejecución (modo, límite de tiempo, réplicas, tamaños, mezclas, perfiles, tolerancias y versiones del solver y de Python).

Columnas del CSV: `instancia`, `solver`, `origen`, `grupo`, `aeronaves`, `mezcla`, `perfil`, `replica`, `semilla`, `limite_tiempo`, `variables`, `restricciones`, `estado`, `estado_texto`, `objetivo`, `tiempo`, `gap`, `nodos`, `factible`, `adelanto_total`, `retraso_total`, `errores`.

Un error aislado durante la resolución (por ejemplo, falta de memoria) queda registrado como fila con `estado = ERROR` y no detiene la campaña. Si fallan tres instancias consecutivas, la ejecución se detiene para evitar registrar errores en serie; al corregir el problema basta con volver a lanzar el mismo comando. Las filas con `estado = ERROR` se reintentan automáticamente en la siguiente ejecución; por eso, al analizar los resultados conviene filtrar `estado != ERROR` (puede quedar la fila histórica del error junto a la reintentada con éxito).

#### 5.7 Advertencias sobre el modo definitivo

- Los tamaños 150, 200 y 250 son **pruebas de estrés computacional**: comprimen muchas aeronaves en un horizonte breve y no representan una operación realista de Carriel Sur. En `n = 250` el modelo tiene 62.250 variables binarias, por lo que la construcción y resolución pueden consumir varios GB de memoria.
- Con un límite de 3600 s por instancia, el peor caso de la campaña completa es cercano a 360 horas por solver. Se recomienda ejecutar por tramos con `--tamanos` y revisar periódicamente el CSV.
- Para conservar el registro de la terminal durante una ejecución larga, redirija la salida a un archivo (PowerShell):

  ```powershell
  python experimentos.py --modo definitivo --solver ambos *> resultados\log_definitivo.txt
  ```

- Gurobi y CPLEX usan la misma configuración de solver (`SOLVER_SETTINGS` en `ASP_instancias.py`): 1 hilo y MIPGap de `1e-4`. El límite de tiempo se fija por modo (o con `--limite`).
