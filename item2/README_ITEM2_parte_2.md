# ITEM 2 — Guía paso a paso: demo, 10 intentos y evidencia (Parte 2)

> Continúa de `README_ITEM2.md` (Parte 1). Aquí va la **demostración**, la **tabla de los 10
> intentos** con el error por FK, el **bag**, el **video de 3 min** y las respuestas al informe.

---

## 7. La demostración: 4 integrantes simultáneos

Con toda la cadena arriba (§6 de la Parte 1), cada integrante escribe órdenes al mismo tiempo
en su `cliente_texto`. Sobre la mesa pones los 4 cubos; cada orden válida entra a la **cola de
prioridad** del broker con la prioridad que dio el modelo.

**Qué debe verse y demostrarse:**
1. **Prioridad del modelo**: la prioridad del goal sale de la decisión (`priority = prioridad*85`),
   no la escribe el cliente. (Se ve en `/arm/queue_state`.)
2. **Publicador único**: `verificar_publicadores.py` = exactamente 1 (`arm_broker`).
3. **Rechazo de orden no permitida ANTES de encolar**: dicta/teclea una orden que LAYA o el
   clasificador marque `permitido=False` (p. ej. `cierra la puerta con el destornillador`).
   Debe aparecer una fila en `rechazos_orquestador.csv` con causa `no_permitida` **sin** que el
   broker la haya encolado.
4. **Objeto que no está sobre la mesa**: teclea un color/objeto que no pusiste → la cámara no lo
   confirma → fila con causa `sin_deteccion` y el brazo **no se mueve**.

Comprueba los rechazos:
```bash
cat rechazos_orquestador.csv
```
Formato: `t_unix, client_id, priority, causa, motivo, frase`.

### Grabar la evidencia de la demo
```bash
# Antes de grabar: publicador único
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt

# Bag de la demo (cola + poses del brazo)
ros2 bag record -o demo_p2 /arm/queue_state /joint_states

# En otra terminal, la cola en vivo (para el video)
ros2 topic echo /arm/queue_state
```
Graba **video de 3 minutos** donde se vean a la vez: la cola (`/arm/queue_state`), el brazo y
las órdenes. Cuatro integrantes enviando en paralelo, con al menos **una no permitida**.

---

## 8. Los 10 intentos de agarre

Un **intento es exitoso si el objeto correcto queda en la zona correcta**. Para cada uno se
reporta el **error entre la posición solicitada y la alcanzada**, con la FK del RB-2.

### 8.1 Cómo corre el orquestador un intento
Por cada orden válida, `orquestador_item2` ejecuta la secuencia (pinza abrir → busqueda →
recogida → pinza cerrar → busqueda → reparto → destino[color] → pinza abrir → home). Al final
escribe **una fila** en `intentos.csv`:

| intento | frase | objeto | color | zona | exito | q_solicitada | q_alcanzada | error_mm |
|---|---|---|---|---|---|---|---|---|

- `q_solicitada` = pose de recogida pedida (rad).
- `q_alcanzada` = última pose leída de `/joint_states` justo tras el movimiento de recogida.
- `error_mm = ‖fk(q_solicitada) − fk(q_alcanzada)‖` (función `intentos.error_mm`, usa `arm_broker.fk`).

### 8.2 Procedimiento para 10 intentos
1. Asegúrate de que `intentos.csv` empieza con solo la cabecera (el contador de intentos es del
   nodo; si relanzas el orquestador, borra el archivo o tenlo en cuenta).
2. Envía 10 órdenes de agarre (mezcla de colores y prioridades). Al menos una **no permitida**
   (cuenta como intento rechazado, no exitoso) y una de objeto inexistente.
3. Al terminar, resume la tasa de éxito:
```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, 'src/arm_broker')
from arm_broker import intentos
print(intentos.tasa_exito('intentos.csv'))
EOF
```
   (Devuelve `(total, exitos, tasa)`.)

### 8.3 Tabla del informe (llénala desde `intentos.csv`)
| Intento | Orden | Objeto/zona | ¿Éxito? | error_mm |
|---|---|---|---|---|
| 1 | agarra el cubo rojo | rojo/zona_rojo | sí | … |
| … | | | | |
| **Tasa de éxito** | | | **x/10** | |

> Verificación de la "zona correcta": puesto que el destino se elige **por color**
> (`DESTINOS[color]`), la zona es correcta por construcción; si quieres, verifica visualmente en
> el video que el cubo queda en su zona. Déjalo escrito en el informe.

---

## 9. Métricas de las políticas (evidencia del diseño del RB-2)

Si quieres además comparar FIFO vs prioridad (el enunciado del RB-2 lo pide y suma):

```bash
# Corrida FIFO
ros2 run arm_broker broker --ros-args -p politica:=fifo -p paso_max_rad:=1.6 &
ros2 bag record -o fifo /arm/queue_state /joint_states     # + clientes enviando
# Corrida prioridad
ros2 run arm_broker broker --ros-args -p politica:=prioridad -p tau_envejecimiento_s:=12.0 &
ros2 bag record -o prioridad /arm/queue_state /joint_states

# Exportar y graficar (sintaxis real, ver TERMINALES.md)
python3 analisis/exportar_csv.py fifo/ --salida fifo/
python3 analisis/exportar_csv.py prioridad/ --salida prioridad/
python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv \
  --salida comparacion_politicas.png
```

Recuerda la regla del examen: **anota la predicción ANTES de medir** (`prediccion.md`).

---

## 10. MoveIt2: cómo encaja (enfoque mixto)

En este entregable el movimiento va por el **broker** (interpolación articular) y la geometría
usa **poses fijas = IK precalculada** (las posiciones de la mesa son conocidas). Eso cumple:
`decisión → cola → cámara (color) → pose → brazo`, y respeta el publicador único.

**Cómo se integraría MoveIt2 formalmente (para el informe, y sin romper la regla):**
1. MoveIt2 se usa **solo para planificar** la trayectoria a la pose objetivo (devuelve una lista
   de waypoints articulares), **no** para publicar al brazo.
2. Esos waypoints se envían como **secuencia de goals `move_arm`** al broker (el broker sigue
   siendo el único que publica `/joint_states`). El orquestador ya hace algo equivalente con
   `poses.escalonar`; bastaría sustituir esa función por la salida del planificador.
3. Así se conserva la exclusión mutua del broker y se aprovecha la planificación de MoveIt2.

Déjalo así en el informe: *"usamos IK precalculada por posiciones conocidas; la integración con
MoveIt2 sustituiría el troceado por la trayectoria planificada, manteniendo el broker como
publicador único"*.

---

## 11. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `el broker RECHAZÓ el goal` con causa `paso` | salto mayor que `paso_max_rad` | baja `-p paso_max_rad` del orquestador (más waypoints) o súbelo en el broker |
| `sin_deteccion` en todas las órdenes | cámara/tópico/HSV | prueba `probar_camara.py` y `ros2 topic echo /objeto_detectado`; ajusta luces/HSV |
| La pinza no responde | nombre de acción o deps | `python herramientas/probar_pinza.py`; verifica `control_msgs`; mira `ros2 action list` |
| `la acción de la pinza no aparece` | driver no expone gripper | confirma el nombre con `ros2 action list \| grep -i grip` y pásalo en `-p gripper_action:=...` |
| Todo se rechaza `no_permitida` | LAYA/clasificador marca inseguro | revisa el `motivo` en `rechazos_orquestador.csv` |
| `reverse`/signos raros en el brazo | convención de grados ≠ DH | verifica con `herramientas/verificar_poses.py` y ajusta signos en `poses.py` |
| Segundos publicadores en `/joint_states` | el script de pymycobot sigue corriendo | **apágalo**: solo el broker puede publicar |

---

## 12. Entregables y checklist de la Pregunta 2

| Entregable | Fuente |
|---|---|
| Bag de la demostración | `demo_p2/` (`/arm/queue_state` + `/joint_states`) |
| Tabla de 10 intentos (resultado + error) | `intentos.csv` |
| Video de 3 min (cola + brazo, 4 integrantes) | grabación de pantalla |
| Publicador único | `evidencia/publicadores.txt` |
| Rechazo con causa | `rechazos_orquestador.csv` |
| Predicción previa | `prediccion.md` (escrito antes de medir) |
| (Opcional RB-2) comparación de políticas | `comparacion_politicas.png` |

- [ ] `usb_cam` publica `/camera/image_raw` y `percepcion_camara` detecta colores.
- [ ] Pinza calibrada con `probar_pinza.py` (abierto/cerrado/esfuerzo).
- [ ] `verificar_poses.py` = todas las poses OK.
- [ ] `package.xml` con `std_msgs`, `control_msgs`, `cv_bridge`; `colcon build` OK.
- [ ] Entry points `percepcion_camara`, `orquestador_item2`, `cliente_texto`; un solo orquestador.
- [ ] `verificar_publicadores.py` = 1 publicador `arm_broker`.
- [ ] 4 clientes en paralelo + rechazo `no_permitida` + objeto inexistente (`sin_deteccion`).
- [ ] 10 intentos en `intentos.csv` con `error_mm` y tasa de éxito.
- [ ] Bag + video de 3 min.
- [ ] Sección de MoveIt2 (§10) redactada en el informe.
