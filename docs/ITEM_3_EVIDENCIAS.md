# EVIDENCIAS — Ítem 3 (Pregunta 3): de la voz al movimiento

> Mapa de **qué archivo es la evidencia, qué lo genera, con qué comando y en qué
> equipo**. El paso a paso completo está en `ITEM_3.md`.
>
> **Ruta base:** todos los comandos se corren desde la **raíz del workspace
> `~/rb2_ws`** (donde están `herramientas/`, `analisis/` y `src/`).

## 0. Quién es quién

| Etiqueta | Equipo |
|---|---|
| **PC-LAYA** | Tu PC Windows (RTX 3050) que corre `laya-serve`. |
| **Jetson** | La Jetson (ROS 2 Humble): `transcriptor_voz`, nodos, grabación. |
| **PC-operador** | PC con el micrófono cómodo (graba el audio de las órdenes). |
| **Nube** | Google AI Studio (solo la transcripción). |
| **Equipo** | Trabajo manual: informe, tablas, videos. |
| **repo** | Fuente de código versionado (evidencia de implementación). |

---

## 1. Mapa de evidencias

| Evidencia | La genera | Comando (desde `~/rb2_ws`) | Dispositivo / quién | Responsable |
|---|---|---|---|---|
| `orden_0X.wav` (audio de cada orden) | `arecord` | `arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav` | Jetson / PC-operador |  |
| `evidencia/transcripcion_prueba.txt` | script de prueba con la clave (ITEM_3 §3.2) | ver §3.2 de `ITEM_3.md` | PC-LAYA |  |
| `transcripciones.csv` (audio + texto + método + tiempos) | `transcriptor_voz.py` (a construir) | `ros2 run arm_broker transcriptor_voz --ros-args -p fuente:=archivo -p ruta_audio:=orden_01.wav` | Jetson |  |
| Tabla de las 5 órdenes (se dijo → transcribió → decidió → hizo) | Equipo (demo real) | — | Equipo |  |
| `tiempos.csv` + `tiempos.png` (t0…t5 por etapa) | marcas del `transcriptor_voz`/orquestador + matplotlib | ver §3 | Jetson / PC |  |
| Video del modo texto sin internet | grabación de pantalla | — | Equipo |  |
| `transcriptor_voz.py` + entry point en `setup.py` | Equipo (a construir) | — | repo |  |
| Bag de la cadena hablada | `ros2 bag record` | igual que la P2 | Jetson |  |

**Código que es evidencia de implementación** (lo pone el repo):

- `src/arm_broker/arm_broker/transcriptor_voz.py` (nuevo)
- entry point `transcriptor_voz` en `src/arm_broker/setup.py`
- (aguas abajo) `interprete_ordenes.py`, `broker.py`, orquestador

---

## 2. Comandos exactos

**Jetson / PC-operador** — grabar el audio de cada orden:

```bash
# Lista micrófonos y ajusta -D plughw:X,Y al correcto:
arecord -l
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav
```

**PC-LAYA** — probar la transcripción antes de escribir el nodo (guarda evidencia):

```powershell
# El script de ITEM_3 §3.2 transcribe orden.wav con la clave en GOOGLE_API_KEY.
# Redirige la salida a evidencia\transcripcion_prueba.txt
```

**Jetson** — correr el nodo y registrar (clave SOLO en variable de entorno):

```bash
mkdir -p evidencia
export GOOGLE_API_KEY="AIzaTU_CLAVE"          # nunca en el código

ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p timeout_transcripcion_s:=5.0 -p google_model:=gemini-2.5-flash
# -> escribe transcripciones.csv (audio, texto, metodo google|teclado, tiempos)
```

**Jetson** — desglose de tiempos (marcas `t0…t5`):

```bash
# El nodo/orquestador loguea t0..t5; vuelca las etapas a un CSV y grafica:
python3 - <<'PY'
import csv
# filas = [(etapa, mediana_s), ...] tomadas de los logs
filas = [("captura_audio", 0.0), ("transcripcion", 0.0), ("decision", 0.0),
         ("cola", 0.0), ("percepcion", 0.0), ("ik", 0.0), ("planificacion", 0.0)]
with open("tiempos.csv", "w", newline="") as f:
    csv.writer(f).writerows([("etapa", "mediana_s")] + filas)
PY
# Figura de barras apiladas a partir de tiempos.csv -> tiempos.png
```

---

## 3. Checklist de entrega (P3)

- [ ] `transcriptor_voz.py` (con `timeout_transcripcion_s` y fallback a teclado)
      + entry point en `setup.py` y `colcon build` OK.
- [ ] `orden_0X.wav` y `transcripciones.csv` (audio + transcripción + método).
- [ ] Tabla de las 5 órdenes (incluye objeto inexistente y orden no permitida).
- [ ] `tiempos.csv` + `tiempos.png` con las etapas y las dos respuestas numéricas.
- [ ] Video demostrando el **modo texto con internet desconectado**.
