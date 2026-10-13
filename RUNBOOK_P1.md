# RUNBOOK P1 — decisión (LAYA → `/interpretar_orden`)

Cadena: frase → LAYA (PC) → `interprete_ordenes` → respuesta JSON → `/orden_decidida`.
Solo lo necesario para la demo.

## Entorno (en CADA terminal de la Jetson)
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

### T1 — PC Windows: servidor LAYA
```powershell
# en C:\laya con el venv activado (setup completo: PASOS_ITEM_1.md §3)
$env:LAYA_HOST="0.0.0.0"; $env:LAYA_PORT="8000"; $env:LAYA_DEVICE="cuda"; $env:LAYA_MODELS="multilingual"; $env:LAYA_PRELOAD="1"
laya-serve
```

### T2 — Jetson: comprobar LAYA desde la red (sin ROS)
```bash
python3 herramientas/probar_laya.py http://<IP_PC>:8000 "agarra el cubo rojo"
# debe imprimir la respuesta cruda de LAYA
```

### T3 — Jetson: nodo intérprete (servicio `/interpretar_orden`)
```bash
ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP_PC>:8000 -p timeout_laya_s:=2.0
```

### T4 — Jetson: cliente (escribe la frase)
```bash
ros2 run arm_broker cliente_texto --ros-args \
  -r __node:=cliente_p1 -p client_id:=p1 -p n_ordenes:=0
```
Escribe la orden en español y Enter: `agarra el cubo rojo`, `mueve el cubo azul`, `detener`.

---

## Verificación
```bash
ros2 service list | grep interpretar
ros2 topic echo /orden_decidida --once
python3 herramientas/medir_item1.py      # evidencia latencia/exactitud (P1)
```