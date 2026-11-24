def validar_solucion(datos, tiempos, adelantos, retrasos):
    """Verifica la factibilidad de una solucion del modelo ASP."""

    n = datos["n"]
    E = datos["earliest"]
    T = datos["target"]
    L = datos["latest"]
    S = datos["sep"]

    errores = []
    tolerancia = 1e-5

    # Verificacion de ventanas temporales
    for i in range(n):
        if tiempos[i] < E[i] - tolerancia:
            errores.append(
                f"Aeronave {i + 1}: aterrizaje fuera del limite inferior."
            )

        if tiempos[i] > L[i] + tolerancia:
            errores.append(
                f"Aeronave {i + 1}: aterrizaje fuera del limite superior."
            )

    # Verificacion de adelantamientos y retrasos
    for i in range(n):
        adelanto = max(0, T[i] - tiempos[i])
        retraso = max(0, tiempos[i] - T[i])

        if abs(adelantos[i] - adelanto) > tolerancia:
            errores.append(
                f"Aeronave {i + 1}: adelantamiento incorrecto."
            )

        if abs(retrasos[i] - retraso) > tolerancia:
            errores.append(
                f"Aeronave {i + 1}: retraso incorrecto."
            )

    # Verificacion de separaciones temporales
    secuencia = sorted(range(n), key=lambda i: tiempos[i])

    for posicion, i in enumerate(secuencia):
        for j in secuencia[posicion + 1:]:
            diferencia = tiempos[j] - tiempos[i]

            if diferencia < S[i][j] - tolerancia:
                errores.append(
                    f"Separacion insuficiente entre las aeronaves "
                    f"{i + 1} y {j + 1}. "
                    f"Separacion requerida: {S[i][j]:.8f} s | "
                    f"Separacion obtenida: {diferencia:.8f} s | "
                    f"Incumplimiento: {S[i][j] - diferencia:.8f} s"
                )

    return errores