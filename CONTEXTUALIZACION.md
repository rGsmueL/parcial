# Historia del trabajo — contextualización del parcial JetCobot

> Este documento cuenta **todo lo que se ha hecho hasta ahora** en este repo, en orden y con
> el *porqué* de cada decisión. Está escrito para que cualquier persona (o cualquier agente de
> IA) pueda ponerse al día leyendo un solo archivo: qué problema se estaba resolviendo, qué se
> intentó, qué se descartó, qué se entregó y qué falta.

---

## 0. El proyecto en una frase

Parcial de robótica (ROS 2 Humble) para el brazo **JetCobot**: una frase en español entra,
pasa por un clasificador (LAYA), llega a una cola de prioridad en un **broker**, la cámara
resuelve en cuál de las **4 posiciones** está el color pedido, se elige la pose de esa posición
y el brazo la ejecuta.

```
frase → LAYA/clasificador → cola de prioridad del broker → cámara → posición → pose → brazo
```

Hay tres ítems: la cadena completa (1), la cinemática inversa / MoveIt2 (2), y la
documentación/entrega (3). Este repo es el trabajo del Ítem 2 principalmente, que es el que
más se ha desarrollado en esta historia.

**Contexto de ejecución:** el código corre en una **Jetson (Linux)**; el checkout de trabajo
es **Windows**, así que nada de `ros2 run`/`colcon` se ejecuta localmente. Muchas carpetas
(`item2/`, `CLAUDE/`, `docs/`, `arreglar_angulos_y_gripper/`, `moveit2/`) son
**carpetas-fuente**: copias "en crudo" con guías de copiado. **Solo `src/` compila y corre.**

---

## 1. El problema que originó todo: "el brazo no se mueve" (radianes ⇄ grados)

### 1.1 El descubrimiento

El broker publicaba la pose objetivo en `/joint_states` en **radianes**. El driver del kit
(`ros2 run jetcobot_driver sync_plan_nx`, nodo `control_sync_plan`) hace algo muy simple:
toma el valor que llega por `/joint_states` y lo pasa **tal cual** a `send_angles()` de
`pymycobot`. Y `send_angles()` espera **grados**.

Consecuencia: el brazo recibía, por ejemplo, `0.1887` pensando que eran `0.1887°` en lugar de
`10.81°`. **El brazo se movía pero "casi nada"** — un movimiento imperceptible. No hay error ni
excepción: solo un brazo que "no se mueve".

### 1.2 La evidencia

`reporte.txt` (raíz del repo, sin commitear) guarda el log de la corrida problemática. En la
sección `ANGULOS` el driver registraba:

```
[control_sync_plan]: Ejecutando angulos: [0.1886700921519945, -0.44628068974595006, ...]
```

Esos valores coinciden exactamente con `POSE_BUSQUEDA = [10.81, -25.57, 15.9, -72.33, 2.02, -32.69]`
convertida a radianes (`10.81° = 0.18867 rad`). Es decir: el driver estaba recibiendo
**radianes** → el brazo se movía nada.

### 1.3 El arreglo (en `src/`, la fuente de verdad)

Se corrigió en dos líneas, en la frontera exacta:

- `src/arm_broker/arm_broker/broker.py`, en `mover()` (el ÚNICO método que publica
  `/joint_states`):
  ```python
  msg.position = [float(math.degrees(v)) for v in q]   # radianes -> grados
  ```
- `src/arm_broker/arm_broker/orquestador_item2.py`, en `_on_joint_states` (el orquestador solo
  **lee** ese tópico para medir el error de FK):
  ```python
  self.q_actual = [float(math.radians(v)) for v in msg.position[:6]]   # grados -> radianes
  ```

**Regla mental que quedó escrita en todas partes:** internamente (FK, límites,
`paso_max_rad`, `q_actual`, `rechazos.csv`, goals `move_arm`) todo es **radianes**; solo
`/joint_states` —la frontera con el driver— sale en **grados**. El cambio quedó documentado en
`docs/grados/CAMBIOS_GRADOS.md` (qué, dónde, porqué y qué NO cambió).

---

## 2. La carpeta `CLAUDE/` (hecha con otra IA) y por qué se comparó

La carpeta `CLAUDE/` fue generada por la IA de Claude como propuesta paralela para el mismo
problema. Su enfoque era distinto: un parámetro configurable **`factor_compensacion_motor`**
(por defecto `1.0`) con el que broker y orquestador se "compensaban" mutuamente, en lugar del
`math.degrees`/`math.radians` fijo de `src/`. La justificación estaba en
`CLAUDE/PARCHE_COMPENSACION_MOTOR.md`.

**Pregunta clave que dio origen al trabajo:** ¿cuál solución es mejor, la de `src/` o la de
`CLAUDE/`?

### Veredicto: se quedó la de `src/` (`math.degrees` fijo)

| Criterio | `src/` (grados fijos) | `CLAUDE/` (factor configurable) |
|---|---|---|
| Fuente de verdad | una sola (el código) | dos (deben coincidir broker↔orquestador) |
| Riesgo de error | bajo: `math.degrees()` dice exactamente lo que hace | alto: si broker y orquestador se desincronizan, el error de FK queda mal escalado |
| Default `1.0` | no existe | **reintroduce el bug sin darte cuenta** |
| Claridad | explícita | implícita |

De `CLAUDE/` **sí se adoptó** lo bueno: el aviso de unidades al arrancar, `gripper_habilitada`
y el rediseño de 3 acciones (abajo).

---

## 3. Segundo problema: "la pinza no hace nada"

El brazo ya se movía, pero la pinza nunca se abría ni cerraba. Diagnóstico completo en
`docs/grados/PINZA_NO_SE_MUEVE.md`.

### Las tres causas raíz

1. **El driver del kit no expone la acción `gripper_command`** (`control_msgs/action/GripperCommand`).
   `sync_plan_nx` solo escucha `/joint_states`. El orquestador esperaba esa acción y fallaba
   siempre.
2. **Los valores calibrados no coinciden.** El orquestador usaba `abierto=0.0, cerrado=0.04`
   (convención ROS en metros), pero el script probado del kit (`item2/5.py`) usa la escala
   **0–100**: abrir `100`, cerrar `15`.
3. **Timeout heredado.** La pinza reutilizaba `timeout_goal_s` (30 s, pensado para el brazo),
   así que cada comando fallido bloqueaba la demo **30 segundos**.

La evidencia en `reporte.txt`:

```
[orquestador_item2]: 🖐  pinza abrir (0.0)
   ... 30 segundos de silencio ...
[orquestador_item2]: la acción de la pinza no aparece (¿driver arriba?)
```

### Lo que se decidió

- Que la pinza pudiera **simularse** (`-p gripper_habilitada:=false`) para no bloquear la demo.
- Darle un **timeout propio** corto (5 s).
- Crear un **nodo real de pinza** que sí exponga la acción y hable con pymycobot en la escala
  del kit (100/15). Esto respeta la regla del publicador único: la regla aplica **solo a
  `/joint_states`**, y la pinza no lo toca.

---

## 4. La petición inicial (`ins.txt`) y el plan

Con todo el contexto encima, la petición fue (parafraseada): *"contextualízate con
ARQUITECTURA.md y el docx; estoy comparando `src/` con `CLAUDE/` para `lo de grados`; además
creo que no es conveniente usar ángulos porque el docx pide **MoveIt2**; uso `item2/5.py` como
referencia de pick-and-place; dame un plan para implementar MoveIt2 de forma simple, en una
carpeta aparte llamada `moveit2/`, con qué se reemplaza, por qué, y cómo aplicarlo paso a paso
para que cualquier persona lo entienda"*.

### El plan acordado (en dos entregas separadas)

1. **`arreglar_angulos_y_gripper/`** — la fusión definitiva de `src/` y `CLAUDE/`:
   `math.degrees` fijo (no el factor), más `gripper_habilitada`, `gripper_timeout_s`, el
   rediseño de 3 acciones y el nodo de pinza real. Cada archivo con su `.md` explicativo.
2. **`moveit2/`** — el Ítem 2: un planificador con dos backends (`moveit` y `ik` numérica
   propia), conectado al orquestador en un único punto (`_mover_a`), detrás de un flag
   `-p usar_moveit:=true` (default `false` => cero riesgo). MoveIt2 **solo planifica**; el
   broker sigue siendo el único que ejecuta y publica `/joint_states`.

El plan se confirmó antes de tocar nada (estábamos en modo plan), y recién con el "hazlo" se
empezó a implementar.

---

## 5. La ejecución — entrega 1: `arreglar_angulos_y_gripper/`

Versión **definitiva** que une `src/` y `CLAUDE/` sin redundancia:

| Archivo entregado | Qué es / decisión |
|---|---|
| `broker.py` | Nace de `src/`: mantiene `math.degrees` fijo en `mover()`, añade aviso de unidades al arrancar y limpia los logs de depuración (`GUARDADO`, `BUSCANDO`). |
| `orquestador_item2.py` | Fusión: lee `/joint_states` con `math.radians` (de `src/`) + `gripper_habilitada`, las 3 acciones con `self.cargando` (de `CLAUDE/`) + **`gripper_timeout_s` nuevo** (5 s, ya no cuelga 30 s). Se eliminó todo el código de `factor_compensacion_motor`. |
| `poses.py` | Los planes de las 3 acciones (`agarrar`, `soltar`, `mover`) con `plan_transportar`/`plan_pick_and_place` (de `CLAUDE/`). |
| `gripper.py` | Cliente de pinza con diagnóstico claro (de `CLAUDE/`). |
| `pinza_pymycobot.py` | **Nodo nuevo**: expone la acción `gripper_command` y por dentro llama a `set_gripper_value()` de pymycobot con la escala del kit (0–100). Se lanza el orquestador con `-p gripper_abierto:=100 -p gripper_cerrado:=15`. Documenta el conflicto del puerto serie con el driver. |
| `CAMBIOS_GRADOS_Y_GRIPPER.md` | Explica de forma sencilla qué cambió, por qué, y la regla mental de unidades. |
| `COMO_APLICAR.md` | Copiar a `src/`, registrar el entry point de `pinza_pymycobot` en `setup.py`, compilar, correr y verificar. |

**Decisiones clave de esta entrega:**
- No se mezcla el factor de `CLAUDE/` con `math.degrees`: una sola fuente de verdad.
- El nodo de pinza no toca `/joint_states` → no anula el puntaje.
- `gripper_habilitada:=false` permite demostrar toda la cadena aunque la pinza real no esté.

---

## 6. La ejecución — entrega 2: `moveit2/`

El Ítem 2 resuelto con arquitectura **"MoveIt2 solo piensa; el broker solo mueve"**:

```
orquestador_item2._mover_a
        │
        ▼
   planificador.py            (fachada única, devuelve waypoints en RADIANES)
        ├── backend 'moveit'  → planificador_moveit.py  (MoveIt2: compute_ik + plan, SOLO PLANIFICA)
        └── backend 'ik'      → ik_numerica.py          (DLS sobre el DH de fk.py, siempre disponible)
        │
        ▼
   goals move_arm → broker (único que ejecuta y publica /joint_states)
```

| Archivo entregado | Qué es / decisión |
|---|---|
| `planificador.py` | Fachada única: `planificar(origen, meta, backend, paso_max_rad, ...)` → lista de configuraciones en radianes. Elige backend, hace **fallback automático** `moveit→ik` si MoveIt2 no está, y densifica con `poses.escalonar` para que el broker nunca rechace por causa `paso`. |
| `ik_numerica.py` | IK numérica propia (mínimos cuadrados amortiguados) sobre la tabla DH de `fk.py`, **sin numpy ni MoveIt2**. Backend por defecto y plan B. |
| `planificador_moveit.py` | Backend MoveIt2 (`moveit_py`). **Solo planifica**: nunca ejecuta ni publica `/joint_states`. Fija el estado inicial explícitamente (nunca `set_start_state_to_current_state()`) porque `/joint_states` va en grados. Convierte mm→m en la frontera. Import tolerante: si falta MoveIt2, se desactiva solo. |
| `orquestador_item2.py` | El orquestador definitivo (mismo de la entrega 1) **más** el planificador conectado en `_mover_a` — el único punto de inserción. Flags: `-p usar_moveit:=true` (default `false`), `-p backend_planificador:=ik|moveit`, `-p plan_cartesiano:=true|false`. |
| `README_MOVEIT2.md` | Cómo funciona, arquitectura, modos de uso (A/B/C/D) y las dos trampas neutralizadas (grados y unidades). |
| `REEMPLAZOS.md` | Mapa archivo→destino, qué **NO** se toca y por qué (broker, poses.py, fk.py…), registro de decisiones y cómo revertir. |
| `verificar_entorno.sh` | Checklist en la Jetson: MoveIt2, moveit_py, URDF/SRDF, publicador único, grados. |
| `config/COMO_CONFIGURAR_MOVEIT.md` | Qué falta instalar (no hay URDF/SRDF/ros2_control en el repo hoy) y cómo montarlo. |
| `config/moveit_params.yaml` | Parámetros de ejemplo para el orquestador. |

**Decisiones clave:**
- MoveIt2 jamás lanza `joint_state_publisher` (sería un segundo publicador → anularía el ítem).
- El "current state" de MoveIt2 no se usa: se le pasa `origen_rad` real del orquestador.
- `usar_moveit=false` por defecto → el sistema se comporta exactamente igual que antes.
- La IK numérica es el plan B **y** el default: funciona sin MoveIt2/URDF, que hoy no existen.

---

## 7. Cierre de contexto: `AGENTS.md`

Se creó en la raíz y se mantuvo al día como **fuente para futuros agentes**: reglas duras del
reto (publicador único, worker único, claves por entorno), la trampa de unidades, los
parámetros correctos para las corridas, los scripts de verificación y la realidad del hardware.
Con las dos entregas, la sección de MoveIt2 pasó de "Opcional / NO implementado" a
"diseñada y entregada en `moveit2/` (NO aplicada a `src/`)".

---

## 8. Evidencia de que la entrega funciona (verificado aquí)

Todo corre sin ROS en este checkout de Windows; aun así se validó lo validable:

- **`py_compile` OK** en los 9 archivos Python de las dos carpetas.
- **Prueba funcional de la IK numérica** (sandbox con el `fk.py` real del repo):
  - IK converge de HOME a la posición de `POSE_RECOGIDA` con error de **0.006 mm**.
  - Trayectoria a línea recta (8 puntos, warm start) con error final **0.103 mm**.
  - `planificar()` respeta `paso_max_rad` (paso máximo observado 0.219 rad) y termina
    exactamente en la meta.
  - Con `backend='moveit'` y sin MoveIt2 instalado, el **fallback automático a `ik`** funciona
    y avisa por el canal de retorno.

Lo que **no** se puede probar aquí: MoveIt2 real, el driver, la cámara, el brazo y la pinza
física (todo eso vive en la Jetson).

---

## 9. Estado actual y siguientes pasos

### Estado
- **`src/` NO fue modificado en las entregas 1–2** (a propósito): esas carpetas son fuente con
  guía de copiado.
- `agent` entregó: `arreglar_angulos_y_gripper/`, `moveit2/` y `AGENTS.md` actualizado.
- **Entrega 3 (4 posiciones) SÍ se aplicó a `src/`** y a `arreglar_angulos_y_gripper/`: se
  agregó `zonas.py` y se actualizaron `percepcion_camara.py`, `poses.py`, `orquestador_item2.py`
  y `herramientas/verificar_poses.py` (ver §10).

### Siguientes pasos (pendientes, en orden)
1. (Opcional) Aplicar la entrega 1 a `src/` (broker, orquestador, poses, gripper, pinza) y
   registrar `pinza_pymycobot` en `setup.py`.
2. Copiar la entrega 2 a `src/` (los 3 módulos nuevos + el orquestador instrumentado; no hace
   falta tocar `setup.py` porque no hay nodos nuevos) y recompilar:
   ```bash
   colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
   source install/setup.bash
   ```
3. En la Jetson: `bash moveit2/verificar_entorno.sh` para ver si MoveIt2/URDF están o no.
4. Correr la demo: primero `backend_planificador:=ik` (seguro), luego `moveit` cuando el
   entorno esté montado; verificar publicador único y `/joint_states` en grados.

---

## 10. Entrega 3 — agarre por 4 posiciones (mapa color→posición)

**Problema:** el sistema solo manejaba **una** posición (el centro del encuadre): la cámara
devolvía la mancha de color más grande y la pose de agarre era fija. Si el cubo pedido no estaba
en ese centro, el agarre fallaba.

**Requisito:** el espacio delimitado del tapete tiene **4 esquinas** conocidas y cualquier color
puede estar en cualquiera; al pedir *"agarra/lleva \<color\>"* hay que **encontrar** ese color
entre las 4 posiciones y agarrar ahí.

**Solución (opción A: ROIs fijas por zona, sin homografía ni IK en línea):**

| Archivo | Qué cambió |
|---|---|
| `zonas.py` (**nuevo**) | **Fuente única de verdad**: `ZONAS = {slot: {roi, recogida}}`. ROIs (640×480) + pose de agarre en grados por posición. `escalar_roi()` adapta a la resolución real. |
| `percepcion_camara.py` | Detecta el color en cada ROI y publica el **mapa `{slot: color}`** (`por_slot`) además del color dominante. `estable` = el mapa completo se repitió `confirmaciones` frames. |
| `poses.py` | `RECOGIDAS[1..4]`, `recogida(slot)`, `plan_agarrar(slot)`, `plan_pick_and_place(color, slot)`. `POSE_RECOGIDA` única queda como *legacy* (`usar_zonas=false`). |
| `orquestador_item2.py` | Tras ir a `POSE_BUSQUEDA`, `_esperar_slot(color)` resuelve la posición desde `por_slot` y agarra con la pose de ese slot. Nuevo rechazo **`color_no_encontrado`**; `intentos.csv` etiqueta `zona = slot<N>_<color>`. Flag `-p usar_zonas:=true` (default). |
| `herramientas/verificar_poses.py` | Valida las 4 `RECOGIDAS` y las transiciones (agarre por slot, transporte por color). |

**Decisiones:**
- Entrega por color **sin cambios** (`DESTINOS` por color).
- Si el color no está en ninguna posición → **solo se rechaza** (`color_no_encontrado`).
- El broker **no se toca**: sigue siendo el único publicador de `/joint_states`; la frontera de
  grados (`broker.mover()` publica grados; el orquestador relee con `math.radians`) se mantiene.
- Las ROIs se midieron a 640×480 (resolución de la cámara de la demo) y `escalar_roi()` las
  reescala si la real difiere.
- Un cubo por color (asumido y confirmado antes de implementar).

**Validación hecha aquí (sin ROS):** `verificar_poses.py --paso-max 1.6` → las 8 poses (HOME,
búsqueda, 4 recogidas, reparto y 4 destinos) pasan límites y workspace; los saltos > 1.6 rad
(recogidas 3/4 y búsqueda→reparto) los trocea `escalonar`. `py_compile` OK. Aplicado a `src/` y
a la copia de `arreglar_angulos_y_gripper/` (a pedido).

**Pendiente:** re-medir las ROIs si la cámara de la demo no entrega 640×480 o si el espacio
delimitado se mueve.

---

## 11. Línea de tiempo resumida

| Etapa | Qué pasó | Dónde quedó |
|---|---|---|
| 1 | Descubrimiento del bug de grados (brazo "no se mueve") | `docs/grados/CAMBIOS_GRADOS.md`, `reporte.txt` |
| 2 | Arreglo en `src/` (`math.degrees`/`math.radians`) | `src/arm_broker/…/broker.py`, `orquestador_item2.py` |
| 3 | Propuesta paralela de `CLAUDE/` (factor configurable) | `CLAUDE/` + `PARCHE_COMPENSACION_MOTOR.md` |
| 4 | Diagnóstico de la pinza (driver sin acción, escalas, timeout) | `docs/grados/PINZA_NO_SE_MUEVE.md` |
| 5 | Comparativa y **veredicto**: `math.degrees` fijo > factor | este documento, §2 |
| 6 | Petición y plan confirmado (modo plan) | `ins.txt` |
| 7 | Entrega 1: fusión grados + pinza (definitiva) | `arreglar_angulos_y_gripper/` |
| 8 | Entrega 2: Ítem 2 con MoveIt2 + IK numérica | `moveit2/` |
| 9 | Validación sintáctica y funcional de la IK | este documento, §8 |
| 10 | Cierre de contexto para futuros agentes | `AGENTS.md` |
| 11 | Entrega 3: agarre por 4 posiciones (mapa `{slot: color}`) | `zonas.py`, `src/…/percepcion_camara.py`, `poses.py`, `orquestador_item2.py`, este documento §10 |

---

**Fuentes primarias de esta historia:** `ins.txt`, `ARQUITECTURA.md`,
`Parcial_Gran_Reto_JetCobot.docx`, `docs/grados/CAMBIOS_GRADOS.md`,
`docs/grados/PINZA_NO_SE_MUEVE.md`, `CLAUDE/PARCHE_COMPENSACION_MOTOR.md`, `reporte.txt`,
`item2/5.py`, las carpetas `arreglar_angulos_y_gripper/` y `moveit2/`, y `AGENTS.md`.