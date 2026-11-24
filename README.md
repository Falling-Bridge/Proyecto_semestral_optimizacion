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

- **ASP_instancias.py:** Generación de instancias sintéticas y lectura de instancias de OR-Library.
- **gurobi.py:** Implementación del modelo matemático utilizando Gurobi.
- **asp_cplex.py:** Implementación del modelo matemático utilizando CPLEX.
- **validacion.py:** Verificación del cumplimiento de las restricciones en las soluciones obtenidas.
- **experimentos.py:** Ejecución automática de experimentos utilizando ambos solvers.


## Reglas para Ejecutar el Código

### 1. Instalación de dependencias

Para instalar las bibliotecas necesarias, ejecute en la terminal:

```bash
pip install -r requirements.txt
```

### 2. Ejecución del modelo en Gurobi

Para ejecutar el modelo utilizando Gurobi:

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

### 5. Experimentación (Temporal)

Actualmente, la experimentación cuenta con una configuración temporal que permite verificar el funcionamiento de ambos modelos.

Para ejecutar los experimentos utilizando Gurobi:

```bash
python experimentos.py --modo prueba --solver gurobi
```

Para ejecutar los experimentos utilizando CPLEX:

```bash
python experimentos.py --modo prueba --solver cplex
```

Si desea ejecutar los experimentos con ambos solvers:

```bash
python experimentos.py --modo prueba --solver ambos
```

Por el momento, el programa cuenta con dos modos de ejecución:

- **prueba:** Utiliza instancias pequeñas y un tiempo límite de 30 segundos por instancia.
- **definitivo:** Utiliza el conjunto completo de instancias sintéticas del diseño experimental y un tiempo límite de 3600 segundos por instancia.


Los resultados se guardarán automáticamente en formato CSV dentro de la carpeta resultados. Ambos solvers utilizan las mismas instancias para que los resultados puedan ser comparados bajo las mismas condiciones.

