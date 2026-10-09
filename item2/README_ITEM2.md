# ITEM 2 — Guía paso a paso: agarre autónomo bajo la cola del broker (Parte 1)

> Esta carpeta (`item2/`) trae **el código y la guía** de la Pregunta 2 del Parcial (8 pts):
> `frase → decisión (P1) → cola del broker (RB-2) → cámara → pose fija (IK precalculada) →
> MoveIt2/pinza → brazo`.
> Asume que **ya tienes la Pregunta 1** (`interprete_ordenes` + LAYA) y el **broker del RB-2**.
>
> Contexto: `docs/CONTEXTO.md`, `docs/ITEM_2.md`. La voz es la Pregunta 3 (`docs/item3/`).
> Enunciado: `Parcial_Gran_Reto_JetCobot.docx`.

---

## 0. Qué hay en esta carpeta y a dónde va cada archivo

| Archivo aquí (`item2/`) | Cópialo a (ruta destino) | Qué es |
|---|---|---|
| `poses.py` | `src/arm_broker/arm_broker/` | Tus poses fijas del kit (HOME/BUSQUEDA/RECOGIDA/REPARTO/DESTINOS), conversión y waypoints. |
| `gripper.py` | `src/arm_broker/arm_broker/` | Cliente de la pinza (`control_msgs/action/GripperCommand`). |
| `percepcion_camara.py` | `src/arm_broker/arm_broker/` | Nodo que lee `/camera/image_raw` (usb_cam) y publica `/objeto_detectado`. |
| `orquestador_item2.py` | `src/arm_broker/arm_broker/` | Nodo central: decisión → rechazo o secuencia de goals → pinza → intentos. |
| `intentos.py` | `src/arm_broker/arm_broker/` | Registro de los 10 intentos + `error_mm` con la FK del RB-2. |
| `cliente_texto.py` | `src/arm_broker/arm_broker/` | Frase por teclado → `/interpretar_orden` → `/orden_decidida` (para los 4 integrantes sin voz). |
| `probar_camara.py` | `herramientas/` | Prueba la cámara por OpenCV, **sin ROS 2**. |
| `verificar_poses.py` | `herramientas/` | Valida tus poses con `fk.py` **sin mover el brazo**. |
| `probar_pinza.py` | `herramientas/` | Abre/cierra la pinza para calibrar posiciones y esfuerzo. |
| `setup_entrypoints.txt` | (referencia) | Las líneas que agregas a `src/arm_broker/setup.py`. |
| `intentos.csv` | (evidencia) | Plantilla de la tabla de 10 intentos. |

> **Flujo**
> `frase → /interpretar_orden (P1) → /orden_decidida → orquestador_item2`
> si `permitido=False` → **rechazo con causa, sin encolar**;
> si no → espera `/objeto_detectado` → `move_arm` (con prioridad del modelo) → `gripper_command`.

---

## 1. Arquitectura y qué corre en cada dispositivo

```
   FRASE (texto o voz)  ──► /interpretar_orden (P1) ──► decisión
                                                          │
                                     /orden_decidida  ◄───┘
                                                          │
                     ┌────────────────────────────────────▼───────────────────────┐
                     │  JETSON                                                            │
                     │  orquestador_item2 ──(rechaza no permitidas)                      │
                     │        │ espera /objeto_detectado                                  │
                     │        │ (percepcion_camara ── /camera/image_raw ◄── usb_cam)       │
                     │        ▼                                                            │
                     │  goal move_arm (priority = modelo*85) ──► BROKER (worker único)     │
                     │        │                                         │ /joint_states → driver
                     │        └── gripper_command ──► pinza                              │
                     └──────────────────────────────────────────────────────────────────┘
```

| Dispositivo | Corre aquí |
|---|---|
| **Tu PC Windows** | `laya-serve` (decisión de la P1) |
| **Jetson** | `usb_cam`, `sync_plan_nx`, `broker`, `interprete_ordenes`, **`percepcion_camara`**, **`orquestador_item2`**, `cliente_texto` (x4), bags |
| **PC de los 4 integrantes** | `cliente_texto` (una terminal cada uno) o `transcriptor_voz` de la P3 |

> ⚠️ **Regla eliminatoria**: solo el **worker del broker** publica `/joint_states`.
> El orquestador **solo lee** `/joint_states` (para el error de FK) y **solo envía goals**.

---

## 2. Requisitos y dependencias

En la Jetson, instala lo que falte:

```bash
sudo apt install ros-humble-control-msgs ros-humble-cv-bridge ros-humble-usb-cam
python3 -m pip install opencv-python    # si usas probar_camara.py (sin ROS)
```

Edita `src/arm_broker/package.xml` y agrega estas dependencias:

```xml
  <depend>std_msgs</depend>
  <depend>control_msgs</depend>
  <depend>cv_bridge</depend>
```
(`rclpy`, `sensor_msgs` y `arm_broker_interfaces` ya están.)

---

## 3. Copiar el código, entry points y compilar

```bash
# 1) Copia los módulos y nodos al paquete
cp item2/poses.py item2/gripper.py item2/intentos.py \
   item2/percepcion_camara.py item2/orquestador_item2.py item2/cliente_texto.py \
   src/arm_broker/arm_broker/

# 2) Copia las herramientas de prueba
cp item2/probar_camara.py item2/verificar_poses.py item2/probar_pinza.py herramientas/
```

Edita `src/arm_broker/setup.py` dentro de `entry_points['console_scripts']`:

```python
    entry_points={
        'console_scripts': [
            'broker = arm_broker.broker:main',
            'cliente = arm_broker.cliente:main',
            'interprete_ordenes = arm_broker.interprete_ordenes:main',
            'transcriptor_voz = arm_broker.transcriptor_voz:main',
            'percepcion_camara = arm_broker.percepcion_camara:main',   # <-- nuevo
            'orquestador_item2 = arm_broker.orquestador_item2:main',   # <-- nuevo
            'cliente_texto = arm_broker.cliente_texto:main',           # <-- nuevo
        ],
    },
```

> **Orquestador de item3 vs item2**: `orquestador_item2` es el definitivo (cámara, pinza,
> secuencia). El `orquestador.py` de item3 era un andamiaje mínimo. Usa **solo uno**.
> Opción limpia: reemplaza `src/arm_broker/arm_broker/orquestador.py` por `orquestador_item2.py`.

```bash
source /opt/ros/humble/setup.bash
cd ~/rb2_ws                                        # ajusta a tu clone
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

---

## 4. Configuración (qué parámetro mueve qué)

### 4.1 Red ROS (todas las máquinas iguales)
```bash
export ROS_DOMAIN_ID=43                 # UNIFICAR en las 5 máquinas
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"   # IP real
ros2 daemon stop; ros2 daemon start
```

### 4.2 Broker (`paso_max_rad`)
Varias transiciones de tus poses superan el `paso_max_rad` (p. ej. `AZUL→HOME` = 1.98 rad).
Tienes **dos formas** de resolverlo; el orquestador ya trocea en **waypoints** de forma automática
(`escalonar`), así que lo más simple es dejar el broker en `1.6`:

```bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=1.5
```
Si prefieres menos waypoints, sube el paso del broker **y** el del orquestador a `2.0`:
`-p paso_max_rad:=2.0` en ambos.

### 4.3 Orquestador (parámetros clave)
| Parámetro | Default | Para qué |
|---|---|---|
| `escala_prioridad` | `85` | `priority = prioridad*85` (0..3 → 0..255). Decláralo en el informe. |
| `paso_max_rad` | `1.6` | Igual o menor que el del broker, para trocear. |
| `usar_camara` | `true` | `false` = confía en la decisión (sin esperar detección). |
| `espera_deteccion_s` | `3.0` | Cuánto espera un color estable de la cámara. |
| `gripper_action` | `gripper_command` | Nombre de la acción de la pinza. |
| `gripper_abierto` / `gripper_cerrado` | `0.0` / `0.04` | Calíbralos con `probar_pinza.py`. |
| `gripper_esfuerzo` | `50.0` | Fuerza máxima del cierre. |
| `topico_decision` | `orden_decidida` | De dónde vienen las decisiones. |

---

## 5. Pruebas ANTES de la demo (una por una)

### 5.1 Verifica las poses (sin mover el brazo, en cualquier PC)
```bash
python herramientas/verificar_poses.py --paso-max 1.6
```
Debe imprimir `OK` en todas las poses y marcar las transiciones que exceden el paso (el
orquestador las trocea).

### 5.2 Verifica la cámara (sin ROS 2)
```bash
python herramientas/probar_camara.py            # busca /dev/video0,1,2,8
python herramientas/probar_camara.py 0 --guardar frame.png
```
Anota el índice que funciona (normalmente `/dev/video0`).

### 5.3 Verifica la pinza (con el driver arriba)
```bash
# Terminal A (driver)
ros2 run jetcobot_driver sync_plan_nx
# Terminal B
python herramientas/probar_pinza.py
```
Ajusta `gripper_abierto` / `gripper_cerrado` según lo que veas.

### 5.4 Verifica la percepción con la cámara de ROS
```bash
# Terminal A: cámara
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0
# Terminal B: percepción
ros2 run arm_broker percepcion_camara
# Terminal C: mira la detección
ros2 topic echo /objeto_detectado
```
Pon un cubo de cada color y comprueba que aparece `color` y `estable:true`.

---

## 6. Arranque completo (por terminal)

**PC Windows — LAYA** (ver `docs/ITEM_1.md` §4): `laya-serve` en `0.0.0.0:8000`.

**Jetson — T0 (cámara):**
```bash
source /opt/ros/humble/setup.bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0
```

**Jetson — T1 (driver):**
```bash
ros2 run jetcobot_driver sync_plan_nx
```

**Jetson — T2 (broker, ver §4.2):**
```bash
source install/setup.bash
ros2 run arm_broker broker --ros-args -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=1.5
```

**Jetson — T3 (intérprete de la P1):**
```bash
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000
```

**Jetson — T4 (percepción):**
```bash
ros2 run arm_broker percepcion_camara --ros-args -p topico_imagen:=/camera/image_raw
```

**Jetson — T5 (orquestador):**
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p gripper_action:=gripper_command
```

**Cada integrante (su PC o la Jetson) — T6..T9:**
```bash
ros2 run arm_broker cliente_texto --ros-args -r __node:=cliente_<nombre> \
  -p client_id:=<nombre> -p n_ordenes:=0
```
Escribe p. ej. `agarra el cubo rojo` y el orquestador hará el pick-and-place.

**Antes de grabar**, verifica el publicador único (regla eliminatoria):
```bash
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt
```

👉 Continúa en **`README_ITEM2_parte_2.md`** para la demo, los 10 intentos, las métricas y el video.
