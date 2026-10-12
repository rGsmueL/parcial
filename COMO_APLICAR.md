# Cómo aplicar `arreglar_angulos_y_gripper`

Estos archivos son **copias-fuente** (como `item2/` o `CLAUDE/`): no se ejecutan aquí. Hay que
copiarlos al paquete `src/arm_broker/arm_broker/` de la Jetson y recompilar.

## 1. Copiar los archivos al paquete

Desde la **raíz del repo** (en la Jetson, con bash):

```bash
DEST=src/arm_broker/arm_broker
cp arreglar_angulos_y_gripper/broker.py             $DEST/
cp arreglar_angulos_y_gripper/orquestador_item2.py  $DEST/
cp arreglar_angulos_y_gripper/poses.py              $DEST/
cp arreglar_angulos_y_gripper/gripper.py            $DEST/
cp arreglar_angulos_y_gripper/pinza_pymycobot.py    $DEST/
```

## 2. Registrar el nodo nuevo de la pinza en `setup.py`

`pinza_pymycobot.py` es un nodo nuevo: hay que darle entry point. Abre
`src/arm_broker/setup.py` y añade una línea en `console_scripts`:

```python
'pinza_pymycobot = arm_broker.pinza_pymycobot:main',
```

(El bloque queda con `broker`, `cliente`, `interprete_ordenes`, `transcriptor_voz`,
`percepcion_camara`, `orquestador_item2`, `cliente_texto` y ahora `pinza_pymycobot`.)

## 3. Compilar

```bash
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

## 4. Arrancar (Jetson)

**Driver del brazo:**
```bash
ros2 run jetcobot_driver sync_plan_nx
```

**Broker** (ojo: los defaults del código no sirven para las corridas):
```bash
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1
```

**Pinza real** (si el puerto serie se puede compartir con el driver):
```bash
ros2 run arm_broker pinza_pymycobot --ros-args -p puerto:=/dev/ttyUSB0
```

**Orquestador — con pinza real** (escala del kit 100/15):
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p gripper_abierto:=100 -p gripper_cerrado:=15 -p gripper_timeout_s:=5.0
```

**Orquestador — demo sin pinza** (recomendado mientras el puerto no esté resuelto):
```bash
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p gripper_habilitada:=false
```

## 5. Verificar

```bash
# 1) /joint_states debe salir en GRADOS (decenas, no valores < 1)
ros2 topic echo /joint_states

# 2) Regla eliminatoria: exactamente 1 publicador, arm_broker
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt

# 3) Las poses siguen pasando límites/workspace
python herramientas/verificar_poses.py --paso-max 1.6
```

## 6. Si algo no cuadra

| Síntoma | Causa probable | Solución |
|---|---|---|
| El brazo se mueve "una nada" | el paquete instalado no tiene el arreglo de grados | recompila y `source install/setup.bash`; revisa que `/joint_states` muestre decenas |
| La pinza se queda 5 s y falla | no hay action server de pinza | corre `pinza_pymycobot`, o usa `gripper_habilitada:=false` |
| `MyCobot` falla al abrir el puerto | el driver ya tiene `/dev/ttyUSB0` | resuelve el reparto del puerto o usa la demo con pinza simulada |
| Rechazos con causa `paso` | `paso_max_rad` del orquestador < del broker | iguala ambos a `1.6` |
