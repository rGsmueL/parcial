# PASOS ITEM 1 — intérprete de órdenes (LAYA + clasificador de respaldo)

Guía completa desde `git clone` hasta las evidencias (latencia y exactitud sobre las 50 frases).

---

## 0. Qué hace este ítem

Nodo ROS 2 `interprete_ordenes` con el **servicio `/interpretar_orden`**: recibe una frase y
devuelve `accion`, `objeto`, `color`, `prioridad`, `permitido` (+ `degradada`, `fuente`,
`tiempo_total/red/computo`). Internamente consulta a **LAYA** (por HTTP) y, si no contesta en
`timeout_laya_s`, cae al **clasificador local por palabras clave** (marca `degradada=True`).

> Regla del examen: LAYA responde **preguntas tipadas** (choice / score / sí-no), nunca texto
> libre. `interprete_ordenes` es el único puente entre ROS 2 y la PC de LAYA.

---

## 1. Prerrequisitos

- **PC Windows**: Python 3.10+ (3.11/3.12 recomendado), ~3 GB disco, ~2 GB RAM/VRAM, GPU NVIDIA con CUDA.
- **Jetson con ROS 2 Humble** + `colcon`.
- Red local entre Windows y Jetson (mismo dominio ROS).

---

## 2. Desde `git clone`, en la Jetson (y PCs con ROS)

```bash
# 1) Clonar el repo (URL real; PASOS.txt viejo usaba otra)
git clone https://github.com/rGsmueL/parcial.git ~/rb2_ws
cd ~/rb2_ws

# 2) Entorno ROS 2 + red (unificar en TODAS las máquinas)
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID + 1))   # = 43   (42 + nº de equipo; 5 máquinas iguales)
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start

# 3) Dependencia Python del cliente HTTP
pip3 install requests --break-system-packages

# 4) Compilar (en este repo ya está todo copiado y registrado)
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

> Si `colcon build` falla por `InterpretarOrden` no encontrado: revisa que
> `src/arm_broker_interfaces/srv/InterpretarOrden.srv` tenga el separador `---` y que
> `"srv/InterpretarOrden.srv"` esté dentro de `rosidl_generate_interfaces(...)` en el `CMakeLists.txt`.

---

## 3. Levantar LAYA en la PC Windows

En PowerShell (termina en un entorno venv):

```powershell
mkdir C:\laya ; cd C:\laya
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
# si PowerShell se queja:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install -U pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
python -m pip install "laya[serve]"

$env:LAYA_HOST    = "0.0.0.0"      # escucha en toda la red local
$env:LAYA_PORT    = "8000"
$env:LAYA_DEVICE  = "cuda"         # o "cpu" si falla la GPU
$env:LAYA_MODELS  = "multilingual" # un solo checkpoint, cabe en 4 GB
$env:LAYA_PRELOAD = "1"
# opcional: $env:LAYA_API_KEY = "una-clave-larga-que-inventes"

laya-serve
```

Firewall de Windows (una sola vez, PowerShell **como administrador**):

```powershell
New-NetFirewallRule -DisplayName "laya-serve :8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Verificar LAYA (debe dar `status=200`):

```powershell
curl.exe -s http://127.0.0.1:8000/health
python herramientas\probar_laya.py http://127.0.0.1:8000 "agarra el cubo rojo"
```

Obtén la IP de tu PC con `ipconfig` (p. ej. `192.168.1.50`); desde la Jetson:

```bash
curl -s http://<IP_DE_TU_PC>:8000/health
python3 herramientas/probar_laya.py http://<IP_DE_TU_PC>:8000 "agarra el cubo rojo"
```

---

## 4. Arranque en la Jetson

### Terminal A — el nodo

```bash
cd ~/rb2_ws && source install/setup.bash
export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID + 1))
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start
export LAYA_API_KEY="misma-clave-que-en-el-servidor"   # solo si la pide

ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP_DE_TU_PC>:8000 \
  -p timeout_laya_s:=2.0 \
  -p objetos:="['cubo','cilindro','esfera']" \
  -p colores:="['rojo','verde','azul','amarillo']" \
  -p acciones:="['agarrar','soltar','mover','detener']"
```

Al arrancar mide la línea base de red contra `/health`. Un warning porque LAYA aún no está
arriba **no es error**.

### Terminal B — probar el servicio (normal y clasificador)

```bash
cd ~/rb2_ws && source install/setup.bash

# Normal (va a LAYA)
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo'}"

# Forzando el clasificador local (sin tocar LAYA)
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo', forzar_clasificador: true}"
```

Logs esperados:

```
✅ [LAYA] "agarra el cubo rojo" → agarrar/cubo/rojo p=1 permitido=True · 420 ms
⚠️  [DEGRADADA] "agarra el cubo rojo" → agarrar/cubo/rojo p=1 permitido=True · 2003 ms
🔁 [CLASIFICADOR, pedido] ...
```

---

## 5. Medir latencia y exactitud (evidencia)

Con `interprete_ordenes` corriendo y desde la **raíz** del workspace (`frases_50.csv` está ahí):

```bash
cd ~/rb2_ws && source install/setup.bash

# Validación rápida (8 frases)
python3 herramientas/medir_item1.py herramientas/frases_ejemplo.csv salida_prueba.csv

# Corrida 1 — laboratorio en calma
mkdir -p evidencia
python3 herramientas/medir_item1.py frases_50.csv resultados_calma.csv \
  2>&1 | tee evidencia/resumen_calma.txt

# Corrida 2 — con los 4 equipos preguntando a la vez
python3 herramientas/medir_item1.py frases_50.csv resultados_carga.csv \
  2>&1 | tee evidencia/resumen_carga.txt
```

El script imprime resumen de **mediana y p95** de `tiempo total / red / cómputo` y la tabla de
**exactitud LAYA vs clasificador** si el CSV trae columnas `esperado_*`.

---

## 6. Evidencias que se piden

| Archivo | Comando que lo genera |
|---|---|
| `frases_50.csv` | ya está en la raíz (con `esperado_*`) |
| `evidencia/laya_prueba.txt` | `probar_laya.py` en Windows |
| `evidencia/servicio_interpretar.txt` | `ros2 service call /interpretar_orden ...` (normal y degradada) |
| `resultados_calma.csv` | `medir_item1.py frases_50.csv resultados_calma.csv` |
| `resultados_carga.csv` | idem mientras los 4 equipos cargan |
| `evidencia/resumen_calma.txt` / `resumen_carga.txt` | stdout de `medir_item1.py` |
| Tablas latencia (calma/carga) + exactitud | de los resúmenes |
| Media página de comentario | qué frases falla cada método (`acierto_laya` / `acierto_clasificador`) |

Predicción previa (regla del examen): anota antes de medir el valor esperado
(p. ej. "mediana ≈ 300 ms, p95 ≈ 900 ms en calma; bajo carga la mediana se duplica").

---

## 7. Problemas comunes

- **Falta `requests`** → `ImportError`: `pip3 install requests --break-system-packages`.
- **Jetson no conecta con LAYA**: firewall TCP 8000 abierto y `LAYA_HOST=0.0.0.0` (no `127.0.0.1`).
- **Camino por defecto `http://127.0.0.1:8000` no sirve desde la Jetson**: pasa `-p laya_url:=http://<IP_PC>:8000`.
- **Resumen LAYA vacío**: todas las respuestas degradadas (LAYA no respondió); revisa la red.
- **Prioridad del clasificador siempre 1** (no estima urgencia); úsalo en el informe de exactitud.
- **Campos de LAYA**: `_extraer()` tolera `choice/score/noul/label/value/answer`; si el JSON real difiere, ajusta esa lista en `cliente_laya.py`.

---

## 8. Checklist de entrega

- [ ] `interprete_ordenes` responde por `/interpretar_orden`.
- [ ] Degradación a clasificador funciona (apaga LAYA y repite).
- [ ] `resultados_calma.csv` y `resultados_carga.csv`.
- [ ] `evidencia/resumen_calma.txt` y `resumen_carga.txt`.
- [ ] `evidencia/laya_prueba.txt` y `evidencia/servicio_interpretar.txt`.
- [ ] Tablas de latencia (calma/carga) y de exactitud + media página de comentario.