# ÍTEM 2 — Pregunta 2 (8 pts): agarre autónomo bajo la cola del broker

> Cuatro objetos de colores sobre la mesa, órdenes en lenguaje natural llegando
> **de las 4 máquinas del equipo al mismo tiempo**, y el brazo que los recoge
> bajo la **cola de prioridad del broker** del RB-2. Aquí está explicado el
> código que ya existe (broker, políticas, cliente, FK y sus herramientas),
> qué hay que **construir encima** y el paso a paso, comando por comando y por
> dispositivo, para la demostración.
>
> Enunciado: `Parcial_Gran_Reto_JetCobot.docx`. Detalle fino del broker:
> `README.md` (ítems 2 y 3), `GUIA_SIN_LAYA.md` (movimiento básico),
> `TERMINALES.md` + `PASOS.txt` (arranque y bags).

---

## 1. Qué pide el enunciado (resumen)

**Integrar la cadena completa** reutilizando los retos previos:

```
frase (P1) ──► /interpretar_orden ──► decisión ──► COLA DE PRIORIDAD del broker (RB-2)
                                                        │ al desencolar
                                                        ▼
                                              cámara localiza el objeto
                                                        ▼
                                              cinemática inversa (IK)
                                                        ▼
                                              MoveIt2 planifica trayectoria
                                                        ▼
                                              gripper: agarre + traslado
```

Requisitos con calificación directa:
1. La **prioridad del goal viene de la decisión del modelo**, no está escrita
   a mano por el cliente.
2. Se mantiene la regla del RB-2: **solo el worker del broker publica al
   brazo**. Durante la demo, los 4 integrantes envían en paralelo.
3. Una orden **`permitido = False`** se rechaza **antes de encolarse**,
   indicando la causa (el docente dictará al menos una).
4. **10 intentos de agarre** + tasa de éxito (objeto correcto en zona
   correcta).
5. Para cada intento exitoso, **error entre la posición solicitada y la
   alcanzada**, calculado con la **FK del RB-2** (`fk.py`).
6. Entregables: **bag** de la demostración, **tabla de los 10 intentos**
   (resultado + error) y **video de 3 min** con la cola del broker y el brazo
   trabajando bajo pedidos simultáneos.

> ⚠️ **Observación eliminatoria del docx**: un equipo cuyo brazo reciba
> comandos desde un nodo distinto al worker del broker **pierde el puntaje
> íntegro** de la P2, aunque el agarre funcione.

---

## 2. El código que ya existe, explicado

### 2.1 `src/arm_broker/arm_broker/broker.py` — el corazón (ítem 2 del RB-2)

Un solo nodo `arm_broker`. Tres grupos de callbacks:

| Grupo | Tipo | Para qué |
|---|---|---|
| `grupo_entrada` | `ReentrantCallbackGroup` | aceptar goals **mientras** otro se ejecuta |
| `grupo_worker` | `MutuallyExclusiveCallbackGroup` | **exclusión mutua**: dos vueltas del worker nunca se solapan |
| `grupo_estado` | `MutuallyExclusiveCallbackGroup` | publicar `/arm/queue_state` a 5 Hz sin que se congele durante un movimiento |

Parámetros (`--ros-args -p …`): `politica` (`fifo`/`prioridad`),
`tau_envejecimiento_s` (8.0 por defecto, **usar 12.0** en mediciones),
`cola_max` (20), `paso_max_rad` (1.2 por defecto, **1.6** para corridas
comparativas), `duracion_movimiento_s` (3.0; 1.5 en corridas), 
`pasos_interpolacion` (10), `archivo_rechazos` (`rechazos.csv`).

Ciclo de vida de un goal:

1. **`goal_callback` (admisión)** — barata e inmediata, no ejecuta nada:
   `_validar(q)` en este orden →
   1. valores **finitos** (NaN/inf → causa `limite`),
   2. **límites articulares** (`fk.dentro_de_limites`),
   3. **workspace** (`fk.dentro_del_workspace`: `z>=0`, alcance 80–480 mm),
   4. **paso articular** (`fk.paso_articular(q_actual, q) ≤ paso_max`),
   5. **cola llena** (bajo el mismo lock se **reserva** el cupo: evita que 4
   clientes vean el mismo hueco y se supere `cola_max`).
   Todo rechazo → log con causa + fila en `rechazos.csv`
   (`t_unix, client_id, priority, causa, motivo, joint_positions`).
2. **`handle_accepted_callback` (encolado)** — crea el `Pedido` y lo pone en
   `self.pendientes`; **aquí no se ejecuta ni se publica nada**.
3. **`_worker` (timer de 20 ms en el grupo MutuallyExclusive)** — si el brazo
   está libre, la **política** elige índice, se saca el pedido y se ejecuta
   **entero** antes de mirar el siguiente (esa espera `pedido.fin.wait()` es
   la exclusión mutua).
4. **`execute_callback`** — **revalida el paso** (la pose pudo cambiar por los
   pedidos de adelante → causa `paso_al_ejecutar`), interpola linealmente
   desde `q_actual` hasta el destino en `pasos_interpolacion` pasos,
   publicando cada uno en **`/joint_states`** con `mover(q)` y mandando
   feedback `EXECUTING`; cierra con `succeed/canceled/abort` y devuelve
   `wait_time_s` + `exec_time_s`.
5. **`publicar_estado_cola`** (5 Hz) — llena `QueueState` (longitud, quién
   ejecuta, esperas, contadores) y manda feedback `QUEUED` con la posición en
   cola a cada pendiente.

**El broker es el ÚNICO publicador de `/joint_states`** (requisito verificable).

### 2.2 `src/arm_broker/arm_broker/politicas.py` — quién le toca (ítem 3 del RB-2)

- **`Pedido`**: `client_id`, `priority`, `t_llegada`, `joint_positions`,
  `t_inicio_ejec`, `fin` (Event), `resultado`; propiedad `espera_s`.
- **`FIFO.siguiente(pendientes)`** → índice del `t_llegada` menor. Línea base:
  ignora prioridad, sirve para aislar el efecto del aging.
- **`SegundaPolitica`** (`nombre='prioridad'`): `puntuación = priority +
  espera_s / tau`, elige el **máximo**; empate → el más antiguo (`-t_llegada`).
  Con `tau = 12 s`, un pedido de prioridad 1 que espera 24 s iguala a uno de
  prioridad 3 recién llegado → urgencia manda pero **nadie se eterniza**
  (acota la inanición).
- `POLITICAS = {'fifo': FIFO, 'prioridad': SegundaPolitica}` — el broker toma
  la clase por el parámetro `politica`.

### 2.3 `src/arm_broker/arm_broker/cliente.py` — los pedidos

- Lee una traza CSV (6 ángulos por fila; vacío = 2 poses de prueba
  `[0.3,0,0,0,0,0]` y `[-0.3,0,0,0,0,0]`).
- Parámetros: `client_id`, `priority`, `traza`, `repeticiones`, `pausa_s`,
  `modo` (`secuencial` | `asincrono`), `inicio_unix` (arranque sincronizado
  para que todos arranquen igual aunque cada `ros2 run` tarde distinto).
- **secuencial**: manda uno y espera el resultado → cola corta.
  **asíncrono**: manda toda la traza sin esperar → cola llena → es la carga
  que hace que la política de prioridad tenga algo que decidir.
- **Nunca publica `/joint_states`**; solo envía goals a `move_arm`.
- Log por goal: `success`, `espera=…s`, `ejec=…s`, `RECHAZADA` si el broker
  lo rechazó (el motivo está en el log/CSV del broker).

### 2.4 `src/arm_broker/arm_broker/fk.py` — la portera (ítem 1 del RB-2)

Tabla DH (con offsets geométricos), `fk(q) → (x,y,z)` en mm, y las tres
validaciones que el broker usa como portero: `dentro_de_limites`,
`dentro_del_workspace` (80 ≤ r ≤ 480 mm, `z ≥ 0`), `paso_articular`.
**También es la que calcula el error de agarre** que pide el enunciado:
`error = ‖ fk(q_solicitada) − fk(q_alcanzada) ‖`.

### 2.5 Interfaces (`src/arm_broker_interfaces/`)

- `action/MoveArm.action` — goal: `joint_positions[]`, `client_id`,
  `priority` (uint8, **mayor = más urgente**); result: `success`, `message`,
  `wait_time_s`, `exec_time_s`; feedback: `state` (`QUEUED`/`EXECUTING`),
  `queue_position`, `elapsed_s`.
- `msg/QueueState.msg` — la telemetría de la cola (lo que sale en el video).

---

## 3. Herramientas que le tocan a este ítem (y cómo funcionan)

| Herramienta | Qué hace | Cuándo correrla |
|---|---|---|
| `herramientas/generar_carga.py` | Genera `carga.csv` (40 poses dentro de límites y workspace) con `--semilla` fija → misma traza para FIFO y prioridad (requisito de reproducibilidad). Importa `fk` por `sys.path` relativo, corre en cualquier PC. | Solo si hay que regenerar la traza: `python herramientas/generar_carga.py --n 40 --semilla 7 --salida carga.csv` |
| `herramientas/validar_rechazos.py` | Demuestra con **evidencia** las 3 causas de rechazo: primero valida localmente con `fk.py` que cada caso dispare **solo** su causa, luego manda los goals (`limite`: q3=3.0 rad; `workspace`: pose pegada a la base; `paso`: q3=1.8 desde home), y por último **lee `rechazos.csv`** para comprobar que las 3 causas quedaron escritas con motivo. Sale con código 0/1. | Con el broker recién arrancado: `python3 herramientas/validar_rechazos.py --paso-max 1.2` |
| `analisis/verificar_publicadores.py` | Ejecuta `ros2 topic info /joint_states --verbose` y exige **exactamente 1 publicador llamado `arm_broker`**. Código 0 = OK; 1 = medición inválida. `--salida archivo.txt` guarda la salida como evidencia. | **Antes de cada grabación** (regla eliminatoria) |
| `herramientas/simular_corrida.py` | Simulador por eventos que usa `politicas.py` **tal cual** (mismo contrato `siguiente()` devuelve índice) y la misma validación del broker, para **predecir** esperas, p95, inanición y Jain de cada política. `--ambos --salida prediccion.md` escribe la predicción que va en el diseño previo. | **Antes de medir** (el enunciado exige predicción escrita previamente) |
| `analisis/exportar_csv.py` | Lee el bag con `rosbag2_py` y escribe `queue_state.csv` y `joint_states.csv` dentro de la carpeta de la política. Requiere ROS 2. | Después de grabar los bags |
| `analisis/exportar_csv_directo.py` | Lo mismo **sin ROS 2**: abre el `.db3` como SQLite y decodifica el CDR a mano. Resultado idéntico. | Alternativa desde tu PC Windows |
| `analisis/metricas.py` | `python3 metricas.py fifo/queue_state.csv prioridad/queue_state.csv --salida comparacion_politicas.png` → espera media/p95 por prioridad, **inanición** (espera máxima de la prioridad más baja), **equidad de Jain** por cliente, contadores. Toma el nombre de la política del **nombre de la carpeta**. | Tras exportar |
| `analisis/metricas_directo.py` / `generar_datos_analisis.py` | Igual sin ROS 2; `generar_datos_analisis.py` hace todo el pipeline (exportar + métricas + figura) de una vez desde la raíz. | Desde tu PC, con los bags copiados |
| `herramientas/verificar_fk.py` | En la Jetson (puerto serie libre, **sin** `sync_plan_nx`): lleva el brazo a 4 poses, compara `fk(q)` con `get_coords()`; criterio ≤ 10 mm. También sirve para **medir el error de agarre** de otra forma. | Antes de la demo, para validar la FK |

---

## 4. Qué FALTA construir (la parte nueva de la P2)

Nada de esto existe todavía en el repo. Se sugiere agregar **un nodo
orquestador** (por ejemplo `arm_broker/orquestador.py`) que haga el puente:

### 4.1 Orquestador: decisión → goal con prioridad del modelo
```python
# pseudocódigo del flujo a implementar
dec = llama_servicio(frase)                      # /interpretar_orden (P1)

if not dec.permitido:                            # ← rechazo ANTES de encolar
    escribe_rechazo(frase, causa='no_permitida', motivo=dec.motivo)
    return                                        # NO se envía goal

pose = perception_y_ik(dec.objeto, dec.color)    # cámara + IK (ver §4.2)
goal = MoveArm.Goal(joint_positions=pose,
                    client_id=<integrante>,
                    priority=escala(dec.prioridad))   # ← viene del modelo
envia_goal(goal)
```
- **Escala de prioridad**: LAYA devuelve `0..3` (o el clasificador devuelve
  `1`); el campo `priority` del goal es `uint8 0..255`. Mapea, por ejemplo,
  `priority = prioridad * 85` (0→0, 1→85, 2→170, 3→255) y **decláralo en el
  informe**. Nunca lo escribas fijo en el cliente.
- **Rechazo `no_permitida`**: el broker solo valida geometría, así que el
  rechazo de órdenes no permitidas ocurre **aguas arriba**, en el orquestador,
  registrándolo con su causa en un CSV (mismo formato que `rechazos.csv`:
  `t_unix, client_id, priority, causa, motivo, frase`). Así se cumple
  "rechazada antes de encolarse, indicando la causa".
- Un cliente ROS 2 genérico para las pruebas sin cámara sigue siendo
  `cliente.py` (con `-p priority:=…`).

### 4.2 Percepción + IK + MoveIt2 + gripper (lo que está fuera del repo)
1. **Cámara localiza el objeto**: detección por color (HSV en OpenCV es
   suficiente para 4 colores planos) → píxel → coordenada usando la
   calibración de la cámara. Salida: posición `(x,y,z)` del objeto.
2. **Cinemática inversa**: resolver `q1..q6` para esa posición (una IK
   numérica propia o la de MoveIt2; el kit a menudo trae poses precalculadas
   por color — si las usas, decláralo).
3. **MoveIt2 planifica** la trayectoria y el **gripper** ejecuta agarre y
   traslado a la zona indicada.
4. Durante el movimiento **solo** puede publicar el worker del broker: si
   MoveIt2 va a controlar directamente el brazo, hazlo **después** de que el
   broker termine su goal (secuencia: broker mueve a la pose de aproximación →
   MoveIt2/gripper hacen el agarre), o integra MoveIt2 como consumidor de la
   misma fuente de verdad. **Nunca** dos publicadores de `/joint_states`.

### 4.3 Contadores de los 10 intentos
Tabla (CSV) con: `intento, frase/orden, objeto_solicitado, zona, exito(bool),
q_solicitada, q_alcanzada, error_mm` donde
`error_mm = ‖fk(q_sol) − fk(q_alc)‖` (usa `arm_broker.fk.fk`, corre en
cualquier PC con Python). La tasa de éxito = `exitos/10`.

---

## 5. Plan de corrida, paso a paso y por dispositivo

### Fase A — Preparación (día anterior / antes de la demo)
1. **Tu PC**: LAYA arriba (`ITEM_1.md` §4.3) y firewall abierto.
2. **5 máquinas** (4 integrantes + quien grabe): mismo `ROS_DOMAIN_ID`,
   mismo `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, mismo `ROS_DISCOVERY_SERVER`,
   `ros2 daemon stop; ros2 daemon start`.
3. **Jetson**: compilar (`colcon build --packages-select arm_broker_interfaces
   arm_broker --symlink-install`) y probar en frío con `cliente.py`.
4. **Predicción escrita ANTES de medir**:
   ```bash
   python3 herramientas/simular_corrida.py --ambos --tau 12.0 \
     --paso-max 1.6 --modo secuencial --salida prediccion.md
   ```
   Anota el p95 esperado por política.

### Fase B — Verificaciones previas (Jetson)
```bash
# 1) Un solo publicador de /joint_states (REGLA ELIMINATORIA)
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt

# 2) Los 3 rechazos con causa y motivo en el CSV
python3 herramientas/validar_rechazos.py --paso-max 1.2
```

### Fase C — Arranque de la cadena (por dispositivo)

**Jetson — Terminal 0 (driver):**
```bash
source /opt/ros/humble/setup.bash
ros2 run jetcobot_driver sync_plan_nx
```

**Jetson — Terminal 1 (broker, prioridad con aging):**
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43        # UNIFICAR con el resto
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start
cd ~/rb2_ws && source install/setup.bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad \
  -p tau_envejecimiento_s:=12.0 \
  -p duracion_movimiento_s:=1.5 \
  -p paso_max_rad:=1.6 \
  -p archivo_rechazos:=rechazos.csv
```

**Jetson — Terminal 2 (intérprete de la P1):**
```bash
export LAYA_API_KEY="..."      # solo si el servidor la exige
ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP_PC_CON_LAYA>:8000 -p timeout_laya_s:=2.0
```

**Cada integrante (su PC) — orquestador/cliente en paralelo:**
```bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
cd ~/rb2_ws && source install/setup.bash
# una orden por integrante, prioridad según el modelo (o traza para carga)
ros2 run arm_broker cliente --ros-args \
  -p client_id:=samuel -p priority:=170 -p modo:=secuencial
```
Los cuatro al mismo tiempo: eso es la "demostración con pedidos simultáneos".

### Fase D — Grabación (Jetson o PC con la cola visible)
```bash
python3 analisis/verificar_publicadores.py     # otra vez, antes de grabar
ros2 bag record -o demo_p2 /arm/queue_state /joint_states
```
Mientras corre la grabación: los 4 clientes enviando órdenes (al menos una
**no permitida** para el rechazo, y las de agarre), se graba **video de
3 minutos** donde se vean la cola (`/arm/queue_state` en una terminal con
`ros2 topic echo`) y el brazo.

### Fase E — Métricas de las políticas (RB-2, evidencia del diseño)
```bash
ros2 bag record -o fifo       /arm/queue_state /joint_states   # corrida FIFO
ros2 bag record -o prioridad  /arm/queue_state /joint_states   # corrida prioridad
# exportar y medir (TERMINALES.md, sintaxis real):
python3 analisis/exportar_csv.py fifo/ --salida fifo/
python3 analisis/exportar_csv.py prioridad/ --salida prioridad/
python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv \
  --salida comparacion_politicas.png
```
En tu PC Windows (sin ROS 2), copiando las carpetas de bags:
```powershell
python analisis\generar_datos_analisis.py     # exporta + métricas + figura
```

### Fase F — Los 10 intentos de agarre
Con la cadena completa arriba, ejecuta 10 órdenes de agarre (mezcla
prioridades y al menos una no permitida que se rechace). Para cada uno llena
la tabla de §4.3; calcula `error_mm` con:
```python
from arm_broker import fk   # en cualquier PC, desde la raíz del repo
x1 = fk.fk(q_solicitada); x2 = fk.fk(q_alcanzada)
error = sum((a-b)**2 for a, b in zip(x1, x2)) ** 0.5   # mm
```

---

## 6. Entregables de la Pregunta 2

| Entregable | Fuente |
|---|---|
| Bag de la demostración | `demo_p2/` (`/arm/queue_state` + `/joint_states`) |
| Tabla de 10 intentos (resultado + error) | CSV de §4.3 |
| Video de 3 min (cola + brazo bajo pedidos simultáneos) | grabación de pantalla + brazo |
| Evidencia de publicador único | `evidencia/publicadores.txt` (`verificar_publicadores.py`) |
| Evidencia de rechazo con causa | `rechazos.csv` + fila `no_permitida` del orquestador |
| Predicción previa | `prediccion.md` (escrito antes de medir) |
| Comparación de políticas | `comparacion_politicas.png` + resumen de `metricas.py` |

---

## 7. Checklist de la Pregunta 2

1. [ ] LAYA arriba en tu PC (`ITEM_1.md` §4) y `interprete_ordenes` en la Jetson.
2. [ ] Orquestador implementado: decisión → pose → goal con `priority` escalada (§4.1).
3. [ ] Rechazo `no_permitida` con causa **antes** de enviar el goal (§4.1).
4. [ ] Cámara → IK → MoveIt2 → gripper encadenados, sin segundo publicador (§4.2).
5. [ ] `verificar_publicadores.py` = exactamente 1 publicador `arm_broker` (§Fase B).
6. [ ] `validar_rechazos.py` = las 3 causas en `rechazos.csv` (§Fase B).
7. [ ] Predicción con `simular_corrida.py` escrita **antes** de medir (§Fase A).
8. [ ] 4 clientes en paralelo + bag + video de 3 min (§Fase C-D).
9. [ ] Bags FIFO vs prioridad → CSV → `metricas.py` → figura (§Fase E).
10. [ ] 10 intentos con error por FK y tasa de éxito (§Fase F).
