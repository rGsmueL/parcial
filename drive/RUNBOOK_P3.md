# RUNBOOK P3 — voz (Google → decisión → brazo)

Cadena: audio/teclado → `GOOGLE_API_KEY` (Gemini) → texto → `/interpretar_orden` (P1) →
`/orden_decidida` → `orquestador_item2` → broker → brazo. Si Gemini falla (sin clave/internet),
**cae a modo teclado** automáticamente.

## Entorno (en CADA terminal de la Jetson)
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER=<IP_JETSON>:11811
ros2 daemon stop; ros2 daemon start
```

## Compilar (una vez; ya hecho en P1 no hace falta repetir)
```bash
cd ~/rb2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

---

## Terminales

### T0 — Driver (opcional, solo si quieres que el brazo se mueva físicamente)
```bash
ros2 run jetcobot_driver sync_plan_nx
```

### T1 — PC Windows: servidor LAYA
```powershell
# en C:\laya con el venv activado (setup completo: PASOS_ITEM_1.md §3)
$env:LAYA_HOST="0.0.0.0"; $env:LAYA_PORT="8000"; $env:LAYA_DEVICE="cuda"; $env:LAYA_MODELS="multilingual"; $env:LAYA_PRELOAD="1"
laya-serve
```

### T2 — Jetson: intérprete P1
```bash
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000
```

### T3 — Jetson: broker
```bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1
```

### T4 — Jetson: orquestador (sin cámara, sin pinza → solo lo necesario)
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 \
  -p usar_camara:=false -p gripper_habilitada:=false
```

### T5 — Jetson: voz → texto (desde `~/rb2_ws`)
```bash
cd ~/rb2_ws
export GOOGLE_API_KEY="TU_CLAVE_DE_GOOGLE_AI_STUDIO"
```

**Vía audio** (`.wav` generado con `arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav`):
```bash
ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p google_model:=gemini-2.5-flash -p timeout_transcripcion_s:=5.0 -p n_ordenes:=1
```

**Vía teclado** (modo texto; entregable obligatorio del ítem 3):
```bash
ros2 run arm_broker transcriptor_voz --ros-args -p fuente:=teclado -p n_ordenes:=0
```

---

## Verificación
```bash
# transcripción SIN ROS (rápido, en ~/rb2_ws):
python3 herramientas/probar_transcripcion.py orden_01.wav gemini-2.5-flash
# → "Transcripción (... ms): 'agarra el cubo rojo'"

ros2 topic echo /orden_decidida --once
cat transcripciones.csv     # t_unix,ruta_audio,texto,metodo,tiempos...
```

## Demo SIN internet (obligatoria)
Corta solo la WAN, dejando la LAN con la PC de LAYA:
```bash
sudo iptables -A OUTPUT -d 0.0.0.0/0 -j DROP
sudo iptables -I OUTPUT -d <IP_PC_LAYA> -j ACCEPT
ping -c 2 8.8.8.8                 # debe FALLAR
curl -s http://<IP_PC_LAYA>:8000/health   # debe RESPONDER
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_01.wav
# Gemini falla → aviso + input() por teclado → decisión (LAYA local) → brazo
sudo iptables -D OUTPUT -d 0.0.0.0/0 -j DROP   # restaurar
```

> Errores comunes: sin `GOOGLE_API_KEY` → cae a teclado (no es fatal); modelo `404` → usa el
> que liste `curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"`;
> CSV se escribe en el CWD → lanza desde `~/rb2_ws`.