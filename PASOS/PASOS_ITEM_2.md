# PASOS ITEM 2 — agarre autónomo bajo la cola del broker (texto + audio opcional)

Guía completa desde `git clone` hasta la demo por **texto** (principal) y por **audio** (opcional).

---

## 0. Qué hace este ítem

Cadena: `frase → /interpretar_orden (P1) → /orden_decidida → orquestador_item2 → broker → brazo + pinza`.
El orquestador atiende **4 acciones** que vienen del intérprete:

| Acción | Color | Secuencia | Termina |
|---|---|---|---|
| `agarrar` | obligatorio | busqueda (detección) → abrir → recogida → cerrar | queda cargando |
| `soltar` (con color) | opcional | busqueda → reparto → destino[color] → abrir → busqueda | POSE_BUSQUEDA |
| `soltar` (sin color) | — | abre donde está → busqueda | POSE_BUSQUEDA |
| `mover` / `llevar` | obligatorio | pick-and-place completo | POSE_HOME |
| `detener` | — | limpia cola → HOME | POSE_HOME |

> Regla eliminatoria: **solo el worker del broker publica `/joint_states`**. El orquestador
> solo envía goals a `move_arm` + `gripper_command` y lee `/joint_states` para el error FK.

---

## 1. Prerrequisitos

- ROS 2 Humble en la Jetson; LAYA corriendo en tu PC Windows (ver `PASOS_ITEM_1.md`).
- Cámara USB (`usb_cam`), brazo con driver `sync_plan_nx`, pinza (acción `gripper_command`).

---

## 2. Desde `git clone`, en la Jetson

```bash
git clone https://github.com/rGsmueL/parcial.git ~/rb2_ws
cd ~/rb2_ws

source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID + 1))   # = 43 (5 máquinas iguales)
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start

pip3 install requests --break-system-packages

# Dependencias del sistema
sudo apt install ros-humble-control-msgs ros-humble-cv-bridge ros-humble-usb-cam
python3 -m pip install opencv-python          # solo para probar_camara.py

# Compilar
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

`src/arm_broker/package.xml` debe declarar `std_msgs`, `control_msgs`, `cv_bridge`.
Entry points ya registrados en `src/arm_broker/setup.py`: `broker`, `interprete_ordenes`,
`percepcion_camara`, `orquestador_item2`, `cliente_texto` (el `orquestador` viejo del item3
**no** existe / no se usa: corre **solo** `orquestador_item2`).

---

## 3. Red (igual en todas las máquinas)

```bash
export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID + 1))   # 43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start
```

---

## 4. Arranque por terminal — VÍA TEXTO (la principal)

**PC Windows**: `laya-serve` en `0.0.0.0:8000` (ver `PASOS_ITEM_1.md` §3).

**Jetson, terminal por terminal:**

```bash
# T0 — cámara
source /opt/ros/humble/setup.bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p video_device:=/dev/video0

# T1 — driver del brazo
ros2 run jetcobot_driver sync_plan_nx

# T2 — broker (único publicador del brazo)
cd ~/rb2_ws && source install/setup.bash; export ROS_DOMAIN_ID=42; export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID+1)); export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_DISCOVERY_SERVER="172.51.1.28:11811"; ros2 daemon stop; ros2 daemon start
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1

# T3 — intérprete de la P1
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000

# T4 — percepción (publica /objeto_detectado)
ros2 run arm_broker percepcion_camara --ros-args -p topico_imagen:=/camera/image_raw

# T5 — orquestador del Item 2
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p gripper_action:=gripper_command
```

**Cada integrante (T6..T9) — cliente de texto:**

```bash
cd ~/rb2_ws && source install/setup.bash
export ROS_DOMAIN_ID=42; export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID+1)); export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 run arm_broker cliente_texto --ros-args -r __node:=cliente_<nombre> \
  -p client_id:=<nombre> -p n_ordenes:=0
```

---

## 5. Frases por acción (en cualquier `cliente_texto`)

| Acción | Frases | Qué hace |
|---|---|---|
| agarrar | `agarra el cubo rojo` | toma el cubo y queda cargando |
| soltar sin color | `suelta el cubo` | abre donde está y vuelve a búsqueda |
| soltar con color | `deja el cubo en azul` | va a la zona azul, suelta y vuelve a búsqueda |
| mover | `lleva el cubo rojo` | pick-and-place completo a la zona roja y HOME |
| detener | `detente` / `para` / `alto` | limpia la cola y vuelve a HOME |

En `agarrar`/`mover` el color es **obligatorio** y la cámara debe confirmarlo; si no, la orden
se rechaza con causa `sin_deteccion`. Órdenes `permitido=False` se rechazan **sin encolar**.

---

## 6. VÍA AUDIO (opcional)

Los audios se graban en la **Raspberry Pi** y se copian a la **raíz** del workspace de cada
terminal Raspberry (la ruta de `transcriptor_voz` es relativa al directorio de trabajo).

### 6.1 Grabar y transferir (autores del audio)

```bash
# En la Raspberry que graba
arecord -l                                          # ver los dispositivos (plughw:X,Y)
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav

# Mover a la raíz del workspace en cada terminal Raspberry
scp orden_01.wav usuario@<raspberry-terminal-i>:~/rb2_ws/   # o por USB
# Renombrar por terminal si es necesario:
#   raspberry T6 → orden_T6.wav, T7 → orden_T7.wav, ...
```

Los `.wav` **no están en el repo**: los generas tú.

### 6.2 Correr por audio (reemplaza a `cliente_texto`)

```bash
cd ~/rb2_ws && source install/setup.bash
export ROS_DOMAIN_ID=42; export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID+1)); export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
export GOOGLE_API_KEY="TU_CLAVE_DE_GOOGLE_AI_STUDIO"

ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p google_model:=gemini-2.5-flash \
  -p timeout_transcripcion_s:=5.0 -p n_ordenes:=1 \
  -p topico_decision:=orden_decidida
```

El flujo es: `orden_01.wav → Gemini → texto → /interpretar_orden → /orden_decidida → orquestador_item2`.

> `transcriptor_voz` es formalmente el Item 3; aquí se usa como **vía alternativa** para dar la
> frase. Si quieres que el introductor sea quien dicte desde el teclado de la Raspberry, usa:
> `-p fuente:=teclado`.

---

## 7. Pruebas ANTES de la demo

```bash
# Sin mover el brazo: valida poses
python herramientas/verificar_poses.py --paso-max 1.6

# Cámara sin ROS
python herramientas/probar_camara.py 0

# Pinza con el driver arriba
python herramientas/probar_pinza.py
```

Publicador único (regla eliminatoria):

```bash
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt
ros2 topic info /orden_decidida -v    # debe salir UN solo suscriptor: orquestador_item2
```

---

## 8. Evidencias que se piden

- `intentos.csv` — una fila por acción ejecutada (con `error_mm` por FK en `agarrar`/`mover`).
  Tabla de los **10 intentos** requerida por el enunciado.
- `rechazos_orquestador.csv` — `no_permitida`, `objeto_desconocido`, `sin_deteccion`.
- `ros2 topic echo /objeto_detectado` — captura del `color` y `estable:true`.
- `evidencia/publicadores.txt` — verificación del publicador único.
- Video de la demo (pick-and-place) + bolsa de tópicos si la piden.

---

## 9. Problemas comunes

- **Broker rechaza goal por `paso`**: baja `-p paso_max_rad` del orquestador (más waypoints) o súbelo en el broker.
- **Todo se rechaza `no_permitida`**: revisa `motivo` en `rechazos_orquestador.csv` (LAYA/clasificador).
- **`sin_deteccion`**: mueve el cubo a cámara; sube `-p espera_deteccion_s:=3.0`; verifica `usb_cam`.
- **Gripper no cierra para el cubo**: calibra `-p gripper_abierto` / `gripper_cerrado` con `probar_pinza.py`.
- **No se ve `/orden_decidida`**: el `ROS_DOMAIN_ID` y `ROS_DISCOVERY_SERVER` deben ser idénticos en las 5 máquinas (43).
- **Dos orquestadores suscritos**: corre solo `orquestador_item2` (el `orquestador` de item3 no está registrado).

---

## 10. Checklist de entrega

- [ ] Cámara, driver, broker, intérprete, percepción, orquestador y clientes arriba.
- [ ] `agarrar`, `soltar` (con/sin color), `mover`, `detener` probados.
- [ ] `verificar_publicadores.py` pasa (1 publicador del broker).
- [ ] `intentos.csv` con 10 intentos y `rechazos_orquestador.csv`.
- [ ] Opcional: audio con `transcriptor_voz` desde una Raspberry.