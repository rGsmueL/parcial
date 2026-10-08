# Guía: trabajar SIN LAYA y mover el brazo a una posición

Objetivo: entender qué se puede hacer **hoy**, sin los códigos del JetCobot para agarrar
un cubo por color y sin la IP de LAYA.

## 1. Idea clave

```
"agarrar el cubo rojo"          posiciones del brazo (6 ángulos q1..q6)
         │                                   │
   [LAYA, por HTTP]                [cliente.py → acción move_arm]
         │                                   │
   interprete_ordenes.py                  broker.py
   (Ítem 1: traduce la frase)               │
         │                           /joint_states
   → NO es de este reto hoy         → DRIVER sync_plan_nx (Jetson)
```

- **LAYA solo se usa en el Ítem 1** (traducir una frase a decisión). Es por HTTP y el
  nodo funciona aunque LAYA no exista: si no contesta en `timeout_laya_s` (2 s) contesta
  el clasificador local de respaldo y marca `degradada=True`.
- **Mover el brazo NO necesita LAYA.** La cadena es: `cliente.py` → acción `move_arm` →
  `broker.py` → tópico `/joint_states` → driver `sync_plan_nx` en el Jetson.
- Punto de partida: envía 6 ángulos, no colores. El color se convierte en pose por
  aparte (es el "andar" que falta), así que por ahora se mueve a posiciones fijas.

## 2. Mover el brazo a una posición, sin LAYA

### Terminal 0 — Driver (en el JETSON)

```bash
source /opt/ros/humble/setup.bash
ros2 run jetcobot_driver sync_plan_nx
```

### Terminal 1 — Broker (en tu máquina)

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"   # <-- IP real del Discovery Server
ros2 daemon stop; ros2 daemon start

cd ~/rb2_ws            # tu workspace
colcon build --symlink-install
source install/setup.bash
ros2 run arm_broker broker --ros-args -p politica:=fifo
```

### Terminal 2 — Cliente

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start

cd ~/rb2_ws
source install/setup.bash

# Opción A: sin traza, manda 2 poses de prueba
#   [0.3,0,0,0,0,0] y [-0.3,0,0,0,0,0]  (cliente.py, líneas 52-54)
ros2 run arm_broker cliente

# Opción B: mandar tu propia posición (6 ángulos en rad por fila, un CSV):
ros2 run arm_broker cliente -p traza:=carga.csv
```

Una pose de ejemplo dentro de límites: `0.3,0,0,0,0,0` (mueve el hombro). El broker
valida antes de mover: límites articulares, workspace (`z>=0`, alcance ~80–480 mm) y
paso máximo (por defecto `paso_max_rad:=1.2`, `broker.py:37`). Si el goal aparece como
"RECHAZADA", mirá el log del broker (causa en `rechazos.csv`).

### Verificación

```bash
ros2 topic echo /joint_states        # ver el brazo publicando
ros2 node list                        # debe aparecer arm_broker y el driver
ros2 action list                      # move_arm (cuando corre el broker)
```

## 3. Ítem 1 sin LAYA (solo clasificador local)

```bash
# Build de interfaces y nodo (registra el .srv, ver README_RETO2.md pasos 2-5)
cd ~/rb2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash

# Correr el nodo SIN necesidad de IP: usa el default http://127.0.0.1:8000
ros2 run arm_broker interprete_ordenes
# (si LAYA no existe solo saldrá un warning de la "línea base de red", no falla)

# Pedir una interpretación forzando el clasificador local:
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo', forzar_clasificador: true}"

# Sin forzar: si LAYA no está, contesta el clasificador igual tras 2 s (degradada).
```

Esto responde `accion/objeto/color` por palabras clave y la bandera `degradada=True`.
Es la evidencia del flujo de respaldo del Ítem 1.

## 4. Dónde están los placeholders (qué rellenar con datos del laboratorio)

| Dónde está | Qué hay hoy | Qué hacer el día del examen |
|---|---|---|
| `README_RETO2.md:88` | `http://<IP>:<PUERTO>` | Reemplazar por la IP real de LAYA al probar |
| `README_RETO2.md:108` | `-p laya_url:=http://<IP>:<PUERTO>` | Lo mismo, al correr el nodo |
| `README_RETO2.md:121` | `export LAYA_API_KEY="..."` | Poner la clave real (solo env var, nunca en el código) |
| `interprete_ordenes.py:25` | default `http://127.0.0.1:8000` | **No se toca el código**: se pasa `-p laya_url:=...` al ejecutar |
| `cliente_laya.py` | prueba varios nombres de campo (`choice`, `score`, `label`…) | Solo si la respuesta real de LAYA trae campos distintos, ajustar `_extraer()` |
| `PASOS.txt:6` y `:32` | `172.51.1.28:11811` | IP real del Discovery Server / Jetson |
| `README.md:62`, `TERMINALES.md:12` | citan `config/equipo.env` y `conectar_reto.sh` | Esos archivos **no existen en el repo**: o se crean, o se usan los `export` de PASOS.txt |

## 5. Checklist el día del examen

1. Confirmar `ROS_DOMAIN_ID` (¿43 de PASOS.txt o 47 de TERMINALES.md?) en las 5 máquinas.
2. Poner IP real del Discovery Server / Jetson.
3. Levantar driver en Jetson → broker → cliente.
4. Para el Ítem 1: `probar_laya.py` primero, luego correr `interprete_ordenes` con
   `-p laya_url:=http://<IP>:<PUERTO>` y `LAYA_API_KEY` en el entorno.
5. Medir con `medir_item1.py` sobre las 50 frases (calma + carga).