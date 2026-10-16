# RUNBOOK P2 — agarre (pinza + cámara `/image_raw` + broker)

Cadena: frase → decisión → orquestador → broker → `/joint_states` (grados) → driver → brazo,
con cámara y pinza reales. Solo lo necesario para la demo.

Puntos clave:
- **Único publicador de `/joint_states`** = `arm_broker` (`broker`); nunca lances otro.
- La cámara publica en **`/image_raw`** (no `/camera/image_raw`).
- Pinza en escala del kit **0..100**: `gripper_abierto:=100`, `gripper_cerrado:=15`.

## Entorno (en CADA terminal)
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER=<IP_JETSON>:11811
ros2 daemon stop; ros2 daemon start
```

## Compilar (una vez)
```bash
cd ~/rb2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

---

## Terminales

### T1 — Cámara
```bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0
ros2 topic list | grep image    # debe salir /image_raw
```

### T2 — Driver del brazo
```bash
ros2 run jetcobot_driver sync_plan_nx
```

### T3 — Broker (único publicador de `/joint_states`)

El \ solo indica que se continua abajo porque la longitud del comando es muy larga
```bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=2.0 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1
```

### T4 — Nodo de pinza (expone la acción `gripper_command`)
```bash
ros2 run arm_broker pinza_pymycobot --ros-args -p puerto:=/dev/ttyUSB0
```
> Compite por el puerto serie con el driver (T2). Si falla, ver sección "Pinza no se mueve".

### T5 — Percepción de cámara (detecta el color en las 4 posiciones)
```bash
ros2 run arm_broker percepcion_camara --ros-args -p topico_imagen:=/image_raw
```
> Publica `/objeto_detectado` con el mapa `{slot: color}` de las 4 posiciones (ver `zonas.py`).

### T6 — Orquestador 
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p usar_zonas:=true \
  -p gripper_abierto:=100.0 -p gripper_cerrado:=15.0 -p gripper_timeout_s:=5.0
```
Con `-p usar_zonas:=true` (por defecto) resuelve en qué de las 4 posiciones está el color pedido;
si el color no está en ninguna, rechaza con causa `color_no_encontrado`. Para volver al
comportamiento viejo de pose única, `-p usar_zonas:=false`.
Sin pinza física, añade: `-p gripper_habilitada:=false`
### T7— Interprete de ordenes
```bash
ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP_PC>:8000 -p timeout_laya_s:=3.0
```

### T8 — Cliente (una terminal por persona)
```bash
ros2 run arm_broker cliente_texto --ros-args \
  -r __node:=cliente_1 -p client_id:="nombre" -p n_ordenes:=0
```
Cambia `__node`/`client_id` por persona (`cliente_luis`/`luis`). Ordenes: `agarra el cubo rojo`,
`suelta`, `mueve el cubo azul`, `detener`.

---

## Verificación
```bash
ros2 action list -t | grep grip
ros2 topic echo /objeto_detectado --once
ros2 topic echo /joint_states --once          # sale en GRADOS (no "corregir")
ros2 action send_goal /gripper_command control_msgs/action/GripperCommand \
  "{command: {position: 100.0, max_effort: 50.0}}"
python3 analisis/verificar_publicadores.py     # 1 coincidencia = arm_broker
```

## Pinza no se mueve (puerto ocupado)
```bash
fuser -v /dev/ttyUSB0
ls -l /dev/serial/by-id/
# con el driver (T2) DETENIDO:
python3 -c "import time; from pymycobot.mycobot import MyCobot; r=MyCobot('/dev/ttyUSB0',1000000); r.set_gripper_value(100,50); time.sleep(1.5); r.set_gripper_value(15,50)"
```
Opciones: compartir el puerto **(a)**; un solo nodo dueño del puerto **(b)**; calibración con el
driver detenido **(c)**; demo sin pinza con `-p gripper_habilitada:=false` **(d)**.

## Prueba de la pinza (tester, sin ROS)
```bash
python3 herramientas/probar_pinza.py
```