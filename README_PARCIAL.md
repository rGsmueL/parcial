# Ítem 1 (Pregunta 1 del Parcial) — interprete_ordenes

Resuelve: nodo `interprete_ordenes` con el servicio `/interpretar_orden`, clasificador de
respaldo por palabras clave, y las herramientas para medir latencia (mediana/p95) y exactitud
sobre las 50 frases.

## Qué hace cada archivo

```
arm_broker_interfaces/srv/InterpretarOrden.srv   → definición del servicio (nuevo)
arm_broker/arm_broker/interprete_ordenes.py      → el nodo (nuevo)
arm_broker/arm_broker/cliente_laya.py            → habla por HTTP con LAYA (nuevo)
arm_broker/arm_broker/clasificador_palabras_clave.py → respaldo sin red (nuevo)
herramientas/probar_laya.py                      → prueba suelta, sin ROS 2 (correr PRIMERO)
herramientas/medir_item1.py                      → corre las 50 frases y saca las tablas
herramientas/frases_ejemplo.csv                  → 8 frases de prueba, para probar el flujo
                                                    antes de tener las 50 oficiales
```

Los tres archivos de `arm_broker/arm_broker/` van **dentro de su paquete `arm_broker` ya
existente**, junto a `fk.py`, `broker.py`, `cliente.py`, `politicas.py`. El `.srv` va dentro
de su paquete `arm_broker_interfaces` ya existente, junto a `action/MoveArm.action` y
`msg/QueueState.msg`.

## 1. Copiar los archivos a su workspace

```bash
cp arm_broker_interfaces/srv/InterpretarOrden.srv  ~/ros2_ws/src/arm_broker_interfaces/srv/
cp arm_broker/arm_broker/interprete_ordenes.py     ~/ros2_ws/src/arm_broker/arm_broker/
cp arm_broker/arm_broker/cliente_laya.py           ~/ros2_ws/src/arm_broker/arm_broker/
cp arm_broker/arm_broker/clasificador_palabras_clave.py ~/ros2_ws/src/arm_broker/arm_broker/
```

Ajusten las rutas de arriba a donde realmente tengan su workspace y sus paquetes.

## 2. Registrar el nuevo servicio en `arm_broker_interfaces`

Abran `arm_broker_interfaces/CMakeLists.txt` y busquen el bloque `rosidl_generate_interfaces(...)`
(ya debe tener ahí `action/MoveArm.action` y `msg/QueueState.msg`). Agréguenle la línea del
nuevo `.srv`:

```cmake
rosidl_generate_interfaces(${PROJECT_NAME}
  "action/MoveArm.action"
  "msg/QueueState.msg"
  "srv/InterpretarOrden.srv"      # <-- agregar esta línea
  DEPENDENCIES std_msgs
)
```

(El nombre exacto de ese bloque en su CMakeLists puede variar un poco — lo importante es
agregar `"srv/InterpretarOrden.srv"` a la lista de interfaces que ya tienen.)

## 3. Registrar el nuevo nodo en `arm_broker`

Abran `arm_broker/setup.py` y, en `entry_points` → `console_scripts` (donde ya deben tener
algo como `'cliente = arm_broker.cliente:main'`), agreguen:

```python
'interprete_ordenes = arm_broker.interprete_ordenes:main',
```

## 4. Dependencia `requests`

El cliente HTTP a LAYA usa la librería `requests` (no es parte de ROS 2):

```bash
pip3 install requests --break-system-packages
```

## 5. Compilar

```bash
cd ~/ros2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

Si `colcon build` se queja de no encontrar `InterpretarOrden`, revisen que el `.srv` haya
quedado bien copiado (con el separador `---` entre petición y respuesta) y que la línea del
paso 2 esté dentro del bloque correcto del CMakeLists.

## 6. Probar la conexión a LAYA ANTES de confiar en el nodo

El día del examen, apenas tengan la IP y puerto reales:

```bash
python3 herramientas/probar_laya.py http://<IP>:<PUERTO> "agarra el cubo rojo"
```

Esto imprime la respuesta JSON cruda de LAYA. **Revisen que los campos `accion`, `objeto`,
`color`, `prioridad`, `permitido` se puedan reconocer** (el script `cliente_laya.py` ya
intenta varios nombres comunes — `choice`, `score`, `noul`, `label`, `value`, `answer` —
pero si el formato real es distinto, ajusten la función `_extraer()` en
`arm_broker/cliente_laya.py` con lo que vean acá).

Importante sobre el tiempo de cómputo del servidor: la documentación pública de LAYA **no
incluye un campo de tiempo de procesamiento en la respuesta**. `cliente_laya.py` lo aproxima
así: mide una línea base de red contra `/health` (que no hace cómputo real) al arrancar el
nodo, y resta esa línea base del tiempo total de cada pregunta para estimar el cómputo. Si el
`probar_laya.py` muestra que la respuesta real SÍ trae un campo de tiempo propio, díganmelo
o ajústenlo ustedes: es mejor usar ese valor directo que la aproximación.

## 7. Correr el nodo

```bash
ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP>:<PUERTO> \
  -p timeout_laya_s:=2.0 \
  -p objetos:="['cubo','cilindro','esfera']" \
  -p colores:="['rojo','verde','azul','amarillo']" \
  -p acciones:="['agarrar','soltar','mover','detener']"
```

Si no pasan `-p laya_url:=...`, usa `http://127.0.0.1:8000` por defecto (sirve para probar
localmente si alguien levanta un LAYA de prueba en su propia máquina).

Si el laboratorio pide clave de API:

```bash
export LAYA_API_KEY="su-clave-de-google-ai-studio-o-laya"
```
(nunca la escriban en el código ni la suban al repo — ver indicaciones generales del examen)

## 8. Probar el servicio a mano

En otra terminal (con el mismo `source install/setup.bash`):

```bash
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo'}"
```

Para forzar el clasificador local (sin tocar LAYA):

```bash
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo', forzar_clasificador: true}"
```

En la terminal donde corre el nodo deberían ver líneas como:

```
✅ [LAYA] "agarra el cubo rojo" → agarrar/cubo/rojo p=1 permitido=True · 420 ms
```

## 9. Medir latencia y exactitud (evidencia de la Pregunta 1)

Primero prueben con el CSV de ejemplo (8 frases) para validar que todo el flujo funciona:

```bash
python3 herramientas/medir_item1.py herramientas/frases_ejemplo.csv salida_prueba.csv
```

El día del examen, con las 50 frases oficiales del docente (agréguenle ustedes las columnas
`esperado_accion,esperado_objeto,esperado_color,esperado_permitido` con la respuesta correcta
que definan para cada una, si quieren la tabla de exactitud):

```bash
# Primera corrida: laboratorio en calma
python3 herramientas/medir_item1.py frases_50.csv resultados_calma.csv

# Segunda corrida: con los 4 equipos preguntando a la vez (coordinar con el resto de la sección)
python3 herramientas/medir_item1.py frases_50.csv resultados_carga.csv
```

El script imprime en pantalla, bien visible:
- cada frase con el resultado de LAYA y del clasificador, marcando `⚠️ DEGRADADA` cuando LAYA
  no contestó a tiempo,
- el resumen final de mediana y p95 (total / red / cómputo),
- la tabla de exactitud LAYA vs. clasificador (si el CSV trae las columnas `esperado_*`).

Y guarda todo el detalle fila por fila en el CSV de salida — eso es lo que entregan junto con
la media página de comentario que pide el enunciado.

## Qué es cada cosa, en una frase

- **Servicio ROS 2** (`/interpretar_orden`): como una función remota — pides algo, esperas la
  respuesta, y listo (a diferencia de la acción `move_arm` del RB-2, que tiene cola, feedback
  y puede tardar).
- **LAYA**: el modelo de IA del laboratorio. No es un nodo ROS 2, se le habla por HTTP.
  Responde preguntas tipadas (elegir una opción, un nivel, o sí/no) — nunca redacta texto,
  por diseño, que es exactamente lo que pide el examen.
- **Clasificador por palabras clave**: su propio código, sin red ni IA, que busca palabras
  conocidas en la frase. Es el plan B cuando LAYA no contesta a tiempo.
- **`degradada`**: bandera en la respuesta que indica si contestó el clasificador (`True`) o
  LAYA (`False`) — así pueden filtrar después en sus tablas.
