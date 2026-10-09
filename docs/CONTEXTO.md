# CONTEXTO — Gran Reto JetCobot (Parcial) + Reto Brazo 2 (RB-2)

> Guía general del proyecto: qué problema se resuelve, qué se busca en el Reto 2,
> qué pide el Parcial, cómo está organizado el repositorio y qué corre en cada
> dispositivo. Las guías de ejecución por pregunta están en
> [`ITEM_1.md`](ITEM_1.md), [`ITEM_2.md`](ITEM_2.md) e [`ITEM_3.md`](ITEM_3.md).

---

## 1. El problema, en una página

Un brazo robótico **JetCobot** (6 grados de libertad, controlado desde una
Jetson con ROS 2 Humble y el driver `sync_plan_nx`) debe atender **órdenes en
español, escritas o habladas**, que llegan de varias personas **al mismo tiempo**.
Nadie escribe coordenadas: se dicta *"agarra el cubo rojo"* y el sistema tiene
que convertir eso en movimiento, **sin quedarse nunca esperando** y con
**tiempos de respuesta conocidos y medidos**.

Ese sistema se construyó en dos etapas que conviven en este mismo repositorio:

| Etapa | Nombre | Qué aporta | Estado |
|---|---|---|---|
| Anterior | **RB-2 (Reto Brazo 2)** | La cinemática directa, el **broker** de acceso exclusivo al brazo y las **políticas de cola** (FIFO vs prioridad con envejecimiento) | Implementado en `src/` |
| Actual | **Parcial — Gran Reto JetCobot** | El servicio de interpretación de frases (LAYA), la cadena completa de agarre autónomo y la **voz** como entrada | Parcialmente implementado (ver §6) |

**La idea central:** el examen *no* pide reimplementar el brazo ni el broker
(el enunciado prohíbe reemplazar lo del RB-2). Pide **encadenar** lo que ya
existe: `frase → decisión tipada (LAYA) → cola de prioridad del broker →
cámara → cinemática inversa → MoveIt2 → gripper`, y medirlo con evidencia.

---

## 2. Qué se busca en el Reto 2 (RB-2) — lo que ya está hecho

El RB-2 se dividió en tres ítems, y todo está implementado en este repo:

### Ítem 1 — Cinemática directa (`src/arm_broker/arm_broker/fk.py`)
- Tabla **Denavit-Hartenberg** del kit (6 eslabones), `fk(q)` devuelve la
  posición `(x,y,z)` en mm del efector.
- **Validaciones** que después usa el broker:
  `dentro_de_limites()` (rangos de cada articulación),
  `dentro_del_workspace()` (`z >= 0` y alcance 3D entre 80 y 480 mm),
  `paso_articular(q_desde, q_hasta)` (salto máximo en rad).
- Verificación física: `herramientas/verificar_fk.py` (corre **en la Jetson**
  con `pymycobot`, compara `fk(q)` contra `get_coords()`; criterio: error ≤ 10 mm).

### Ítem 2 — Broker de acceso exclusivo (`src/arm_broker/arm_broker/broker.py`)
- **Un solo nodo** (`arm_broker`) publica `/joint_states`; los clientes solo
  envían goals a la acción `move_arm`.
- Admisión validada con FK **antes** de encolar (límites → workspace → paso →
  cola llena), con **causa y motivo** escritos en `rechazos.csv`.
- **Worker único** en un grupo `MutuallyExclusiveCallbackGroup`: nunca hay dos
  goals en ejecución a la vez (exclusión mutua por construcción).
- Telemetría en `/arm/queue_state` a 5 Hz (`QueueState.msg`).

### Ítem 3 — Políticas de cola y métricas (`src/arm_broker/arm_broker/politicas.py`)
- **FIFO** (línea base) vs **prioridad con envejecimiento**:
  `puntuación = priority + espera_s / tau`, con `tau = 12.0` para las
  mediciones; desempate por pedido más antiguo.
- Predicción **antes** de medir: `herramientas/simular_corrida.py` → `prediccion.md`.
- Medición: grabar bags (`fifo/`, `prioridad/`), exportar a CSV
  (`analisis/exportar_csv.py` o `exportar_csv_directo.py`) y calcular
  mediana, p95, inanición y equidad de Jain (`analisis/metricas.py` o
  `metricas_directo.py`).

Documentación de todo esto: `README.md` (ítems 2 y 3), `GUIA_SIN_LAYA.md`
(cómo mover el brazo sin LAYA), `TERMINALES.md` (bags y métricas),
`PASOS.txt` (orden de arranque, con avisos de que está desactualizado).

---

## 3. Qué pide el Parcial (del docx `Parcial_Gran_Reto_JetCobot.docx`)

**Examen parcial — Gran Reto JetCobot.** Robótica (08079), Semestre 2026-2.
Secciones S-003/S-004, 4 horas, grupal (máx. 4 integrantes), 20 puntos.
Equipo N.º 1: Samuel Alexander Criollo Arevalo, Joaquín Carrasco Quispe,
Maykol Bernaldo Vega, Wilmer.

| Pregunta | Tema | Pts | Qué hay que construir/probar |
|---|---|---|---|
| **1** | Servicio de interpretación de órdenes | 6 | Nodo `interprete_ordenes` con servicio `/interpretar_orden` que traduce una frase a una **decisión tipada** (acción, objeto, color, prioridad, permitido) consultando a **LAYA** por HTTP, con **tiempo límite** y respaldo por palabras clave; medir **mediana y p95** sobre 50 frases separando **red** de **cómputo**, en **calma y bajo carga**, y reportar **exactitud** de LAYA vs clasificador. |
| **2** | Agarre autónomo bajo la cola del broker | 8 | La cadena completa: decisión → **cola de prioridad del broker** → cámara → cinemática inversa → MoveIt2 → gripper. La prioridad viene del modelo (no se escribe a mano), solo el worker del broker publica al brazo, las órdenes `no permitidas` se rechazan **antes de encolarse** con causa, **10 intentos** de agarre con tasa de éxito y **error por FK**, más bag + video de 3 min. |
| **3** | De la voz al movimiento | 6 | Nodo `transcriptor_voz` (audio → texto en español vía **Google AI Studio**) que alimenta al servicio de la P1; **timeout → modo texto por teclado**; 5 órdenes habladas con su tabla (dicho/transcrito/decisión/brazo); **desglose de tiempos** por etapas con tabla y figura; demo con internet desconectado. |

### Reglas eliminatorias del enunciado (aplican a todo)
1. **El examen se hace sobre el JetCobot propio y el broker del RB-2**: no se
   puede sustituir por una implementación nueva.
2. **LAYA no es un nodo ROS 2**: se habla por HTTP con la IP/puerto/preset que
   entrega el docente (o con el servidor que levantes tú, ver §5).
3. **La clave de Google AI Studio va en variable de entorno**; publicarla en
   el código descuenta puntos.
4. **Solo el worker del broker publica comandos al brazo**: si otro nodo
   publica en `/joint_states`, se pierde **íntegro** el puntaje de la P2.
5. **Toda afirmación necesita evidencia**: `ros2 bag`, CSV o video.
6. **Antes de cada medición hay que escribir el valor esperado**; la
   diferencia predicho vs medido se califica.
7. **`ROS_DOMAIN_ID` del equipo**: un equipo que mueva el brazo de otro pierde
   el puntaje de la pregunta en curso.

### Arquitectura de máquinas (Figura 1 del docx)
```
┌────────────────────────┐      HTTP (red local)     ┌──────────────────────────┐
│  Windows del lab (o    │  ◄─────────────────────── │  JETSON del equipo       │
│  tu PC con LAYA)       │   /v1/systemone           │  grafo ROS 2 propio      │
│  modelo LAYA (GPU)     │                           │  broker · clientes ·     │
└────────────────────────┘                           │  interprete_ordenes ·    │
                                                     │  transcriptor_voz ·      │
┌────────────────────────┐   Gemini API (internet)   │  sync_plan_nx (driver)   │
│  Google AI Studio      │ ◄──────────────────────── │                          │
│  (transcripción P3)    │                           └──────────────────────────┘
└────────────────────────┘                                        │
                                                                  ▼
                                                          JetCobot (brazo)
```
Cinco hechos que dice el docx y conviene no olvidar:
- LAYA **no aparece** en `ros2 node list` ni se descubre por Discovery Server.
- `interprete_ordenes` es el **único** punto de contacto con la máquina Windows.
- LAYA es **compartido**: la latencia de la demostración no será la de calma.
- El tiempo medido **incluye red**; hay que separar red y cómputo.
- La transcripción depende de internet; **la decisión y el movimiento, no**.

---

## 4. Arquitectura y orden de carpetas del repositorio

```
carrprp/                                  ← raíz del repo (GitHub: rGsmueL/parcial)
│
├── Parcial_Gran_Reto_JetCobot.docx       ← enunciado oficial del examen
├── README.md                             ← RB-2: arquitectura, políticas, admisión,
│                                           traza, verificación, red, DH, predicción
├── README_PARCIAL.md                     ← Pregunta 1: cómo instalar, compilar y
│                                           medir el nodo interprete_ordenes
│                                           (antes se llamaba README_RETO2.md)
├── GUIA_SIN_LAYA.md                      ← qué hacer HOY sin LAYA ni IP: mover el
│                                           brazo, Ítem 1 con clasificador local,
│                                           tabla de placeholders por rellenar
├── TERMINALES.md                         ← comandos de terminal para grabar bags y
│                                           calcular métricas (usa config/equipo.env,
│                                           archivo que NO existe por que ya se hacer 
|                                           de forma manueal con el PASOS.txt, ver §6)
├── PASOS.txt                             ← orden de arranque (cliente, driver,
│                                           broker, bags); la sección final de
│                                           métricas está desactualizada
├── carga.csv                             ← traza oficial de 40 poses (semilla 7)
│
├── docs/                                 ← ESTAS GUÍAS (nuevas)
│   ├── CONTEXTO.md                       ← este archivo
│   ├── ITEM_1.md                         ← Pregunta 1: interprete_ordenes + LAYA
│   ├── ITEM_2.md                         ← Pregunta 2: cadena bajo la cola
│   └── ITEM_3.md                         ← Pregunta 3: voz → movimiento
│
├── src/                                  ← paquetes ROS 2 (el workspace se clona
│   │                                       o enlaza en la Jetson/PC con ROS 2)
│   ├── arm_broker_interfaces/            ← paquete ament_cmake (interfaces)
│   │   ├── action/MoveArm.action         ← goal: joint_positions[], client_id,
│   │   │                                   priority(0..255) · result: success,
│   │   │                                   message, wait_time_s, exec_time_s ·
│   │   │                                   feedback: state, queue_position, elapsed_s
│   │   ├── msg/QueueState.msg            ← telemetría de la cola a 5 Hz
│   │   ├── srv/InterpretarOrden.srv      ← petición: frase + forzar_clasificador ·
│   │   │                                   respuesta: acción/objeto/color/prioridad/
│   │   │                                   permitido/motivo + degradada + tiempos
│   │   ├── CMakeLists.txt                ← rosidl_generate_interfaces (ya incluye
│   │   │                                   action, msg y srv)
│   │   └── package.xml
│   │
│   └── arm_broker/                       ← paquete ament_python (nodos y lógica)
│       ├── arm_broker/
│       │   ├── fk.py                     ← Ítem 1 RB-2: DH + validaciones
│       │   ├── broker.py                 ← Ítem 2 RB-2: ActionServer, admisión,
│       │   │                               worker único, publicador único
│       │   ├── politicas.py              ← Ítem 3 RB-2: Pedido, FIFO,
│       │   │                               SegundaPolitica (aging), POLITICAS
│       │   ├── cliente.py                ← cliente de trazas (secuencial/async)
│       │   ├── interprete_ordenes.py     ← P1: nodo del servicio /interpretar_orden
│       │   ├── cliente_laya.py           ← P1: cliente HTTP a LAYA (+ línea base)
│       │   └── clasificador_palabras_clave.py  ← P1: respaldo sin red
│       ├── setup.py                      ← entry points: broker, cliente,
│       │                                   interprete_ordenes
│       ├── setup.cfg
│       ├── package.xml
│       └── resource/arm_broker
│
├── herramientas/                         ← scripts de prueba y medición
│   ├── generar_carga.py                  ← genera la traza (semilla reproducible)
│   ├── carga.csv                         ← copia de la traza (misma que la raíz)
│   ├── frases_ejemplo.csv                ← 8 frases de prueba con columnas esperado_*
│   ├── probar_laya.py                    ← prueba LAYA SIN ROS 2 (correr primero)
│   ├── medir_item1.py                    ← mide latencia y exactitud de la P1
│   ├── simular_corrida.py                ← simulador por eventos → prediccion.md
│   ├── validar_rechazos.py               ← demuestra las 3 causas de rechazo
│   ├── verificar_fk.py                   ← FK vs brazo real (Jetson, pymycobot)
│   └── completar_informe.py              ← escribe los ítems 2 y 3 del RB-2 dentro
│                                           de Informe.docx (ese .docx no está en el repo)
│
└── analisis/                             ← instrumentación de bags y métricas
    ├── verificar_publicadores.py         ← exige EXACTAMENTE 1 publicador en
    │                                       /joint_states llamado arm_broker
    ├── exportar_csv.py                   ← bag → CSV con rosbag2_py (requiere ROS 2)
    ├── exportar_csv_directo.py           ← bag .db3 → CSV SIN ROS 2 (SQLite + CDR)
    ├── metricas.py                       ← métricas + figura desde CSV
    ├── metricas_directo.py               ← ídem sin ROS 2, guarda resumen y .png
    └── generar_datos_analisis.py         ← orquesta las dos anteriores de una vez
```

### Qué corre en cada dispositivo (mapa rápido)

| Dispositivo | Corre aquí | Herramientas usables |
|---|---|---|
| **Tu PC Windows** (RTX 3050 laptop) | Repositorio, **servidor LAYA** (`laya-serve`), edición de código, análisis de bags copiados | `probar_laya.py`, `generar_carga.py`, `simular_corrida.py`, `exportar_csv_directo.py`, `metricas_directo.py`, `generar_datos_analisis.py`, `completar_informe.py` |
| **Jetson** (ROS 2 Humble) | Driver `sync_plan_nx`, **broker**, **clientes**, **interprete_ordenes**, **transcriptor_voz**, grabación de bags | `medir_item1.py`, `validar_rechazos.py`, `verificar_fk.py`, `verificar_publicadores.py`, `exportar_csv.py`, `metricas.py` |
| **PCs de los 4 integrantes** | Clientes que envían órdenes en paralelo (P2) y los modos de prueba | `cliente.py` (con ROS 2) o terminales del enunciado |
| **Google AI Studio (nube)** | Transcripción de audio de la P3 (API REST con clave) | `curl` / `requests` |
| **Hugging Face (nube)** | Solo descarga inicial de los checkpoints de LAYA | — |

---

## 5. Qué es LAYA y cómo encaja aquí

**LAYA** es un motor de decisiones *System-1* no autoregresivo (repo oficial:
<https://github.com/NandhaKishorM/laya>): en **una sola pasada** devuelve
**decisiones tipadas** sobre un texto, sin generar texto libre. Tres tipos de
pregunta:

| Tipo | Significado | Ejemplo en este proyecto |
|---|---|---|
| `choice` | elegir una opción de una lista cerrada | acción (`agarrar/soltar/mover/detener/desconocido`), objeto, color |
| `score` | un nivel de una escala | prioridad `0..3` |
| `noul` | sí/no (devuelve P(verdadero)) | `permitido` (≥ 0.5 se toma como `True`) |

Características relevantes para el examen:
- **No es un nodo ROS 2**: se sirve por HTTP con `laya-serve`, que expone
  `POST /v1/systemone` (mismo protocolo que la API Jev) y `GET /health`.
  Eso es **exactamente** lo que ya hablan `cliente_laya.py` y `probar_laya.py`.
- Se instala y corre **en tu propia PC** (`pip install "laya[serve]"`), con la
  GPU si hay (tu RTX 3050 sirve). No hay API oficial en la nube: lo que va a
  la nube es la **descarga** de los checkpoints (Hugging Face) y, en la P3, la
  **transcripción** (Google AI Studio).
- Autenticación opcional: si el servidor se levanta con `LAYA_API_KEY`, el
  cliente debe mandar `Authorization: Bearer <key>` (nuestro `cliente_laya.py`
  ya lo hace si la variable de entorno está definida en la máquina del nodo).
- Si LAYA **no contesta dentro de `timeout_laya_s`** (2 s por defecto),
  `interprete_ordenes` cae al **clasificador por palabras clave** y marca la
  respuesta `degradada=True`: el sistema nunca se queda esperando.

Instalación, configuración y uso paso a paso: **[`ITEM_1.md`](ITEM_1.md) §4**.

---

## 6. Estado real del repo: inconsistencias y pendientes

Cosas que hay que saber **antes** de confiar en la documentación vieja:

### Inconsistencias entre documentos
| Tema | Qué dicen | Qué hacer |
|---|---|---|
| `ROS_DOMAIN_ID` | `PASOS.txt` y `GUIA_SIN_LAYA.md` → **43**; `TERMINALES.md` → **47** (equipo 5) | Unificar el mismo valor en **las 5 máquinas** antes de medir; anotar cuál se usó |
| `config/equipo.env` y `conectar_reto.sh` | Los cita `README.md` §6 y `TERMINALES.md` | **No existen**: usar los `export` de `PASOS.txt` o crearlos |
| Métricas | `PASOS.txt` línea 53-57 usa `--fifo/--prio/--outdir` | Desactualizado: la sintaxis real es `metricas.py fifo/queue_state.csv prioridad/queue_state.csv --salida salida.png` (ver `TERMINALES.md`) |
| `README_RETO2.md` | Existía en el commit `v1` | Borrado; su contenido es ahora `README_PARCIAL.md` |
| Tabla DH | `fk.py` usa `d5=75.55`, `d6=50`; `mi_info.txt` del kit declara `d5=75.05`, `d6=60` | **Verificar físicamente** con `verificar_fk.py` en la Jetson; no se arregla por código |
| Workspace `~/rb2_ws` | `PASOS.txt` clona `reto2_robotica` en `~/rb2_ws` | Este repo es `rGsmueL/parcial`; ajustar la ruta real del clone |

### Pendientes de código (lo que hay que construir)
| Pregunta | Existe | Falta |
|---|---|---|
| **P1** | nodo, cliente LAYA, clasificador, `.srv`, medidor | CSV con las **50 frases oficiales** + columnas `esperado_*`; confirmar el JSON real de LAYA con `probar_laya.py` |
| **P2** | broker, políticas, cliente, FK, validadores | **Orquestador** que llame a `/interpretar_orden` y envíe el goal con la **prioridad del modelo**; rechazo de órdenes `permitido=False` **antes** de encolar con causa; **cámara → IK → MoveIt2 → gripper** |
| **P3** | todo lo de P1 y P2 | Nodo **`transcriptor_voz`** (audio → Google AI Studio → `/interpretar_orden`) con timeout y **modo teclado** |

### Archivos de evidencia esperados al final
`rechazos.csv` · `resultados_calma.csv` / `resultados_carga.csv` ·
`prediccion.md` (escrito antes de medir) · bags `fifo/` y `prioridad/` ·
`comparacion_politicas.png` · audio + transcripciones · tabla de 10 intentos ·
tabla de 5 órdenes habladas · desglose de tiempos + figura · videos.

---

## 7. Orden de lectura sugerido

1. Este archivo (`CONTEXTO.md`) — qué es todo y dónde está.
2. `Parcial_Gran_Reto_JetCobot.docx` — el enunciado, si hay duda manda el docx.
3. [`ITEM_1.md`](ITEM_1.md) — instala LAYA en tu PC y levanta el servicio de
   interpretación (es lo primero que se usa en las otras dos preguntas).
4. [`ITEM_2.md`](ITEM_2.md) — la cadena bajo la cola del broker.
5. [`ITEM_3.md`](ITEM_3.md) — agrega la voz por delante de todo lo anterior.
6. De apoyo: `README_PARCIAL.md` (detalle fino de la P1),
   `README.md` (detalle fino del RB-2), `GUIA_SIN_LAYA.md` (placeholders),
   `TERMINALES.md` y `PASOS.txt` (comandos de arranque).
