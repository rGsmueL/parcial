# ARQUITECTURA DEL PROYECTO — JetCobot (Parcial Gran Reto) + Reto Brazo 2 (RB-2)

> **Para qué sirve este documento.** Es un mapa técnico completo del repositorio
> `carrprp`: qué problema resuelve, cómo está dividido, qué hace **cada archivo**,
> cuáles son los flujos de datos, las interfaces ROS 2, las reglas/restricciones y
> las **inconsistencias conocidas** entre documentos y código. Está pensado para
> dárselo a una IA (o a un compañero nuevo) como contexto único antes de tocar
> código, de modo que se detecten errores de método, supuestos falsos y
> desactualizaciones.
>
> Fuente de verdad en caso de duda: **el código en `src/`** y el enunciado
> `Parcial_Gran_Reto_JetCobot.docx`. La documentación narrativa
> (`docs/`, `README*.md`, `PASOS*.md`) describe el proyecto pero tiene zonas
> desactualizadas (ver §12).

---

## 1. Resumen ejecutivo

Un brazo robótico **JetCobot** (6 GDL, controlado desde una **Jetson con ROS 2
Humble** y el driver `sync_plan_nx`) debe atender **órdenes en español, escritas
o habladas**, que llegan de **varias personas a la vez**, sin escribir
coordenadas y sin quedarse nunca esperando. La frase *"agarra el cubo rojo"* se
convierte en movimiento mediante la cadena:

```
frase → decisión tipada (LAYA) → cola de prioridad del broker → cámara →
cinemática inversa → MoveIt2 → gripper → brazo
```

El trabajo está dividido en **dos etapas que conviven en el mismo repo**:

| Etapa | Nombre | Qué aporta | Estado |
|---|---|---|---|
| Anterior | **RB-2 (Reto Brazo 2)** | Cinemática directa (`fk.py`), **broker** de acceso exclusivo (`broker.py`) y **políticas de cola** (`politicas.py`) | Implementado en `src/` |
| Actual | **Parcial Gran Reto JetCobot** | Interpretación de frases (LAYA + clasificador), cadena de agarre autónomo y voz | Implementado en `src/` (ver §12 para pendientes de evidencia) |

Preguntas del parcial:

- **P1 (6 pts)** — Nodo `interprete_ordenes` con servicio `/interpretar_orden`:
  frases → decisión tipada consultando **LAYA** por HTTP, con timeout y respaldo
  por palabras clave. Medir latencia (mediana/p95, red vs cómputo) en calma y
  bajo carga, y exactitud LAYA vs clasificador sobre 50 frases.
- **P2 (8 pts)** — Agarre autónomo bajo la cola del broker: decisión → cola →
  cámara → pose (IK precalculada) → pinza. Prioridad del modelo, rechazo de
  órdenes no permitidas antes de encolar, 10 intentos con error por FK, bag +
  video.
- **P3 (6 pts)** — De la voz al movimiento: nodo `transcriptor_voz` (audio →
  texto en español vía Google AI Studio) que alimenta a P1; fallback a teclado;
  5 órdenes habladas y desglose de tiempos; demo sin internet.

---

## 2. Arquitectura de alto nivel

### 2.1 Diagrama de dispositivos

```
┌──────────────────────────┐     HTTP /v1/systemone     ┌───────────────────────────────┐
│  PC Windows del equipo   │  ◄─────────────────────── │  JETSON (grafo ROS 2)         │
│  laya-serve (GPU/CPU)    │                            │  broker · cliente ·           │
│  NO necesita internet    │                            │  interprete_ordenes ·         │
└──────────────────────────┘                            │  percepcion_camara ·          │
                                                        │  orquestador_item2 ·          │
┌──────────────────────────┐   HTTPS (internet)         │  transcriptor_voz ·           │
│  Google AI Studio        │  ◄──────────────────────── │  cliente_texto ·              │
│  (transcripción de voz)  │   x-goog-api-key           │  sync_plan_nx (driver)        │
└──────────────────────────┘                            └───────────────┬───────────────┘
                                                                        │ /joint_states
                                                                        ▼
                                                                  JetCobot (brazo + pinza)
```

Dato del enunciado que guía el diseño: *"la transcripción depende de internet;
la decisión y el movimiento, no"*. Por eso LAYA corre **local** en la PC y solo
la transcripción sale a la nube.

### 2.2 Flujo de datos ROS 2 (tópicos y acciones)

```
                            P3 (voz)                         P1 (decisión)
  operador ──audio──► transcriptor_voz ──frase──► /interpretar_orden (srv)
       │                     │                              │
       │ (fallback teclado)  │ publica String(JSON)         │ responde
       └─────────────────────┴──► /orden_decidida ──────────┘
                                        │
                                        ▼
                            orquestador_item2  (rechaza permitido=False ANTES de encolar)
                                        │
                     espera /objeto_detectado (JSON de percepcion_camara)
                                        │
                       envía goals move_arm (priority = prioridad*85)
                                        ▼
                            BROKER arm_broker (ActionServer move_arm)
                              · único publicador de /joint_states
                              · publica /arm/queue_state a 5 Hz
                                        │
                                        ▼
                        /joint_states ──► sync_plan_nx (driver) ──► brazo
                            ▲
                            └─ orquestador_item2 SOLO LEE /joint_states (error FK)
                                        │
                                        └── gripper_command (GripperCommand) ──► pinza

  Para carga de pruebas (P2/RB-2): cliente.py envía goals move_arm en paralelo.
  Para frases por teclado sin voz: cliente_texto.py → /interpretar_orden → /orden_decidida.
```

### 2.3 Invariantes (reglas duras)

1. **Exactamente un publicador de `/joint_states`**, el nodo `arm_broker`.
   Cualquier otro nodo que publique ahí anula el puntaje de la P2. Verificación:
   `analisis/verificar_publicadores.py`.
2. **Solo el worker del broker** envía comandos al brazo. Los clientes y el
   orquestador solo envían *goals* a la acción `move_arm` (y el orquestador solo
   *lee* `/joint_states`).
3. **Prioridad: número MAYOR = MÁS urgente** (`0..255`, en `MoveArm.action`).
4. **Órdenes `permitido=False` / objeto desconocido se rechazan ANTES de
   encolar**, con causa y motivo registrados en CSV (lo hace el orquestador, no
   el broker; el broker solo valida geometría).
5. **`tau_envejecimiento_s = 12.0`** obligatorio en las mediciones (default de
   código = 8.0).
6. **Predicción escrita antes de medir** (`prediccion.md` con
   `herramientas/simular_corrida.py`).
7. Claves de API **solo** por variable de entorno (`LAYA_API_KEY`,
   `GOOGLE_API_KEY`); nunca en el código.
8. `ROS_DOMAIN_ID` = 43 (42 + nº de equipo) **igual en todas las máquinas**.

---

## 3. Mapa del repositorio

```
carrprp/                                   ← raíz (GitHub: rGsmueL/parcial)
├── ARQUITECTURA.md                        ← este documento
├── README.md                              ← RB-2: broker, políticas, admisión, DH, predicción
├── README_PARCIAL.md                      ← P1: instalar/compilar/medir interprete_ordenes
├── TERMINALES.md                          ← comandos de terminal para bags y métricas
├── PASOS.txt                              ← orden de arranque (¡sección final desactualizada!)
├── carga.csv                              ← traza oficial: 40 poses, semilla 7
├── frases_50.csv                          ← 50 frases + columnas esperado_* (P1)
├── Parcial_Gran_Reto_JetCobot.docx        ← enunciado oficial
├── errroes.docx                           ← notas de errores (Word)
│
├── docs/                                  ← guías narrativas
│   ├── CONTEXTO.md                        ← guía general del proyecto (muy completa)
│   ├── ITEM_1.md / ITEM_2.md / ITEM_3.md  ← guías por pregunta
│   ├── ITEM_1_EVIDENCIAS.md … ITEM_3_EVIDENCIAS.md
│   ├── agarrar_cubo_sin_rastreo.py        ← script de referencia del kit (poses en grados)
│   └── item3/                             ← ORIGEN/COPIAS de los archivos de la P3
│       ├── README_ITEM3.md
│       ├── transcriptor_voz.py, voz_google.py, orquestador.py
│       ├── probar_transcripcion.py, graficar_tiempos.py
│       ├── transcripciones.csv, plantilla_ordenes.csv, setup_entrypoints.txt
│
├── PASOS/
│   ├── PASOS_ITEM_1.md / PASOS_ITEM_2.md / PASOS_ITEM_3.md
│
├── item2/                                 ← ORIGEN/COPIAS de los archivos de la P2
│   ├── README_ITEM2.md, README_ITEM2_parte_2.md, COMO_USAR_ITEM2.md
│   ├── CAMBIOS_ITEM2.md, DATOS_FALTANTES.md, PROMM,PP gpt.md
│   ├── poses.py, gripper.py, intentos.py, percepcion_camara.py
│   ├── orquestador_item2.py, cliente_texto.py, 5.py
│   ├── probar_camara.py, probar_pinza.py, verificar_poses.py
│   ├── intentos.csv, setup_entrypoints.txt
│
├── src/                                   ← paquetes ROS 2 (lo que se compila)
│   ├── arm_broker_interfaces/             ← ament_cmake (interfaces)
│   │   ├── action/MoveArm.action
│   │   ├── msg/QueueState.msg
│   │   ├── srv/InterpretarOrden.srv
│   │   ├── CMakeLists.txt, package.xml
│   └── arm_broker/                        ← ament_python (nodos y lógica)
│       ├── arm_broker/*.py
│       ├── setup.py, setup.cfg, package.xml
│       └── resource/arm_broker
│
├── analisis/                              ← instrumentación de bags y métricas
│   ├── verificar_publicadores.py
│   ├── exportar_csv.py, exportar_csv_directo.py
│   ├── metricas.py, metricas_directo.py, generar_datos_analisis.py
│
└── herramientas/                          ← scripts de prueba y medición
    ├── probar_laya.py, medir_item1.py
    ├── generar_carga.py, simular_corrida.py, validar_rechazos.py
    ├── verificar_fk.py, verificar_poses.py
    ├── probar_camara.py, probar_pinza.py, probar_transcripcion.py
    ├── graficar_tiempos.py, completar_informe.py
    ├── frases_ejemplo.csv, carga.csv
```

> `item2/` y `docs/item3/` son **carpetas-fuente**: contienen los archivos "en
> crudo" de esas preguntas con su guía de copiado. El código real que se compila
> y ejecuta es el de `src/arm_broker/arm_broker/` (ya integrado).

---

## 4. Paquete `arm_broker_interfaces` (ament_cmake)

Solo define interfaces ROS 2. `CMakeLists.txt` genera las tres con
`rosidl_generate_interfaces` (dependencias: `action_msgs`, `builtin_interfaces`).

### 4.1 `action/MoveArm.action`

```
# goal
float64[] joint_positions   # 6 ángulos en radianes (interno)
string    client_id
uint8     priority          # 0..255, MAYOR = MÁS URGENTE
---
# result
bool      success
string    message
float64   wait_time_s       # tiempo esperado en cola
float64   exec_time_s       # tiempo de ejecución
---
# feedback
string state                # QUEUED | EXECUTING
int32  queue_position
float64 elapsed_s
```

### 4.2 `msg/QueueState.msg` (telemetría a 5 Hz)

`stamp`, `executing_client`, `executing_goal_id`, `executing_elapsed_s`,
`queue_length`, `queued_goal_ids[]`, `queued_clients[]`,
`queued_priorities[]` (uint8), `queued_wait_s[]`, `total_accepted`,
`total_rejected`, `total_completed`.

### 4.3 `srv/InterpretarOrden.srv`

```
# request
string frase
bool   forzar_clasificador    # true = ignora LAYA, usa solo el clasificador local
---
# response
string accion                 # agarrar | soltar | mover | detener | desconocido
string objeto                 # cubo | cilindro | esfera | ... | desconocido
string color                  # rojo | verde | azul | amarillo | ninguno
int32  prioridad              # 0..255 (LAYA devuelve 0..3)
bool   permitido
string motivo                 # vacío si permitido
bool   degradada              # true = respondió el clasificador local
string fuente                 # "laya" | "palabras_clave"
float64 tiempo_total_s
float64 tiempo_red_s
float64 tiempo_computo_s
```

---

## 5. Paquete `arm_broker` (ament_python) — archivos

`setup.py` registra estos entry points (nombres para `ros2 run arm_broker <x>`):

| Ejecutable | Módulo | Rol |
|---|---|---|
| `broker` | `broker.py` | Servidor de la acción `move_arm` (corazón) |
| `cliente` | `cliente.py` | Cliente de trazas (carga de prueba, RB-2) |
| `interprete_ordenes` | `interprete_ordenes.py` | Nodo del servicio `/interpretar_orden` (P1) |
| `transcriptor_voz` | `transcriptor_voz.py` | Audio → texto → decisión (P3) |
| `percepcion_camara` | `percepcion_camara.py` | Detección de color por cámara (P2) |
| `orquestador_item2` | `orquestador_item2.py` | Orquestador definitivo de la P2 |
| `cliente_texto` | `cliente_texto.py` | Frase por teclado → servicio (P2) |

> **Nota:** `orquestador.py` (orquestador mínimo de la P3) existe en el código
> pero **NO está registrado** en `setup.py`. El orquestador que se usa es siempre
> `orquestador_item2`. `docs/item3/` trae una copia del mínimo; `item2/README`
> recomienda reemplazarlo.

### 5.1 `broker.py` — Broker de acceso exclusivo (Ítem 2 RB-2)

Nodo único `arm_broker`. Un goal atraviesa **tres etapas**:

1. **`goal_callback` (admisión)** — barata, no ejecuta ni toca el brazo.
   Valida con `fk.py` en este orden y rechaza con causa:
   1. valores finitos (NaN/inf → `limite`),
   2. **límites articulares** (`fk.dentro_de_limites`),
   3. **workspace** (`fk.dentro_del_workspace`: `z>=0`, alcance 80–480 mm),
   4. **paso articular** (`fk.paso_articular(q_actual, q) ≤ paso_max_rad`),
   5. **cola llena** (`len(pendientes) + reservados >= cola_max`). El cupo se
      **reserva bajo el mismo lock** (variable `reservados`) para que varios
      clientes simultáneos no sobrepasen `cola_max`.
   Todo rechazo → log + fila en `rechazos.csv`
   (`t_unix, client_id, priority, causa, motivo, joint_positions`).
2. **`handle_accepted_callback` (encolado)** — convierte el cupo reservado en un
   `Pedido` dentro de `self.pendientes`. **Aquí no se ejecuta nada.**
3. **`_worker` (timer 20 ms, `MutuallyExclusiveCallbackGroup`)** — si el brazo
   está libre (`self.ejecutando is None`), la política elige el índice, saca el
   pedido y lo atiende **completo** antes de mirar el siguiente. La espera
   `pedido.fin.wait()` dentro del grupo mutuamente excluyente **es** la exclusión
   mutua. Purga pedidos cancelados antes de elegir.
4. **`execute_callback`** — **revalida el paso** contra `q_actual` real (causa
    `paso_al_ejecutar`), interpola linealmente desde `q_actual` hasta el destino en
    `pasos_interpolacion` pasos, publica cada uno en `/joint_states` con `mover()`
    y emite feedback `EXECUTING`. Al final: `succeed`/`canceled`/`abort` y devuelve
    `wait_time_s` + `exec_time_s`. Siempre hace `pedido.fin.set()`.
    **`/joint_states` se publica en grados** (conversión `rad→°` en `mover()`):
    el driver `sync_plan_nx` pasa el valor tal cual a `send_angles()` de
    pymycobot, que espera grados. Lo interno (FK, `paso_max_rad`, `q_actual`)
    sigue en radianes.
5. **`publicar_estado_cola` (timer 0.2 s)** — llena y publica `/arm/queue_state`
   y envía feedback `QUEUED` con la posición en cola a cada pendiente.

Detalles relevantes:

- **Parámetros:** `politica` (`fifo`|`prioridad`), `tau_envejecimiento_s` (default
  **8.0**, usar 12.0), `cola_max` (20), `paso_max_rad` (default **1.2**, usar 1.6
  en corridas comparativas), `duracion_movimiento_s` (default **5.0**, >=5 s para
  que el brazo físico alcance cada ángulo), `pasos_interpolacion` (default **1**,
  un `/joint_states` por movimiento con el ángulo objetivo real; subirlo interpola),
  `archivo_rechazos` (`rechazos.csv`, vacío lo desactiva).
- **Grupos de callbacks:** `grupo_entrada` (Reentrant, acepta mientras otro
  ejecuta), `grupo_worker` (MutuallyExclusive, serializa), `grupo_estado`
  (MutuallyExclusive, no se congela durante un movimiento).
- **Executor:** `MultiThreadedExecutor(num_threads=4)`.
- **Limitación conocida:** el broker **no controla la pinza**; la pinza se
  comanda por separado con `GripperCommand` (ver `gripper.py`).

> **Código de depuración pendiente de limpiar** (logs temporales):
> `broker.py:204-210` imprime `GUARDADO goal_id=…`/`ENCOLADO …`, y
> `broker.py:317-320` imprime `BUSCANDO goal_id=…`. No afectan la lógica pero son
> ruido de desarrollo.

### 5.2 `politicas.py` — Políticas de cola (Ítem 3 RB-2)

- **`Pedido`**: `goal_handle`, `goal_id`, `client_id`, `priority`, `joint_positions`,
  `t_llegada`, `t_inicio_ejec`, `fin` (Event), `resultado`, `lanzado`; propiedad
  `espera_s` = ahora (o `t_inicio_ejec`) − `t_llegada`.
- **`Politica`** (base): `siguiente(pendientes)` devuelve **índice** o `None`;
  `atendido(pedido)` hook.
- **`FIFO`** (`nombre='fifo'`): índice de menor `t_llegada`. Línea base que
  ignora prioridad.
- **`SegundaPolitica`** (`nombre='prioridad'`): `puntuacion = priority + espera_s/tau`;
  elige el **máximo**, desempate por el **más antiguo** (`-t_llegada`). Con
  `tau=12 s`, prioridad 1 que espera 24 s iguala a prioridad 3 recién llegada →
  urgencia manda pero nadie se eterniza.
- `POLITICAS = {'fifo': FIFO, 'prioridad': SegundaPolitica}`.

### 5.3 `fk.py` — Cinemática directa y validaciones (Ítem 1 RB-2)

- `JOINT_NAMES = ['1_Joint' … '6_Joint']`.
- **Tabla DH** (`DH`): `d1=134.75`, `a2=-110`, `a3=-96`, `d4=63.4`, `d5=75.55`,
  `d6=50`, con offsets `-90°` en J2/J4 y `+90°` en J5. La posición del efector es
  la 4.ª columna de `T_0_6`.
- **`fk_matriz(q)`** / **`fk(q)`** → `(x, y, z)` en mm (sin NumPy, matrices 4x4).
- **`JOINT_LIMITS`** (rad): J1 ±2.93, J2 ±2.36, J3 ±2.53, J4 ±2.58, J5 ±2.93,
  J6 ±3.14.
- **`ALCANCE_MIN_MM=80`, `ALCANCE_MAX_MM=480`**.
- **`dentro_de_limites(q)`**, **`dentro_del_workspace(q)`** (`r=‖xyz‖` en
  [80,480] y `z>=0`), **`paso_articular(q_desde, q_hasta)`** (máx `|Δq|`).
- **Discrepancia DH:** `fk.py` usa `d5=75.55, d6=50`; `mi_info.txt` del kit declara
  `d5=75.05, d6=60`. No se resuelve por código: verificar físicamente con
  `verificar_fk.py` (criterio error ≤ 10 mm).

### 5.4 `interprete_ordenes.py` — Nodo P1

- Parámetros: `laya_url` (default `http://127.0.0.1:8000`), `timeout_laya_s` (2.0),
  `objetos`, `colores`, `acciones`; clave desde `LAYA_API_KEY`.
- Al arrancar mide la **línea base de red** (`cliente_laya.medir_red_base`, 5×
  `GET /health`); si falla, sigue con `0.0`.
- `callback`: si `forzar_clasificador` → clasificador local; si no, `cliente_laya.preguntar`;
  ante timeout/error → clasificador + `degradada=True`. Separa
  `tiempo_red = min(base, total)` y `tiempo_computo = total − red`.
- Frase vacía → decisión `desconocido`, `permitido=False`.

### 5.5 `cliente_laya.py` — Único módulo HTTP hacia LAYA (P1)

- `_preguntas_tipadas(...)`: 5 preguntas → `choice` (acción, objeto, color),
  `score` (prioridad `0..3`), `noul` (permitido, sí/no).
- `preguntar(url, api_key, frase, timeout_s, ...)`: `POST {url}/v1/systemone`
  con `state.body` + `questions`; lee `cuerpo['answers']` (o el cuerpo);
  `_extraer` tolera claves `choice/score/noul/label/value/answer`; normaliza
  `prioridad` a `0..255` y `permitido` a bool (string/number/bool).
- `medir_red_base(url, api_key, n=5)`: mediana de `GET /health`.
- Si el servidor real trae otro nombre de campo, se ajusta `_extraer` (usar
  `herramientas/probar_laya.py` para ver la respuesta cruda).

### 5.6 `clasificador_palabras_clave.py` — Respaldo sin red (P1)

- Diccionarios `ACCIONES` (agarrar/soltar/mover/detener con sinónimos), `OBJETOS`
  (cubo/cilindro/esfera), `COLORES`, y lista `PROHIBIDO`
  (`destornillador`, `tijera(s)`, `cuchillo`, `persona`, `mano`).
- `clasificar(frase)` devuelve **el mismo dict** que `cliente_laya` para que el
  nodo los trate igual. `permitido=False` si hay palabra prohibida o acción
  desconocida; **prioridad siempre 1** (no estima urgencia).
- Búsqueda por substring (`palabra in frase`), determinística, sensible a la
  lista (falla con sinónimos no listados).

### 5.7 `cliente.py` — Cliente de trazas (RB-2)

- Envía poses de un CSV (6 ángulos/fila; vacío = 2 poses de prueba) al broker.
- Parámetros: `client_id`, `priority`, `traza`, `repeticiones`, `pausa_s`,
  `modo` (`secuencial`|`asincrono`), `inicio_unix` (arranque sincronizado).
- **secuencial**: un goal y espera su resultado. **asincrono**: manda toda la
  traza sin esperar → llena la cola (es la carga que hace decidir a la política).
- **Nunca publica `/joint_states`**; solo envía goals a `move_arm`.

### 5.8 `percepcion_camara.py` — Detección de color (P2)

- Suscribe `sensor_msgs/Image` (`/image_raw`, de `usb_cam`), convierte con
  `cv_bridge`, umbraliza por **HSV** (`COLORES_HSV` para rojo/amarillo/verde/azul),
  elige el mayor contorno (`area_min`) y marca `estable` tras `confirmaciones`
  fotogramas iguales.
- Publica `std_msgs/String` JSON en `/objeto_detectado`:
  `{color, presente, estable, cx, cy, t}`. **No mueve el brazo.**

### 5.9 `orquestador_item2.py` — Orquestador definitivo (P2)

Puente decisión → broker. **No publica `/joint_states`** (solo lee para el error
FK; como el broker publica en grados, él convierte a radianes al leer, `_on_joint_states`).

- Suscribe `/orden_decidida` (decisiones JSON) y `/objeto_detectado`; acción
  `move_arm` (`ActionClient`) y `gripper_command` (`Pinza`).
- Hilo trabajador (`queue.Queue`) atiende **una orden completa a la vez**.
- Por orden:
  1. `permitido=False` → **rechazo `no_permitida`** en `rechazos_orquestador.csv`
     (sin encolar).
  2. `detener` → limpia la cola de órdenes y vuelve a HOME.
  3. Acción no reconocida con color → se comporta como `mover`; sin color →
     rechazo `objeto_desconocido`.
  4. Para `agarrar`/`mover`/`llevar` → **mueve primero a `POSE_BUSQUEDA`**
     (espacio de detección) y, si `usar_camara`, espera `/objeto_detectado` con el
     color estable (`espera_deteccion_s`); si no, rechazo `sin_deteccion`.
  5. `priority = prioridad * escala_prioridad (85)`, acotado a `0..255`.
  6. Ejecuta el plan (`poses.plan_agarrar`, `plan_soltar`, `plan_pick_and_place`),
     troceando movimientos con `poses.escalonar` (≤ `paso_max_rad`) y comandando
     la pinza entre poses.
  7. Registra el intento y el **error FK** con `intentos`.
- Parámetros: `client_id` (`p2`), `escala_prioridad` (85), `paso_max_rad` (1.6),
  `usar_camara` (true), `espera_deteccion_s` (3.0), `timeout_goal_s` (30.0),
  `gripper_action` (`gripper_command`), `gripper_abierto` (0.0),
  `gripper_cerrado` (0.04), `gripper_esfuerzo` (50.0), `topico_decision`
  (`orden_decidida`), `topico_deteccion` (`objeto_detectado`), `archivo_rechazos`
  (`rechazos_orquestador.csv`), `archivo_intentos` (`intentos.csv`).

### 5.10 `poses.py` — Poses fijas / IK precalculada (P2)

- Poses en **grados** (convención del kit) y conversión a radianes: `POSE_HOME`,
  `POSE_BUSQUEDA`, `POSE_RECOGIDA`, `POSE_REPARTO` y `DESTINOS` por color
  (amarillo/rojo/verde/azul).
- `a_radianes(grados)`, `escalonar(q_desde, q_hasta, paso_max)` (trocea en
  waypoints para que cada salto ≤ paso_max).
- Planes: `plan_agarrar()` (abrir → recogida → cerrar; **sin** `busqueda`, que ya
  la hizo el orquestador antes de detectar), `plan_soltar(color)`,
  `plan_pick_and_place(color)` (lista de pasos `('gripper','abrir'|'cerrar')` o
  `('pose', nombre, grados)`).
- Las posiciones son **conocidas** (no se busca el objeto; la cámara solo confirma
  color). Verificar con `herramientas/verificar_poses.py` antes de la demo.

### 5.11 `gripper.py` — Pinza (P2)

- Envoltura de un `ActionClient` a `control_msgs/action/GripperCommand`.
- `Pinza(nodo, accion, abierto, cerrado, esfuerzo, timeout)` con `abrir()`,
  `cerrar()`, `disponible()`; usa espera por evento (seguro con
  `MultiThreadedExecutor`). Calibrar con `herramientas/probar_pinza.py`.

### 5.12 `intentos.py` — Registro de intentos y error FK (P2)

- `CABECERA = [intento, frase, objeto, color, zona, exito, q_solicitada,
  q_alcanzada, error_mm]`.
- `error_mm(q_sol, q_alc) = ‖fk(q_sol) − fk(q_alc)‖` (mm).
- `preparar_csv`, `registrar`, `tasa_exito` (exitos/total).

### 5.13 `transcriptor_voz.py` — Audio → decisión (P3)

- Parámetros: `fuente` (`archivo`|`teclado`), `ruta_audio`, `google_model`
  (default `voz_google.MODELO_POR_DEFECTO`), `timeout_transcripcion_s` (5.0),
  `modo_texto_tras_fallo` (true), `n_ordenes` (≤0 = infinito),
  `csv_transcripciones` (`transcripciones.csv`), `topico_decision`
  (`orden_decidida`). Clave desde `GOOGLE_API_KEY`.
- Por orden: obtiene texto (Google; si falla/timeout → **input por teclado**),
  llama al servicio `/interpretar_orden`, publica la decisión JSON en
  `/orden_decidida` y registra en CSV
  (`t_unix, ruta_audio, texto, metodo, t_tr, t_dec, t0..t3`).

### 5.14 `voz_google.py` — Cliente HTTP a Google AI Studio (P3)

- `MODELO_POR_DEFECTO = 'gemini-3.8-flash'` (**inconsistente** con docs/PASOS que
  usan `gemini-2.5-flash`, ver §12).
- `transcribir(ruta, api_key, modelo, timeout_s)`: `POST
  {URL_BASE}/{modelo}:generateContent` con `x-goog-api-key` y audio en
  `inline_data` base64; extrae `candidates[0].content.parts[*].text`.
- `clave_desde_entorno()` lee `GOOGLE_API_KEY`; soporta `.wav/.mp3/.m4a/.aac/…`.

### 5.15 `cliente_texto.py` — Frase por teclado (P2)

- `input()` → `/interpretar_orden` → publica la decisión JSON en `/orden_decidida`
  (con `client_id`). Permite que los 4 integrantes manden órdenes en paralelo sin
  voz. Parámetros: `client_id`, `n_ordenes` (≤0 = infinito), `topico_decision`.

### 5.16 `orquestador.py` — Orquestador mínimo (NO registrado)

- Versión mínima de la P2/P3: escucha `/orden_decidida`, rechaza `no_permitida`/
  objeto desconocido, elige pose por color (parámetro `mapa_poses`, placeholder) y
  envía goal. Registra `rechazos_orquestador.csv`, `intentos.csv`,
  `tiempos_acciones.csv`. **No está en `setup.py`**; se conserva como andamiaje.
  El orquestador en uso es `orquestador_item2`.

---

## 6. `analisis/` — instrumentación de bags y métricas

| Archivo | Qué hace | Requiere ROS 2 |
|---|---|---|
| `verificar_publicadores.py` | `ros2 topic info /joint_states --verbose`; exige **exactamente 1** publicador llamado `arm_broker`. Código 0 = OK, 1 = fallo. `--salida` guarda evidencia. **Correr antes de cada grabación.** | Sí |
| `exportar_csv.py` | Lee un bag con `rosbag2_py` y escribe `queue_state.csv` + `joint_states.csv`. Uso: `exportar_csv.py <carpeta> [--salida .]`. | Sí |
| `exportar_csv_directo.py` | Igual **sin ROS 2**: abre el `.db3` como SQLite y decodifica CDR a mano. Validado contra fifo/ y prioridad/. | No |
| `metricas.py` | Calcula espera media/p95 por prioridad, **inanición** (espera máxima de la prioridad más baja), **equidad de Jain** (por nº de goals y por espera), contadores y **exclusión mutua** (reentradas/doble reserva, resolución 200 ms). Genera `comparacion_politicas.png`. Uso: `metricas.py fifo/queue_state.csv prioridad/queue_state.csv --salida …`. Toma el nombre de la política del **nombre de la carpeta**. | No |
| `metricas_directo.py` | Igual sin ROS 2; lee una subcarpeta por política dentro de `--datos`, guarda `resumen_metricas.txt` + figura. | No |
| `generar_datos_analisis.py` | Pipeline completo: exporta `./fifo` y `./prioridad` a `datos_analisis/`, calcula métricas y figura. | No |

Convención de `metricas.py`: **prioridad mayor = más urgente**, por lo que el
**índice de inanición** es la espera máxima de la prioridad **más baja**.

---

## 7. `herramientas/` — prueba y medición

| Archivo | Qué hace | Dónde / cuándo |
|---|---|---|
| `probar_laya.py` | `GET /health` + `POST /v1/systemone` **sin ROS 2**; imprime JSON crudo. | **Primero**, al tener IP de LAYA |
| `medir_item1.py` | Corre las frases: 2 llamadas por frase (normal y `forzar_clasificador=True`), guarda CSV, imprime mediana/p95 (total/red/cómputo) y exactitud si hay `esperado_*`. | Jetson, con el nodo P1 |
| `generar_carga.py` | Genera `carga.csv` (40 poses, semilla 7) importando `fk`; traza idéntica para FIFO y prioridad. | Antes de correr |
| `simular_corrida.py` | Simulador por eventos usando `politicas.py` tal cual; predice esperas, p95, inanición y Jain → `prediccion.md`. | **Antes de medir** |
| `validar_rechazos.py` | Demuestra las 3 causas (`limite`, `workspace`, `paso`) y comprueba que quedan en `rechazos.csv`. | Con el broker arriba |
| `verificar_fk.py` | En la **Jetson con `pymycobot`** (sin driver): 4 poses, `fk(q)` vs `get_coords()`, criterio ≤ 10 mm. | Antes de la demo |
| `verificar_poses.py` | Valida las poses del orquestador con `fk.py` **sin mover el brazo**; marca saltos > `--paso-max`. | Antes de la demo |
| `probar_camara.py` | Prueba la cámara por OpenCV **sin ROS 2**; `--guardar frame.png`. | Antes de la demo |
| `probar_pinza.py` | Abre/cierra la pinza para calibrar `abierto/cerrado/esfuerzo` (driver arriba). | Antes de la demo |
| `probar_transcripcion.py` | Prueba la transcripción de un `.wav` **sin ROS 2**. | Antes de la demo P3 |
| `graficar_tiempos.py` | Genera el desglose de tiempos (etapas) → `.png`. | Evidencia P3 |
| `completar_informe.py` | Escribe los ítems 2 y 3 del RB-2 dentro de `Informe.docx` (ese `.docx` no está en el repo). | Entrega |
| `frases_ejemplo.csv` | 8 frases de prueba con columnas `esperado_*`. | Validación P1 |
| `carga.csv` | Copia de la traza (misma que la raíz). | — |

---

## 8. Documentación

- `docs/CONTEXTO.md` — guía general (problema, las dos etapas, arquitectura de
  máquinas, LAYA, estado del repo, orden de lectura). Es la mejor introducción.
- `docs/ITEM_1.md` / `ITEM_2.md` / `ITEM_3.md` — guías paso a paso por pregunta
  (instalación de LAYA, cadena de agarre, voz).
- `docs/ITEM_*_EVIDENCIAS.md` — plantillas/notas de evidencia por ítem.
- `PASOS/PASOS_ITEM_*.md` — secuencias de arranque por ítem.
- `TERMINALES.md` — comandos exactos para grabar bags y calcular métricas.
- `README.md` — detalle del RB-2 (arquitectura, políticas, admisión, DH,
  predicción).
- `README_PARCIAL.md` — detalle fino de la P1.
- `item2/README_ITEM2.md` + `README_ITEM2_parte_2.md` — guía de copiado y demo de
  la P2; `CAMBIOS_ITEM2.md`, `DATOS_FALTANTES.md`, `COMO_USAR_ITEM2.md`.
- `docs/item3/README_ITEM3.md` — guía de la P3.

---

## 9. Flujos detallados

### 9.1 P1 — Interpretar una frase

```
frase ─► interprete_ordenes.callback
   ¿forzar_clasificador?
   ├─ no → cliente_laya.preguntar ──HTTP──► LAYA /v1/systemone
   │        timeout_laya_s agotado / error
   │           └─► clasificador.clasificar  (degradada=True, fuente='palabras_clave')
   │        OK → decisión tipada (degradada=False, fuente='laya')
   │             tiempo_red = min(línea_base, total); tiempo_computo = total − red
   └─ sí → clasificador.clasificar
   ▼
Response(accion, objeto, color, prioridad, permitido, motivo, degradada, fuente, tiempos)
```

### 9.2 P2 — Agarre autónomo

```
cliente_texto / transcriptor_voz → /interpretar_orden → decisión
        └─► publica JSON en /orden_decidida
                      │
              orquestador_item2._on_decision → cola interna (hilo)
                      │
        ¿permitido? no → rechazos_orquestador.csv (sin encolar)
                   sí → ¿detener? → limpia cola + HOME
                        ¿necesita color? → BUSQUEDA (espacio de detección)
                                          → espera /objeto_detectado (estable)
                        prioridad = prioridad*85
                        por cada paso del plan:
                            move_arm (goal) → BROKER → /joint_states
                            gripper abrir/cerrar → gripper_command
                        registra intento + error_mm en intentos.csv
```

### 9.3 P3 — De la voz al movimiento

```
audio (.wav) → transcriptor_voz → Google AI Studio (HTTPS)
   fallback timeout/sin internet → teclado (input)
        │ texto
        ▼
   /interpretar_orden (P1) → decisión → /orden_decidida → orquestador_item2 (P2) → brazo
   Registro en transcripciones.csv: t0 (fin habla) … t3 (decisión)
```

### 9.4 Ciclo de vida de un goal en el broker

```
goal_callback (admisión: finitos→límites→workspace→paso→cola)  ──REJECT──► rechazos.csv
        │ACCEPT (reserva cupo)
        ▼
handle_accepted_callback (crea Pedido en pendientes)
        ▼
_worker (timer 20 ms)  ──el brazo libre──►  politica.siguiente() → pop
        ▼
execute_callback  (revalida paso → interpola → publica /joint_states → feedback)
        ▼
succeed/canceled/abort  →  libera brazo, politica.atendido(), contadores
```

### 9.5 FIFO vs prioridad con envejecimiento

| | FIFO | Prioridad + aging |
|---|---|---|
| Criterio | `min(t_llegada)` | `max(priority + espera_s/tau)`, empate → más antiguo |
| Ignora | prioridad | — |
| Efecto | orden estricto de llegada | urgencia manda pero nadie se eterniza |
| Uso | línea base para aislar el efecto del aging | política de la demo |

---

## 10. Configuración y comandos

### 10.1 Red (igual en las 5 máquinas)

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start
```

### 10.2 Repo y compilación

```bash
git clone https://github.com/rGsmueL/parcial.git ~/rb2_ws
cd ~/rb2_ws
pip3 install requests --break-system-packages
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

### 10.3 Arranque típico P2 (Jetson)

```bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0   # cámara
ros2 run jetcobot_driver sync_plan_nx                                       # driver
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000
ros2 run arm_broker percepcion_camara --ros-args -p topico_imagen:=/image_raw
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true
ros2 run arm_broker cliente_texto --ros-args -r __node:=cliente_<nombre> \
  -p client_id:=<nombre> -p n_ordenes:=0
```

### 10.4 Verificaciones previas

```bash
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt
python3 herramientas/validar_rechazos.py --paso-max 1.2
python3 herramientas/verificar_poses.py --paso-max 1.6
ros2 topic echo /objeto_detectado
```

### 10.5 Bags y métricas

```bash
ros2 bag record -o fifo      /arm/queue_state /joint_states
ros2 bag record -o prioridad /arm/queue_state /joint_states
python3 analisis/exportar_csv.py fifo/ --salida fifo/
python3 analisis/exportar_csv.py prioridad/ --salida prioridad/
python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv \
  --salida comparacion_politicas.png
# Sin ROS 2 (PC Windows):
python analisis/generar_datos_analisis.py
```

---

## 11. Glosario

- **RB-2**: Reto Brazo 2 (etapa previa: FK + broker + políticas).
- **Broker**: nodo único que serializa el acceso al brazo y publica `/joint_states`.
- **Goal**: petición a la acción `move_arm` (pose + client_id + priority).
- **Pedido**: goal ya aceptado y encolado (estructura de `politicas.py`).
- **Aging / envejecimiento**: `espera_s/tau` que sube la puntuación de un pedido
  mientras espera.
- **Inanición**: espera máxima de la prioridad más baja; el aging la acota.
- **Degradada**: respuesta del clasificador local cuando LAYA no contesta.
- **LAYA**: motor de decisiones tipadas (choice/score/noul) servido por HTTP
  (`laya-serve`), corre local. No es un nodo ROS 2.
- **Pose**: 6 ángulos articulares; en `poses.py` en grados, al broker en radianes.
  `/joint_states` se publica en grados (el driver `sync_plan_nx` exige grados);
  los *rechazos.csv* del broker y la FK usan radianes.

---

## 12. Inconsistencias, riesgos y pendientes (importante para una IA)

### Inconsistencias entre documentos y código

| Tema | Qué hay | Qué hacer |
|---|---|---|
| Modelo de transcripción | `voz_google.MODELO_POR_DEFECTO = 'gemini-3.8-flash'`; `PASOS.txt` y `PASOS/PASOS_ITEM_3.md` usan `gemini-2.5-flash`; `README_PARCIAL.md` habla de `gemini-2.5-flash` | Confirmar el modelo disponible en Google AI Studio y unificar; pasar `-p google_model:=…` explícito |
| Sintaxis de métricas | `PASOS.txt` (líneas ~149-154) usa `exportar_csv.py <bag> <csv>` y `metricas.py … --outdir` | **Desactualizado**. Lo correcto (ver `TERMINALES.md`): `exportar_csv.py fifo/ --salida fifo/` y `metricas.py fifo/queue_state.csv prioridad/queue_state.csv --salida …` |
| `config/equipo.env`, `conectar_reto.sh` | Citados por docs viejos | **No existen / no se usan**: exportar variables a mano |
| URL del repo | `PASOS.txt` clona `reto2_robotica` en `~/rb2_ws` | Este repo es `rGsmueL/parcial`; ajustar ruta real |
| Tabla DH | `fk.py`: `d5=75.55, d6=50`; `mi_info.txt`: `d5=75.05, d6=60` | Verificar físicamente con `verificar_fk.py`; no se arregla por código |
| `README_RETO2.md` | Existía en el commit `v1` | Borrado; su contenido es `README_PARCIAL.md` |
| Orquestador | `orquestador_item2` (definitivo) vs `orquestador` (mínimo, **sin entry point**) | Usar **solo** `orquestador_item2` |
| `ROS_DOMAIN_ID` | 43 = 42 + nº de equipo | Igual en las 5 máquinas antes de medir |

### Riesgos de método / bugs latentes

- **`cliente_laya._extraer`** tolera varios nombres de campo pero **no está
  confirmado** contra el servidor real: probar con `probar_laya.py` y ajustar si
  el JSON difiere.
- **`medir_red_base`** aproxima el cómputo como `total − /health`; si LAYA trae un
  campo de tiempo propio, usarlo directo.
- **`clasificador_palabras_clave`**: búsqueda por substring y listas fijas → falsos
  negativos con sinónimos no listados; prioridad siempre 1.
- **`broker.py`** tiene logs de depuración (`GUARDADO`/`BUSCANDO`/`ENCOLADO`) que
  conviene limpiar antes de la entrega.
- **Cámara**: `percepcion_camara` solo confirma color y estabilidad (no localiza
  el objeto en 3D); las poses son fijas. Si se mueve el objeto, el agarre falla.
- **`escalonar`**: un salto `AZUL→HOME` es ~1.98 rad; por eso el broker usa
  `paso_max_rad:=1.6` (o subir ambos pasos a 2.0). Si el orquestador trocea pero
  el broker valida con 1.2 por defecto, habrá rechazos `paso`.
- **DH no validado en hardware**: el error FK puede degradar el error de agarre
  reportado.

### Evidencias esperadas al final

`rechazos.csv` · `rechazos_orquestador.csv` · `resultados_calma.csv` /
`resultados_carga.csv` · `prediccion.md` (antes de medir) · bags `fifo/` y
`prioridad/` · `comparacion_politicas.png` · `intentos.csv` (10 intentos) ·
`transcripciones.csv` + audios · tabla de 5 órdenes habladas · desglose de
tiempos + figura · video P2 (3 min) y video P3 sin internet · `publicadores.txt`.

---

## 13. Índice rápido de archivos (una línea)

**`src/arm_broker_interfaces/`**: `MoveArm.action` (acción del brazo),
`QueueState.msg` (telemetría de cola), `InterpretarOrden.srv` (servicio P1),
`CMakeLists.txt`/`package.xml` (build ament_cmake).

**`src/arm_broker/arm_broker/`**: `broker.py` (ActionServer + worker único +
publicador único), `fk.py` (DH + validaciones), `politicas.py` (FIFO / aging),
`cliente.py` (cliente de trazas), `interprete_ordenes.py` (nodo P1),
`cliente_laya.py` (HTTP LAYA), `clasificador_palabras_clave.py` (respaldo local),
`percepcion_camara.py` (detección de color), `orquestador_item2.py` (orquestador
P2), `poses.py` (poses fijas + escalonado), `gripper.py` (pinza),
`intentos.py` (intentos + error FK), `transcriptor_voz.py` (nodo P3),
`voz_google.py` (HTTP Google AI Studio), `cliente_texto.py` (frases por teclado),
`orquestador.py` (mínimo, sin entry point). `setup.py` registra los 7
ejecutables; `package.xml` declara `rclpy`, `sensor_msgs`,
`arm_broker_interfaces`, `std_msgs`, `control_msgs`, `cv_bridge`.

**`analisis/`**: `verificar_publicadores.py`, `exportar_csv.py`,
`exportar_csv_directo.py`, `metricas.py`, `metricas_directo.py`,
`generar_datos_analisis.py`.

**`herramientas/`**: `probar_laya.py`, `medir_item1.py`, `generar_carga.py`,
`simular_corrida.py`, `validar_rechazos.py`, `verificar_fk.py`,
`verificar_poses.py`, `probar_camara.py`, `probar_pinza.py`,
`probar_transcripcion.py`, `graficar_tiempos.py`, `completar_informe.py`,
`frases_ejemplo.csv`, `carga.csv`.

**Raíz**: `README.md`, `README_PARCIAL.md`, `TERMINALES.md`, `PASOS.txt`,
`carga.csv`, `frases_50.csv`, `Parcial_Gran_Reto_JetCobot.docx`, `errroes.docx`.

**Guías**: `docs/` (CONTEXTO + ITEM_1/2/3 + evidencias + item3/), `PASOS/`,
`item2/` (fuente de la P2).
