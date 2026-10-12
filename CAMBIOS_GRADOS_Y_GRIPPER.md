# Cambios de grados y pinza — explicado sencillo

Esta carpeta trae la **versión definitiva** de los archivos que arreglan dos problemas de la
Pregunta 2 del parcial:

1. el **brazo no se movía** (o se movía "una nada"), y
2. la **pinza no se abría ni cerraba**.

Es una **fusión** de tu carpeta `src/` (que ya tenía el arreglo de grados) con la carpeta
`CLAUDE/` (que traía el manejo de la pinza y un rediseño más simple). Se quedó lo mejor de cada
una, sin duplicar cosas.

---

## Problema 1 — "el brazo no se mueve"

### Qué pasaba
El driver del kit (`ros2 run jetcobot_driver sync_plan_nx`, nodo `control_sync_plan`) hace algo
muy simple: **toma el número que llega por `/joint_states` y lo pasa tal cual a `send_angles()`
de pymycobot**. Y `send_angles()` espera **grados**.

El broker, en cambio, publicaba la pose en **radianes**. Entonces:

```
querías:  10.81°           el driver mandaba a los motores:  0.1887°
(10.81° = 0.1887 rad)                                           ↑ casi nada
```

Resultado: el brazo recibía un ángulo diminuto. **No hay error ni excepción**: por eso parece
que "no se mueve".

### Qué se cambió (dos líneas)
- En `broker.py`, dentro de `mover()` (el único lugar que publica `/joint_states`):
  ```python
  msg.position = [float(math.degrees(v)) for v in q]   # radianes -> grados
  ```
- En `orquestador_item2.py`, dentro de `_on_joint_states` (el orquestador solo *lee* ese tópico
  para medir el error):
  ```python
  self.q_actual = [float(math.radians(v)) for v in msg.position[:6]]   # grados -> radianes
  ```

### La regla mental (memorízala)
> **Por dentro** (FK, límites, `paso_max_rad`, `q_actual`, `rechazos.csv`, los goals `move_arm`)
> todo es **radianes**. **Solo `/joint_states`** —la frontera con el driver— sale en **grados**.

### ¿Por qué NO usamos el "factor de compensación" de `CLAUDE/`?
`CLAUDE/` hacía lo mismo pero con un parámetro configurable (`factor_compensacion_motor`,
por defecto `1.0`). Es **peor** como base porque:
- obliga a que el broker y el orquestador tengan **exactamente el mismo** valor (si se
  desincronizan, el error de FK queda mal);
- su valor por defecto (`1.0`) **vuelve a introducir el bug** sin darte cuenta.

`math.degrees()` no tiene esos riesgos y dice exactamente lo que hace. De `CLAUDE/` sí
adoptamos lo bueno: el aviso al arrancar y el manejo de la pinza (abajo).

---

## Problema 2 — "la pinza no hace nada"

### Qué pasaba
El orquestador intentaba abrir/cerrar la pinza con una **acción ROS** llamada
`gripper_command` (`control_msgs/action/GripperCommand`). Pero el driver del kit **no expone
esa acción**: solo escucha `/joint_states`. Entonces cada intento se quedaba **30 segundos**
esperando una acción que no existe, y fallaba.

Además había dos detalles:
- Los valores que usaba (`abierto=0.0`, `cerrado=0.04`) eran de otra convención (metros). El
  script que **sí probaste** (`item2/5.py`) usa la escala del kit **0..100**: abrir `100`,
  cerrar `15`.
- La pinza reusaba el timeout del brazo (`30 s`) en vez de tener el suyo.

### Qué se cambió
1. **`-p gripper_habilitada:=false`** (nuevo en el orquestador): simula la pinza y **no bloquea**
   la demo mientras se resuelve el hardware real. Cada paso de pinza se registra como "SIMULADO"
   y cuenta como éxito.
2. **`-p gripper_timeout_s`** (nuevo, por defecto `5.0`): un fallo de pinza ya no cuelga 30 s.
3. **Escala del kit**: el nodo nuevo `pinza_pymycobot.py` expone la misma acción
   `gripper_command`, pero por dentro llama a `set_gripper_value()` con la escala **0..100**.
   Se lanza el orquestador con `-p gripper_abierto:=100 -p gripper_cerrado:=15`.

> ⚠️ **Cuidado con el puerto serie.** El driver del brazo tiene abierto `/dev/ttyUSB0`. Un
> segundo `MyCobot(...)` sobre el mismo puerto puede fallar o competir. Si en la Jetson no se
> puede compartir, usa `gripper_habilitada:=false` para la demo y deja `pinza_pymycobot.py`
> para cuando el reparto del puerto esté claro (ver `docs/grados/PINZA_NO_SE_MUEVE.md` §4).

---

## Por qué los arreglos van justo ahí

La regla **eliminatoria** del reto dice: **exactamente un publicador de `/joint_states`**, y debe
ser el **worker del broker**. Por eso:
- La conversión a grados se hace **dentro del broker** (que ya es el único publicador). Un "nodo
  puente" entre el broker y el driver sería **un segundo publicador** → anulas la Pregunta 2.
- El nodo de la pinza **no toca `/joint_states`** (la regla aplica solo a ese tópico), así que
  es válido.
- El orquestador **solo lee** `/joint_states`; nunca publica ahí.

---

## Cómo saber que quedó bien

Con la cadena corriendo (driver + broker + orquestador):

```bash
ros2 topic echo /joint_states
```

Debe mostrar **decenas de grados** (por ejemplo `10.81, -25.57, 15.9, ...`), **no** valores
menores que 1 (`0.18, -0.44, ...`). Si siguen apareciendo valores < 1, el paquete instalado no
se reconstruyó: vuelve a compilar (`colcon build ...`) y `source install/setup.bash`.

Y para la regla del publicador único:

```bash
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt
```

Debe salir **exactamente 1** publicador llamado `arm_broker`.

---

## Resumen de archivos (qué reemplaza a qué)

| Archivo aquí | Va a | Qué contiene |
|---|---|---|
| `broker.py` | `src/arm_broker/arm_broker/broker.py` | grados en `mover()`, aviso de arranque, logs de depuración limpiados |
| `orquestador_item2.py` | `src/arm_broker/arm_broker/orquestador_item2.py` | lee grados→radianes, `gripper_habilitada`, `gripper_timeout_s`, 3 acciones con `cargando` |
| `poses.py` | `src/arm_broker/arm_broker/poses.py` | planes de las 3 acciones (`agarrar`/`soltar`/`mover`) |
| `gripper.py` | `src/arm_broker/arm_broker/gripper.py` | cliente de pinza con diagnóstico claro (de `CLAUDE/`) |
| `pinza_pymycobot.py` | `src/arm_broker/arm_broker/pinza_pymycobot.py` | nodo **nuevo** que sí implementa la acción de pinza (escala 100/15) |

Los pasos exactos para copiarlos, compilar y ejecutar están en **`COMO_APLICAR.md`**.
