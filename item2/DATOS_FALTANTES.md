# DATOS FALTANTES — lo que hay que confirmar antes de correr el Ítem 2

> Todo lo que **no pude deducir del repositorio** (porque vive en el driver/hardware del kit) y
> **cómo conseguirlo** en la Jetson. Cada punto trae el comando y qué anotar. Actualiza esta
> tabla cuando tengas los valores.

---

## 1. Pinza — ¿cómo se comanda? (el dato más importante)

El código usa por defecto la acción estándar `control_msgs/action/GripperCommand` llamada
`gripper_command`. Hay que **confirmar el nombre real** y las posiciones.

```bash
# a) Ver todas las acciones disponibles (mira las que suenen a pinza/gripper)
ros2 action list -t

# b) Ver los servicios y tópicos por si el kit usa otro mecanismo
ros2 service list | grep -i grip
ros2 topic list | grep -i grip

# c) Si aparece como acción, inspecciona su tipo
ros2 action info /gripper_command
```

**Anota:**
- Nombre de la acción/servicio: `__________` (default `gripper_command`)
- Tipo: `control_msgs/action/GripperCommand` u otro: `__________`
- Posición **abierto** y **cerrado** (calíbralas con `python herramientas/probar_pinza.py`):
  `abierto=______  cerrado=______  esfuerzo=______`

> Si el kit **no** expone una acción de pinza y solo se controla con `pymycobot`, dímelo: hay que
> añadir un nodo/servicio de pinza y confirmar que **no** rompe la regla del publicador único.

---

## 2. Cámara — tópico, dispositivo y formato

```bash
# a) Dispositivos de video disponibles
ls -l /dev/video*
v4l2-ctl --list-devices            # si está instalado

# b) Comprueba que usb_cam publica y en qué tópico
ros2 topic list | grep -i image
ros2 topic info /camera/image_raw -v
ros2 topic hz /camera/image_raw
```

**Anota:**
- Dispositivo que funciona: `/dev/video____`
- Tópico de imagen: `__________` (default `/camera/image_raw`)
- Formato/encoding (`rgb8`, `bgr8`, `yuv422`…): `__________`
- ¿La cámara ve los 4 colores con buena luz? `sí / no` (ajusta `COLORES_HSV` en
  `percepcion_camara.py` y `probar_camara.py` si hace falta)

---

## 3. Convención de las poses (grados del kit vs DH del `fk.py`)

Las poses vienen del script del kit en **grados**. El broker usa la **DH de `fk.py`** en radianes.
Hay que confirmar que coinciden (signos y offsets). **Sin** driver corriendo, con el puerto serie
libre:

```bash
python3 herramientas/verificar_poses.py --paso-max 1.6   # valida límites/workspace/step
python3 herramientas/verificar_fk.py                     # compara fk(q) vs get_coords() del brazo
```

**Anota:**
- Error máximo FK vs brazo real (criterio ≤ 10 mm): `______ mm`
- ¿Alguna pose necesitó corregir signo/offset? `sí / no` → detállalo en `poses.py`.

> Nota conocida: `fk.py` tiene `d5=75.55`, `d6=50`; `mi_info.txt` del kit declara `d5=75.05`,
> `d6=60`. Eso se corrige **físicamente** verificando, no adivinando.

---

## 4. Enlace driver ↔ broker

```bash
ros2 node list
ros2 node info /sync_plan_nx          # ¿se suscribe a /joint_states?
ros2 topic info /joint_states -v
```

**Anota:**
- ¿`sync_plan_nx` se mueve leyendo `/joint_states`? `sí / no`
- ¿Cuál es el **único** publicador de `/joint_states` durante la demo? `__________`

---

## 5. Entorno ROS y dependencias

```bash
echo $ROS_DOMAIN_ID                              # anota el del equipo
ros2 pkg prefix control_msgs && echo control_msgs OK
ros2 pkg prefix cv_bridge && echo cv_bridge OK
ros2 pkg prefix usb_cam   && echo usb_cam OK
ros2 pkg prefix moveit  2>/dev/null && echo "MoveIt2 instalado" || echo "MoveIt2 NO instalado"
```

**Anota:**
- `ROS_DOMAIN_ID` del equipo: `______`
- `control_msgs`: `sí/no` · `cv_bridge`: `sí/no` · `usb_cam`: `sí/no`
- MoveIt2 instalado: `sí/no` (si `sí`, dime y activamos la ruta de §10 del Parte 2)
- IP del Discovery Server (si se usa): `______`

---

## 6. Tablero: posiciones y zonas

Del script del kit ya tengo las poses, pero confirma la lógica de la mesa:

| Color | ¿Está sobre la mesa? | Zona de destino (`DESTINOS`) | ¿Coincide con la realidad? |
|---|---|---|---|
| rojo | sí/no | `[80.15,…]` | sí/no |
| verde | sí/no | `[96.15,…]` | sí/no |
| azul | sí/no | `[113.29,…]` | sí/no |
| amarillo | sí/no | `[65.12,…]` | sí/no |

**Anota** cualquier pose que cambie y si el kit usa un **cubo por color** o forma+color.
El enunciado dice "cuatro objetos de colores distintos en posiciones conocidas": si las posiciones
de la mesa difieren de las del script, dime las nuevas para ajustar `poses.py`.

---

## 7. Cómo me pasas los datos

Responde este archivo (o pégame los valores) así:

```
1. Pinza: acción=______ tipo=______ abierto=______ cerrado=______
2. Cámara: dev=______ tópico=______ encoding=______
3. Poses: error_fk=______ mm  correcciones=______
4. Driver: lee /joint_states=______ publicador único=______
5. ROS_DOMAIN_ID=______  deps: control_msgs=___ cv_bridge=___ usb_cam=___ moveit=___
6. Tablero: (tabla del punto 6)
```

Con eso ajusto `poses.py`, `gripper.__init__` y las guías al hardware real.
