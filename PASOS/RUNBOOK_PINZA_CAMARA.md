# Runbook — Demo P2: pinza real + cámara `/image_raw`

> **Qué arregla este runbook**
> 1. `AttributeError: 'GripperCommand_Goal' object has no attribute 'position'` en el
>    **cliente** de la pinza (`gripper.py`) que usaba el `orquestador_item2`.
>    En ROS 2 Humble el goal va dentro de `command`:
>    `goal.command.position` / `goal.command.max_effort` (no `goal.position`).
> 2. El tópico real de la cámara es **`/image_raw`** (no `/camera/image_raw`).
>
> Todos los comandos son para la **Jetson** (bash), con el repo en `~/rb2_ws`.

---

## 0. Correcciones de código (deben estar en `~/rb2_ws/src`)

### 0.1 Cliente de la pinza y probador
`src/arm_broker/arm_broker/gripper.py` y `herramientas/probar_pinza.py`:

```diff
-        goal.position = float(posicion)
-        goal.max_effort = self.esfuerzo
+        goal.command.position = float(posicion)
+        goal.command.max_effort = self.esfuerzo
```

### 0.2 Nodo servidor de la pinza
`src/arm_broker/arm_broker/pinza_pymycobot.py` (dentro de `_execute_callback`):

```python
posicion = float(goal_handle.request.command.position)   # NO .request.position
```

Y registrado en `src/arm_broker/setup.py` (`console_scripts`):

```python
'pinza_pymycobot = arm_broker.pinza_pymycobot:main',
```

### 0.3 Cámara
El default del nodo ya es `/image_raw`. **No** pases `-p topico_imagen:=/camera/image_raw`.
`percepcion_camara` detecta el color en las **4 posiciones** del espacio delimitado (ROIs de
`src/arm_broker/arm_broker/zonas.py`) y publica el mapa `{slot: color}` en `/objeto_detectado`.

---

## 1. Entorno (ejecutar en CADA terminal)

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER=<IP_JETSON>:11811
ros2 daemon stop; ros2 daemon start
```

## 2. Compilar (una vez, tras aplicar las correcciones)

```bash
cd ~/rb2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

---

## 3. Terminales

### T1 — Cámara
```bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0
```
Comprueba el tópico real (debe ser `/image_raw`):
```bash
ros2 topic list | grep image
```

### T2 — Driver del brazo
```bash
ros2 run jetcobot_driver sync_plan_nx
```

### T3 — Broker (único publicador de `/joint_states`)
```bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1
```

### T4 — Nodo de pinza (servidor de la acción `gripper_command`)
```bash
ros2 run arm_broker pinza_pymycobot --ros-args -p puerto:=/dev/ttyUSB0
```
⚠️ Compite por el puerto serie con el driver (T2). Ver §5.

### T5 — Percepción de cámara (mapa de las 4 posiciones)
```bash
ros2 run arm_broker percepcion_camara --ros-args -p topico_imagen:=/image_raw
```

### T6 — Intérprete de órdenes (P1)
```bash
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000
```

### T7 — Orquestador (P2)
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p usar_zonas:=true \
  -p gripper_abierto:=100 -p gripper_cerrado:=15 -p gripper_timeout_s:=5.0
```
> `usar_zonas:=true` (por defecto): agarra en la posición donde la cámara vio el color pedido;
> color ausente → rechazo `color_no_encontrado`. Con `-p usar_zonas:=false` vuelve a la pose única.
Sin pinza física (demo sin hardware de pinza), añade:
```bash
  -p gripper_habilitada:=false
```

### T8 — Cliente (mandar la orden por teclado)
```bash
ros2 run arm_broker cliente_texto --ros-args \
  -r __node:=cliente_ana -p client_id:=ana -p n_ordenes:=0
```
Abre una terminal igual **por cada persona**, cambiando `__node` y `client_id`
(p. ej. `cliente_luis` / `luis`). Escribe la orden en español y pulsa Enter:
`agarra el cubo rojo`, `suelta`, `mueve el cubo azul`, `detener`.

---

## 4. Verificación rápida

```bash
ros2 topic list | grep image
ros2 topic echo /objeto_detectado --once
ros2 action list -t | grep grip
ros2 action send_goal /gripper_command control_msgs/action/GripperCommand \
  "{command: {position: 100.0, max_effort: 50.0}}"
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt   # debe dar 1 = arm_broker
```

`percepcion_camara` también arranca sin argumentos (su default ya es `/image_raw`).
`ros2 topic echo /objeto_detectado --once` debe mostrar `por_slot` con el color de cada una de
las 4 posiciones (y `null` donde no haya cubo).

---

## 5. Si la pinza no se mueve (puerto serie ocupado)

```bash
fuser -v /dev/ttyUSB0
ls -l /dev/serial/by-id/
# con el driver (T2) DETENIDO:
python3 -c "import time; from pymycobot.mycobot import MyCobot; r=MyCobot('/dev/ttyUSB0',1000000); r.set_gripper_value(100,50); time.sleep(1.5); r.set_gripper_value(15,50)"
```

Opciones:
- **(a)** probar a compartir el puerto (si abre, puede funcionar).
- **(b)** un solo nodo dueño del puerto: suscrito a `/joint_states` (`send_angles`) + acción de pinza.
- **(c)** calibración aparte con el driver detenido.
- **(d)** demo con `-p gripper_habilitada:=false`.
