# EVIDENCIAS — Ítem 2 (Pregunta 2): agarre bajo la cola del broker

> Mapa de **qué archivo es la evidencia, qué lo genera, con qué comando y en qué
> equipo**. El paso a paso completo está en `ITEM_2.md`.
>
> **Ruta base:** todos los comandos se corren desde la **raíz del workspace
> `~/rb2_ws`** (donde están `herramientas/`, `analisis/` y `src/`).

## 0. Quién es quién

| Etiqueta | Equipo |
|---|---|
| **PC-LAYA** | Tu PC Windows (RTX 3050) que corre `laya-serve`. |
| **Jetson** | La Jetson (ROS 2 Humble): driver, broker, nodos y grabación. |
| **PC-integrante** | Las otras PC del equipo (clientes en paralelo). |
| **Equipo** | Trabajo manual: informe, tablas, videos. |
| **repo** | Fuente de código versionado (evidencia de implementación). |

---

## 1. Mapa de evidencias

| Evidencia | La genera | Comando (desde `~/rb2_ws`) | Dispositivo / quién | Responsable |
|---|---|---|---|---|
| `carga.csv` (40 poses reproducibles) | `herramientas/generar_carga.py` | `python herramientas/generar_carga.py --n 40 --semilla 7 --salida carga.csv` | PC cualquiera |  |
| `prediccion.md` (escrito ANTES de medir) | `herramientas/simular_corrida.py` | `python3 herramientas/simular_corrida.py --ambos --tau 12.0 --paso-max 1.6 --salida prediccion.md` | PC cualquiera |  |
| `evidencia/publicadores.txt` | `analisis/verificar_publicadores.py` | `python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt` | Jetson (antes de grabar) |  |
| `rechazos.csv` (causas `limite` / `workspace` / `paso`) | `broker.py` (lo escribe el broker) | `python3 herramientas/validar_rechazos.py --paso-max 1.2` | Jetson |  |
| fila `no_permitida` (rechazo antes de encolar) | orquestador (a construir) | — | Jetson |  |
| `demo_p2/` (bag de la demo) | `ros2 bag record` | `ros2 bag record -o demo_p2 /arm/queue_state /joint_states` | Jetson |  |
| `fifo/`, `prioridad/` (bags) | `ros2 bag record` | una corrida por política | Jetson |  |
| `fifo/queue_state.csv`, `fifo/joint_states.csv` (+ `prioridad/`) | `analisis/exportar_csv.py` o `exportar_csv_directo.py` | `python3 analisis/exportar_csv.py fifo/ --salida fifo/` | Jetson / PC |  |
| `comparacion_politicas.png` + resumen | `analisis/metricas.py` o `analisis/generar_datos_analisis.py` | `python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv --salida comparacion_politicas.png` | Jetson / PC |  |
| `intentos.csv` (10 intentos + `error_mm`) | orquestador / Equipo + `arm_broker.fk.fk` | snippet de abajo | PC cualquiera |  |
| Video de 3 min (cola + brazo) | grabación de pantalla | — | Equipo |  |

**Código que es evidencia de implementación** (lo pone el repo):

- `src/arm_broker/arm_broker/broker.py`, `politicas.py`, `cliente.py`, `fk.py`
- `src/arm_broker_interfaces/action/MoveArm.action`, `msg/QueueState.msg`
- `herramientas/generar_carga.py`, `validar_rechazos.py`, `simular_corrida.py`, `verificar_fk.py`
- `analisis/verificar_publicadores.py`, `exportar_csv.py`, `metricas.py`

---

## 2. Comandos exactos

**PC cualquiera** — traza y predicción previa:

```bash
python herramientas/generar_carga.py --n 40 --semilla 7 --salida carga.csv
python3 herramientas/simular_corrida.py --ambos --tau 12.0 --paso-max 1.6 \
  --salida prediccion.md
```

**Jetson** — verificaciones previas (broker recién arrancado):

```bash
mkdir -p evidencia

# 1) Publicador único de /joint_states (regla eliminatoria)
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt

# 2) Los 3 rechazos con causa -> escribe rechazos.csv
#    (el broker debe haberse arrancado con -p archivo_rechazos:=rechazos.csv)
python3 herramientas/validar_rechazos.py --paso-max 1.2
```

**Jetson** — grabación de bags:

```bash
ros2 bag record -o demo_p2     /arm/queue_state /joint_states
ros2 bag record -o fifo        /arm/queue_state /joint_states   # corrida FIFO
ros2 bag record -o prioridad   /arm/queue_state /joint_states   # corrida prioridad
```

**Jetson / PC** — exportar y comparar políticas:

```bash
python3 analisis/exportar_csv.py fifo/      --salida fifo/
python3 analisis/exportar_csv.py prioridad/ --salida prioridad/
python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv \
  --salida comparacion_politicas.png
# En Windows, sin ROS 2 (bags copiados), todo el pipeline de una vez:
python analisis\generar_datos_analisis.py
```

**PC cualquiera** — error de agarre con la FK (rellena `intentos.csv`):

```bash
python - <<'PY'
from arm_broker import fk
qs = [0, 0, 0, 0, 0, 0]   # q_solicitada del intento
qa = [0, 0, 0, 0, 0, 0]   # q_alcanzada del intento
x1, x2 = fk.fk(qs), fk.fk(qa)
print(round(sum((a - b) ** 2 for a, b in zip(x1, x2)) ** 0.5, 2), 'mm')
PY
```

---

## 3. Checklist de entrega (P2)

- [ ] `carga.csv` y `prediccion.md` (predicción **firmada antes** de medir).
- [ ] `evidencia/publicadores.txt` (exactamente 1 publicador `arm_broker`).
- [ ] `rechazos.csv` con las 3 causas + fila `no_permitida` del orquestador.
- [ ] `demo_p2/` (bag) y video de 3 min.
- [ ] `fifo/` y `prioridad/` (bags) → `queue_state.csv` → `comparacion_politicas.png`.
- [ ] `intentos.csv` con los 10 intentos, tasa de éxito y `error_mm` por FK.
