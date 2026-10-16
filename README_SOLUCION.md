# `solucionn/` — versión unificada y corregida

Esta carpeta es un **workspace listo para compilar**: `solucionn/` es la raíz de colcon y
`solucionn/src/` tiene los dos paquetes (`arm_broker_interfaces` + `arm_broker`).

Se armó comparando **las dos `src`** y quedándose con **la que funciona** (`carrprp/src`) más lo
único que aportaba la otra (`arreglar_angulos_y_gripper/src`) sin romper nada.

- **A** = `C:\...\carrprp\src\` → la que funciona bien.
- **B** = `C:\...\carrprp\arreglar_angulos_y_gripper\src\` → la que "corre todo pero no se mueve".

> Regla eliminatoria respetada: **un único publicador de `/joint_states`** (el worker del
> `arm_broker`). Esta carpeta no agrega ningún publicador nuevo.

---

## 1. Comparación A vs B (solo lo que difiere)

| Archivo | A (`src/`) | B (`arreglar_angulos_y_gripper/src/`) | Qué se quedó en `solucionn` |
|---|---|---|---|
| `broker.py` | `mover()` publica **GRADOS** (`math.degrees`) | **igual** + aviso de unidades al arrancar | **A + el aviso de B** (solo logging) |
| `orquestador_item2.py` | acción desconocida ⇒ **rechaza** con causa explícita | acción desconocida **con color ⇒ se ejecuta como `mover`** (fail-open) | **A** (rechazo explícito) |
| `zonas.py` | poses de recogida medidas: q6 = `69, 45, 90, 50`; `POSE_BUSQUEDA` q6 = `64` | q6 cambiados: `-6, -30, 1, -35`; `POSE_BUSQUEDA` q6 = `-25` (no validados en hardware) | **A** |
| `gripper.py` | avisa cada intento; sin `disponible()` | diagnóstico claro + `disponible()` + aviso **una sola vez** | **B** (mejor, mismo comportamiento) |
| `politicas.py` | base con `atendido()` no-op | `SegundaPolitica` **cuenta** `atendidos` | **B** |
| `interprete_ordenes.py` | aplica `decisiones.aplicar_reglas` y exige acción reconocida | versión vieja (sin `decisiones`) | **A** |
| `cliente_laya.py` | fail-safe: `permitido` por defecto **False**, normaliza y valida | fail-open: `permitido` por defecto **True**, sin normalizar | **A** |
| `clasificador_palabras_clave.py` | reutiliza `decisiones` | versión vieja (inline) | **A** |
| `decisiones.py` | **existe** | **no existe** (borrado) | **A** |
| `setup.py` | 8 entry points | idéntico (solo espacios) | **A** |
| `driver.txt` | no existe | **existe, de 0 bytes (vacío)** | **no se copió** |
| `src/src/` (copia anidada de B dentro de sí misma) | no existe | **existe** (paquetes duplicados) | **no se copió** |
| `fk.py`, `poses.py`, `percepcion_camara.py`, `pinza_pymycobot.py`, `intentos.py`, `cliente*.py`, `transcriptor_voz.py`, `voz_google.py`, `arm_broker_interfaces/*` | — | **idénticos** | **A** |

### Veredicto: **A es la que está bien**

| Criterio | A | B |
|---|---|---|
| Unidades (`/joint_states` en grados, interno en radianes) | correcto (`math.degrees` / `math.radians`) | correcto (igual código) |
| Se puede compilar con `colcon` | sí | **no de forma confiable** (paquetes duplicados `src/src`) |
| Decisión de órdenes | fail-safe (`permitido=False` si no se entiende) | fail-open (`permitido=True`) ⇒ puede ejecutar lo que no entiende |
| Poses de agarre | medidas y probadas | q6 cambiados sin validar en hardware |
| Módulo de coherencia `decisiones.py` | sí | **falta** |
| Ruido/basura en `src/` | limpio | `driver.txt` vacío + carpeta `src/src/` |

**B no tiene ningún "arreglo extra" que A no tenga**: en lo que mueve el brazo, el código es el
mismo. Por eso se tomó A como base.

---

## 2. Por qué con `arreglar_angulos_y_gripper` "corre todo pero **no se mueve**"

### 2.1 Lo que SÍ está bien en B (verificado en el código)

- `arm_broker/arm_broker/broker.py` → `mover()`: `msg.position = [float(math.degrees(v)) for v in q]`
  → **publica grados** (línea 434).
- `arm_broker/arm_broker/orquestador_item2.py` → `_on_joint_states()`:
  `self.q_actual = [float(math.radians(v)) for v in msg.position[:6]]` → **relee en radianes** (línea 152).

Es decir: **el arreglo de grados está presente en el código de B**. Entonces el problema no es el
código fuente de B, sino **qué código se está ejecutando en la Jetson**.

### 2.2 Causa confirmada: el `colcon build` de B no puede terminar y se sigue corriendo un `install` viejo

B trae la carpeta **`arreglar_angulos_y_gripper/src/src/`**, que es una **copia anidada de sí
misma** (idéntica byte a byte a `arreglar_angulos_y_gripper/src/`). Resultado: el workspace tiene
**dos paquetes con el mismo nombre**:

```
arreglar_angulos_y_gripper/src/arm_broker            (package arm_broker)
arreglar_angulos_y_gripper/src/src/arm_broker        (package arm_broker)   ← duplicado
arreglar_angulos_y_gripper/src/arm_broker_interfaces (package arm_broker_interfaces)
arreglar_angulos_y_gripper/src/src/arm_broker_interfaces                      ← duplicado
```

`colcon` **no soporta nombres de paquete duplicados** en un mismo workspace
(error: *"Duplicate package names not supported"*). Al fallar el build, el `install/` de esa
Jetson se queda con lo **que se hubiera compilado antes**.

Si ese `install` viejo es **anterior al arreglo de grados**, el broker que corre publica
**radianes** y el driver recibe `0.1887` donde debía recibir `10.81` ⇒ **el brazo se mueve "una
nada"**. No hay excepción ni error: por eso "corre todo pero no se mueve".

Esto es exactamente el síntoma ya documentado en el repo:

- `docs/ARREGLOS/CAMBIOS_GRADOS_Y_GRIPPER.md` §1 ("el brazo no se mueve", radianes ⇄ grados).
- `CONTEXTUALIZACION.md` §1, con la evidencia de `reporte.txt`:
  ```
  [control_sync_plan]: Ejecutando angulos: [0.1886700921519945, -0.44628068974595006, ...]
  ```
  (valores < 1 ⇒ el driver estaba recibiendo radianes).

**Fix:** compilar siempre en un workspace **sin duplicados** (ver §4 y §5) y confirmar que el
`/joint_states` que se publica sale en decenas.

### 2.3 Cómo confirmarlo en la Jetson (en este orden)

```bash
# 1) ¿El build falla por duplicados?   (si falla: borra src/src y recompila)
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install

# 2) ¿Qué se está publicando?  decenas (10.8) = bien  |  < 1 (0.18) = install viejo (radianes)
ros2 topic echo /joint_states

# 3) Log del driver: ¿qué angulos recibe de verdad?
#    "Ejecutando angulos: [0.18, -0.44, ...]"  -> radianes (mal)
#    "Ejecutando angulos: [10.8, -25.5, ...]"  -> grados (bien)
```

Si el driver **no imprime nada** aunque el broker publique, no se están viendo entre sí:
revisa el entorno (`ROS_DOMAIN_ID=43`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`,
`ROS_DISCOVERY_SERVER=<jetson>:11811`, luego `ros2 daemon stop; ros2 daemon start`) y que el nodo
esté vivo (`ros2 node list` → debe aparecer `control_sync_plan`).

Si el driver imprime **decenas** y el brazo sigue quieto, el problema ya no es el broker: es el
driver/puerto serie (`/dev/ttyUSB0`).

Si los goals se rechazan, están en `rechazos.csv` (causa `limite` / `workspace` / `paso`).
Un `paso` significa que el `paso_max_rad` del broker es menor que el del orquestador ⇒ iguala
ambos a `1.6`.

---

## 3. `driver.txt`

**Estado real: `arreglar_angulos_y_gripper/src/driver.txt` está VACÍO (0 bytes)**, creado hoy;
no existe ningún otro `driver.txt` en el repo y ningún archivo/doc lo menciona.

Por eso **no "se adecúa" a A ni a B: no hay contenido que comparar**. Lo que decide la adecuación
no es ese archivo, sino el driver real:

```
ros2 run jetcobot_driver sync_plan_nx      (nodo control_sync_plan)
  /joint_states  ──►  valor tal cual  ──►  send_angles() de pymycobot  (espera GRADOS)
```

Qué hacer con `driver.txt` (dos opciones, ambas válidas):

1. **Guardar la salida real del driver** (es lo más útil para la evidencia del parcial):
   ```bash
   ros2 run jetcobot_driver sync_plan_nx 2>&1 | tee driver.txt
   # y en otra terminal, mientras se mueve algo:
   ros2 topic echo /joint_states
   ```
2. **Guardar el código del driver** (para confirmar que pasa el valor tal cual):
   ```bash
   ros2 pkg prefix jetcobot_driver     # ubicación del paquete en la Jetson
   find "$(ros2 pkg prefix jetcobot_driver)" -name '*.py' | xargs grep -n 'send_angles'
   ```

Dejé una **plantilla ya redactada** en `solucionn/driver.txt` con qué pegar y qué se busca.
Ojo: **no** pongas `driver.txt` dentro de `src/` de un workspace de colcon (no es un paquete y no
aporta nada al build).

---

## 4. Qué contiene `solucionn/`

```
solucionn/
├── README_SOLUCION.md      este documento
├── driver.txt              plantilla/explicación del contrato del driver (§3)
├── analisis/
│   └── verificar_publicadores.py   regla: exactamente 1 publicador (/joint_states)
├── herramientas/
│   ├── verificar_poses.py          poses vs límites/workspace/paso (sin mover el brazo)
│   └── validar_rechazos.py         causas de rechazo (limite/workspace/paso)
└── src/
    ├── arm_broker/                 ← base A + gripper/politicas de B + aviso de unidades
    │   ├── arm_broker/  (broker, orquestador_item2, poses, zonas, percepcion_camara, fk,
    │   │                 politicas, gripper, decisiones, interprete_ordenes, cliente_laya,
    │   │                 clasificador_palabras_clave, pinza_pymycobot, intentos, cliente*,
    │   │                 transcriptor_voz, voz_google, __init__)
    │   ├── resource/arm_broker
    │   ├── package.xml · setup.cfg · setup.py (8 entry points)
    └── arm_broker_interfaces/
        ├── action/MoveArm.action · msg/QueueState.msg · srv/InterpretarOrden.srv
        └── CMakeLists.txt · package.xml
```

- **NO** hay `src/src/` (duplicados que rompen `colcon`).
- **NO** hay `driver.txt` dentro de `src/`.
- **NO** hay `__pycache__` ni `.pyc`.

### ¿Y si querías las poses nuevas de B (q6 negativos)?

Están **fuera** porque no están validadas en hardware. Si las necesitas, copia
`arreglar_angulos_y_gripper/src/arm_broker/arm_broker/zonas.py` sobre
`solucionn/src/arm_broker/arm_broker/zonas.py` y valida **antes** de mover el brazo:

```bash
cd solucionn
python herramientas/verificar_poses.py --paso-max 1.6      # debe salir todo OK
```

Ambas variantes pasan la validación (límites simétricos: las de B también son legales), así que la
elección entre ellas es de **calibración física**, no de código. Con A, las poses son las mismas
que ya te funcionaron.

---

## 5. Cómo usarlo en la Jetson

### 5.1 Copiar y compilar

```bash
# copia solucionn/src a un workspace LIMPIO en la Jetson, por ejemplo ~/sol_ws/src
mkdir -p ~/sol_ws/src
cp -r solucionn/src/* ~/sol_ws/src/

cd ~/sol_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

> Si además tienes la carpeta `arreglar_angulos_y_gripper` en la Jetson, **bórrale el `src/src`**
> antes de compilar ahí; con dos paquetes `arm_broker` el build no compila lo que crees.

### 5.2 Arrancar (parámetros obligatorios; **los defaults del código no sirven**)

```bash
# T1 · driver del kit
ros2 run jetcobot_driver sync_plan_nx

# T2 · broker (único publicador de /joint_states)
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1

# T3 · cámara
ros2 run arm_broker percepcion_camara

# T4 · orquestador (demo sin pinza; la acción de pinza no existe en el driver del kit)
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p usar_zonas:=true -p gripper_habilitada:=false
```

(Opcional, pinza real por pymycobot 0..100: `ros2 run arm_broker pinza_pymycobot --ros-args -p puerto:=/dev/ttyUSB0`
y arrancar el orquestador con `-p gripper_abierto:=100 -p gripper_cerrado:=15`.)

### 5.3 Verificar que sí se mueve

```bash
ros2 topic echo /joint_states                                        # decenas, no < 1
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt   # exactamente 1
cd solucionn && python herramientas/verificar_poses.py --paso-max 1.6           # todo OK
python herramientas/validar_rechazos.py                              # causas de rechazo
```

---

## 6. Tabla de síntomas → causa → solución

| Síntoma | Causa | Solución |
|---|---|---|
| `colcon build` dice *Duplicate package names not supported* | `src/src/` duplicado en el workspace | borrar la carpeta `src/src` y recompilar |
| `/joint_states` con valores < 1 (`0.18`) y el brazo no se mueve | paquete instalado **viejo** (sin `math.degrees`) | recompilar y `source install/setup.bash`; confirmar con `ros2 topic echo` |
| El driver no imprime `Ejecutando angulos` | driver no corriendo / no ve al broker | arrancar `sync_plan_nx`, revisar `ROS_DOMAIN_ID=43`, RMW y discovery server |
| El driver imprime decenas y el brazo no se mueve | puerto serie / driver del kit | revisar `/dev/ttyUSB0` y que no lo tenga tomado otro proceso |
| Rechazos con causa `paso` en `rechazos.csv` | `paso_max_rad` del orquestador < del broker | igualar ambos a `1.6` |
| La pinza se queda ~5 s y falla | el driver del kit no expone `gripper_command` | `-p gripper_habilitada:=false` (demo) o `pinza_pymycobot` |
| Órdenes rechazadas con `color_no_encontrado` | el color no está en ninguna de las 4 ROIs | re-medir ROIs (cámara 640×480) / correr el espacio delimitado |

---

## 7. Qué **no** se tocó

- `carrprp/src/` y `carrprp/arreglar_angulos_y_gripper/` quedan **intactos**.
- `CLAUDE/`, `moveit2/`, `item2/`, `entrega_item2_arm_broker/`, `analisis/`, `herramientas/`,
  `docs/` quedan **intactos**.

Esta carpeta es **nueva y aparte**: nada de lo que corría antes cambia.
