# ÍTEM 1 — Pregunta 1 (6 pts): el servicio de interpretación de órdenes

> Traducir una frase en español (`"agarra el cubo rojo"`) en una **decisión
> tipada** que el robot pueda ejecutar, con tiempo de respuesta acotado y
> medido. Todo el código de esta pregunta **ya existe** en el repo; aquí está
> explicado archivo por archivo y el paso a paso, comando por comando, para
> instalar LAYA, levantar el servicio y medirlo.
>
> Enunciado completo: `Parcial_Gran_Reto_JetCobot.docx` · detalle extra:
> `README_PARCIAL.md` · red sin LAYA: `GUIA_SIN_LAYA.md` §3.

---

## 1. Qué pide el enunciado (resumen)

1. Nodo ROS 2 **`interprete_ordenes`** con servicio **`/interpretar_orden`**:
   recibe una frase, devuelve al menos `acción`, `objeto`, `color`,
   `prioridad` (entero) y `permitido` (booleano). Internamente consulta a LAYA.
2. **Nada de texto libre**: la salida de LAYA debe ser una decisión tipada
   (elección, puntaje o sí/no). Justificar en el informe por qué importa esto
   en un sistema robótico (sin esta restricción, parsear "sí/no" de un texto
   redactado es ambiguo y un mal parseo mueve el brazo mal).
3. **Tiempo límite como parámetro del nodo**; si LAYA no contesta a tiempo →
   clasificador propio por palabras clave + bandera **degradada**. El sistema
   nunca se queda esperando.
4. Medir latencia sobre las **50 frases** del docente: **mediana y p95**,
   separando **red** de **cómputo**.
5. Repetir la medición en **calma** y con **todos los equipos cargando**.
6. Tabla comparativa de **exactitud**: LAYA vs clasificador.
7. Entregable: código, CSV con las 50 frases y la decisión de cada método,
   tablas de latencia (calma/carga) y de exactitud, media página de comentario
   sobre qué frases falla cada método.

---

## 2. Qué hace cada archivo de esta pregunta

| Archivo                                                    | Qué es / qué hace                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/arm_broker_interfaces/srv/InterpretarOrden.srv`       | Definición del servicio. **Petición**: `frase` (string) + `forzar_clasificador` (bool, para medir el clasificador por separado). **Respuesta**: `accion`, `objeto`, `color`, `prioridad` (0..255), `permitido`, `motivo`, más los metadatos `degradada`, `fuente` (`laya`/`palabras_clave`), `tiempo_total_s`, `tiempo_red_s`, `tiempo_computo_s`.                                                         |
| `src/arm_broker/arm_broker/interprete_ordenes.py`          | El nodo. Declara los parámetros `laya_url` (default `http://127.0.0.1:8000`), `timeout_laya_s` (2.0), `objetos`, `colores`, `acciones`. Al arrancar mide la **línea base de red** contra `/health` y crea el servicio. En cada llamadwha: intenta LAYA → si falla o expira el timeout, usa el clasificador local y marca `degradada=True`.                                                                 |
| `src/arm_broker/arm_broker/cliente_laya.py`                | **Único** módulo que habla HTTP. Arma las 5 preguntas tipadas (`choice` acción/objeto/color, `score` prioridad, `noul` permitido), hace `POST {url}/v1/systemone` con `timeout=timeout_laya_s`, lee `answers[qid].choice/score/noul` (tolera nombres `choice/score/noul/label/value/answer`) y devuelve un dict. También tiene `medir_red_base()` (5× `GET /health`, mediana) para separar red de cómputo. |
| `src/arm_broker/arm_broker/clasificador_palabras_clave.py` | Plan B **sin red ni IA**: diccionarios de sinónimos (`agarra/recoge/toma…`, `cubo/bloque…`, colores) + lista `PROHIBIDO` (`destornillador`, `cuchillo`, `mano`…). Devuelve el **mismo dict** que LAYA para que el nodo los trate igual. `permitido=False` si hay palabra prohibida o no se reconoció acción. **Prioridad siempre 1** (no estima urgencia).                                                 |
| `herramientas/probar_laya.py`                              | Prueba suelta **sin ROS 2**: `GET /health` + `POST /v1/systemone` con una frase y muestra la respuesta JSON **cruda**. Se corre **PRIMERO**, el día que tengas la IP, para confirmar los nombres de campo reales de LAYA.                                                                                                                                                                                  |
| `herramientas/medir_item1.py`                              | Cliente ROS 2 del servicio: para cada frase hace **dos** llamadas (una normal → LAYA o degradada; otra con `forzar_clasificador=True` → clasificador puro), guarda CSV fila a fila e imprime mediana/p95 de total/red/cómputo y la tabla de exactitud si el CSV trae columnas `esperado_*`.                                                                                                                |
| `herramientas/frases_ejemplo.csv`                          | 8 frases de prueba **con** columnas `esperado_accion,esperado_objeto,esperado_color,esperado_permitido`, para validar todo el flujo antes de tener las 50 oficiales.                                                                                                                                                                                                                                       |
| `src/arm_broker/setup.py`                                  | Ya registra el entry point: `'interprete_ordenes = arm_broker.interprete_ordenes:main'`.                                                                                                                                                                                                                                                                                                                   |
| `src/arm_broker_interfaces/CMakeLists.txt`                 | Ya registra el `.srv`: `rosidl_generate_interfaces(... "srv/InterpretarOrden.srv" ...)`. **No hay que tocar nada** salvo que se rompa el build.                                                                                                                                                                                                                                                            |

### Flujo completo de una llamada

```
frase ──► interprete_ordenes.callback()
             │  ¿forzar_clasificador?
             ├─ no ─► cliente_laya.preguntar()  ──HTTP──► LAYA (/v1/systemone)
             │          │ timeout_laya_s cumplido         (tu PC, GPU)
             │          ▼
             │        respuesta tipada  → degradada=False, fuente='laya'
             │          tiempo_red = línea base de /health (medida al arrancar)
             │          tiempo_computo = total - red
             │
             └─ sí / error / timeout ─► clasificador.clasificar()
                        ▼
                      misma forma de dict → degradada=True, fuente='palabras_clave'
```

---

## 3. Qué corre en qué dispositivo (Pregunta 1)

| Dispositivo                  | Qué se hace aquí                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------- |
| **Tu PC Windows (RTX 3050)** | Instalar y levantar **LAYA** (`laya-serve`), probarlo con `probar_laya.py`                        |
| **Jetson (ROS 2 Humble)**    | `colcon build`, correr **`interprete_ordenes`**, `ros2 service call`, correr **`medir_item1.py`** |
| **PC sin ROS (cualquiera)**  | Solo `probar_laya.py` (usa `requests`, no ROS)                                                    |

---

## 4. LAYA paso a paso en tu PC Windows

> LAYA es **self-hosted**: se instala y corre en tu máquina. No hay API en la
> nube; lo único que toca internet es la **descarga inicial** de los
> checkpoints desde Hugging Face (~2 GB en disco). Tu RTX 3050 laptop sirve
> para correrlo en GPU; si algo falla, hay ruta de CPU más abajo (§4.7).

### 4.1 Requisitos
- Windows 10/11, **Python 3.10 o superior** (recomendado 3.11/3.12).
- ~3 GB de disco (paquete + checkpoints) y ~2 GB de RAM/VRAM libres.
- CUDA de tu driver NVIDIA (no hace falta instalar el toolkit CUDA completo:
  el wheel de PyTorch ya trae las libs).

Comprueba la versión de Python (PowerShell):

```powershell
py -3 --version        # debe decir 3.10 o más
```

### 4.2 Crear el entorno virtual e instalar

```powershell
# 1) Carpeta de trabajo (puede ser la raíz de este repo o una aparte)
mkdir C:\laya ; cd C:\laya

# 2) Entorno virtual
py -3 -m venv .venv

# 3) Activar (se reconoce porque el prompt muestra (.venv))
.\.venv\Scripts\Activate.ps1
#    Si PowerShell se queja por política de ejecución, una sola vez:
#    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4) pip al día
python -m pip install -U pip

# 5) PyTorch con CUDA (para la RTX 3050). Si prefieres CPU, ve a §4.7
python -m pip install torch --index-url https://download.pytorch.org/whl/cu121

# 6) LAYA + servidor HTTP
python -m pip install "laya[serve]"

# 7) Verificación (imprime la versión sin cargar el modelo)
python -I -c "import laya; print(laya.__version__)"
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
```

`laya[serve]` agrega `fastapi + uvicorn` y el comando **`laya-serve`**.
Si `torch.cuda.is_available()` da `False`, revisa el paso 5 (o usa CPU).

> **Si ya tienes CUDA de otra versión**: `cu118` y `cu124` también sirven
> (`--index-url https://download.pytorch.org/whl/cu118`). La 3050 es
> arquitectura Ampere (sm_86), soportada por todas.

### 4.3 Levantar el servidor

```powershell
# Sigue con la venv activada (prompt con (.venv)), en C:\laya
$env:LAYA_HOST   = "0.0.0.0"                       # escuchar en la red local, no solo localhost
$env:LAYA_PORT   = "8000"
$env:LAYA_DEVICE = "cuda"                          # o "cpu"
$env:LAYA_MODELS = "multilingual"                  # solo el checkpoint de 100+ idiomas (español)
$env:LAYA_PRELOAD = "1"                            # cárgalo al arrancar (evita frío en la 1ª consulta)
# Opcional: si quieres exigir clave al cliente
# $env:LAYA_API_KEY = "una-clave-larga-que-inventes"

laya-serve
```

Salida esperada: el servidor escucha en `0.0.0.0:8000` y **al arrancar (por
`LAYA_PRELOAD=1`) descarga** el checkpoint `laya-multilingual` de Hugging Face
(~1.3 GB, solo la primera vez; después usa la caché de `~/.cache/huggingface`).
Sin `PRELOAD`, la descarga ocurre en la primera consulta.

Por qué `LAYA_MODELS=multilingual` y no los tres checkpoints: el router manda
todo el texto **español** al checkpoint multilingüe (322M parámetros); cargar
los 3 (~1.160M) en una 3050 de 4 GB es justo de memoria y no aporta nada aquí.
Los tres juntos solo si tienes VRAM de sobra (`$env:LAYA_PRELOAD="1"` sin
`LAYA_MODELS`).

### 4.4 Abrir el firewall de Windows (necesario para que la Jetson te llegue)

Administrador de PowerShell:

```powershell
New-NetFirewallRule -DisplayName "laya-serve :8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### 4.5 Verificar desde tu propia PC

```powershell
# a) Salud del servidor
curl.exe -s http://127.0.0.1:8000/health

# b) Una decisión real (mismo payload que usa cliente_laya.py)
$body = @{
  state     = @{ body = "agarra el cubo rojo" }
  questions = @{
    accion    = @{ type = "choice"; instructions = "¿Qué acción pide la frase?";
                   criteria = @("agarrar","soltar","mover","detener","desconocido") }
    objeto    = @{ type = "choice"; instructions = "¿Sobre qué objeto actúa?";
                   criteria = @("cubo","cilindro","esfera","desconocido") }
    color     = @{ type = "choice"; instructions = "¿De qué color?";
                   criteria = @("rojo","verde","azul","amarillo","ninguno") }
    prioridad = @{ type = "score";  instructions = "¿Qué tan urgente, 0 a 3?";
                   criteria = @("0","1","2","3") }
    permitido = @{ type = "noul";   instructions = "¿Es una orden segura de ejecutar en una mesa real?" }
  }
} | ConvertTo-Json -Depth 8

$body | Out-File -Encoding utf8 payload.json

curl.exe -s http://127.0.0.1:8000/v1/systemone -H "content-type: application/json" -d "@payload.body"
```

Con el script del repo (sirve también desde una PC **sin** ROS 2):

```powershell
cd C:\Users\asx\Documents\"CICLO 4"\ROBOTICA\PARCIALLLLLLLLLLLLLLL\carrprp
python -m pip install requests
python herramientas\probar_laya.py http://127.0.0.1:8000 "agarra el cubo rojo"
```

`probar_laya.py` imprime primero `GET /health` (debe dar `status=200`) y
después la **respuesta cruda** de `/v1/systemone`. Fíjate en que existan
`answers.accion.choice`, `answers.prioridad.score`, `answers.permitido.noul`.

### 4.6 Probar desde la Jetson (que es como se usará el día del examen)

```bash
# En la Jetson (bash): ¿llego a la PC?
curl -s http://<IP_DE_TU_PC>:8000/health

# Misma prueba con el script del repo
python3 herramientas/probar_laya.py http://<IP_DE_TU_PC>:8000 "agarra el cubo rojo"
```

Si no conecta: IP correcta, mismo Wi-Fi/LAN, firewall de Windows abierto
(§4.4), y `laya-serve` levantado con `0.0.0.0` (no `127.0.0.1`).

### 4.7 Ruta CPU (si la GPU da problemas)

```powershell
$env:LAYA_DEVICE = "cpu"
$env:LAYA_MODELS = "multilingual"
laya-serve
```
Más lento (decenas-hcientos de ms extra por consulta en CPU), pero el flujo
es idéntico. Para la medición de latencia de la P1, apunta siempre a la
configuración con la que vas a demostrar (si usas CPU, decláralo así en el
informe).

### 4.8 Si la respuesta real de LAYA trae otros nombres de campo

El formato exacto del JSON **solo se confirma contra el servidor real**
(por eso existe `probar_laya.py`). Si ves, por ejemplo, `answers.accion.label`
en vez de `answers.accion.choice`, se agrega esa clave a la lista que prueba
`_extraer()` en `src/arm_broker/arm_broker/cliente_laya.py:50`:

```python
for clave in ('choice', 'score', 'noul', 'label', 'value', 'answer'):
```

Además: `cliente_laya.medir_red_base()` estima el cómputo como
`total − línea_base_de_/health`. Si el servidor real devolviera un campo de
tiempo propio en la respuesta, úsalo directo (revisarlo con `probar_laya.py`)
y documenta el cambio.

### 4.9 Sobre la "nube" de LAYA
- **No existe API oficial en la nube de LAYA**: el modelo es tuyo, corre en tu
  PC. Lo que usa internet es: (a) la **descarga** de checkpoints de Hugging
  Face la primera vez, y (b) opcionalmente el ESPACIO público de demostración
  de Hugging Face, que **no** expone `/v1/systemone` y por lo tanto **no sirve**
  para este proyecto (nuestro cliente habla ese protocolo exacto).
- La **nube** en este examen es para otra cosa: la **transcripción** de audio
  con Google AI Studio (Pregunta 3, ver `ITEM_3.md`).

---

## 5. El nodo en la Jetson: compile, arranque y prueba

> En la Jetson, con ROS 2 Humble. Ajusta `~/rb2_ws` a la ruta real de tu clone.

### 5.1 Compilar (una sola vez, o tras tocar código)

```bash
source /opt/ros/humble/setup.bash
cd ~/rb2_ws
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

Si `colcon build` no encuentra `InterpretarOrden`: revisa que el `.srv`
existe en `src/arm_broker_interfaces/srv/` con su separador `---`, y que la
línea `"srv/InterpretarOrden.srv"` está dentro de `rosidl_generate_interfaces`
del `CMakeLists.txt`.

### 5.2 Entorno de red ROS (las 4 PC + Jetson deben coincidir)

```bash
export ROS_DOMAIN_ID=43                      # o 47: UNIFICAR erosn todas las máquinas
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"   # IP real del Discovery Server
ros2 daemon stop; ros2 daemon start
```

### 5.3 Arrancar el nodo apuntando a tu PC

```bash
# Si el servidor pide clave, expórtala en LA JETSON también (nunca en el código)
export LAYA_API_KEY="misma-clave-que-en-el-servidor"   # solo si la usaste

ros2 run arm_broker interprete_ordenes --ros-args \
  -p laya_url:=http://<IP_DE_TU_PC>:8000 \
  -p timeout_laya_s:=2.0 \
  -p objetos:="['cubo','cilindro','esfera']" \
  -p colores:="['rojo','verde','azul','amarillo']" \
  -p acciones:="['agarrar','soltar','mover','detener']"
```

Al arrancar imprime la línea base de red medida contra `/health` (un warning
si LAYA no está arriba **no** es error: el nodo sigue vivo).

### 5.4 Probar el servicio a mano (otra terminal, con `source install/setup.bash`)

```bash
# Normal (irá a LAYA)
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo'}"

# Forzando el clasificador local (sin tocar LAYA)
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo', forzar_clasificador: true}"
```

Log esperado en la terminal del nodo:

```
✅ [LAYA] "agarra el cubo rojo" → agarrar/cubo/rojo p=1 permitido=True · 420 ms
```

### 5.5 Prueba sin LAYA (demuestra el respaldo)

Detén `laya-serve` (o apunta a una IP muerta) y vuelve a llamar: a los 2 s
responde el clasificador con `degradada=True`:

```
⚠️  [DEGRADADA] "agarra el cubo rojo" → agarrar/cubo/rojo p=1 permitido=True · 2003 ms
```
Eso es la evidencia de que **el sistema nunca se queda esperando**.

---

## 6. Medición: latencia y exactitud (la evidencia de la P1)

### 6.1 Primero con las 8 frases de ejemplo (validación del flujo)

```bash
# Jetson, con interprete_ordenes corriendo y LAYA arriba
python3 herramientas/medir_item1.py herramientas/frases_ejemplo.csv salida_prueba.csv
```

### 6.2 Las 50 frases oficiales

Crea `frases_50.csv` con la columna `frase` (las 50 que entrega el docente) y,
para la tabla de exactitud, agrega `esperado_accion,esperado_objeto,
esperado_color,esperado_permitido` con la respuesta correcta que ustedes
definen para cada una (formato igual que `frases_ejemplo.csv`).

**ANTES de correr, anota lo que esperas obtener** (regla del examen), por
ejemplo: *"esperamos mediana ≈ 300 ms y p95 ≈ 900 ms en calma; bajo carga la
mediana se duplica; LAYA ≥ 85 % de exactitud, clasificador ≈ 70 %"*.

```bash
# Corrida 1 — laboratorio en calma
python3 herramientas/medir_item1.py frases_50.csv resultados_calma.csv

# Corrida 2 — con los 4 equipos preguntando a la vez (coordinar la sección)
python3 herramientas/medir_item1.py frases_50.csv resultados_carga.csv
```

### 6.3 Qué te imprime y qué entregar

- Por frase: resultado de LAYA y del clasificador, marcando `⚠️ DEGRADADA`
  cuando LAYA no contestó a tiempo.
- Resumen: **mediana y p95** de `total`, `red (aprox.)`, `cómputo (aprox.)`.
- Tabla de exactitud LAYA vs clasificador (solo si el CSV trae `esperado_*`).
- CSV fila por fila con todo (esa es la evidencia que se entrega).

Con eso se arman las tres tablas del entregable:

| Entregable P1 | De dónde sale |
|---|---|
| CSV con 50 frases y decisión por método | `resultados_calma.csv` / `resultados_carga.csv` |
| Tabla de latencia en calma | resumen de `medir_item1.py` (corrida 1) |
| Tabla de latencia bajo carga | resumen de `medir_item1.py` (corrida 2) |
| Tabla de exactitud LAYA vs clasificador | sección EXACTITUD del resumen |
| Media página: qué frases falla cada método | comparar filas `acierto_laya=False` vs `acierto_clasificador=False` en el CSV |

Patrones típicos a buscar en esa media página: el clasificador **falla** con
sinónimos no listados (`"agarrame el cubito"`, `"recoge la bolita"`), frases
sin acción clara y manda **prioridad siempre 1**; LAYA **falla** con frases
vagas o dobles acciones (`"agarra el cubo y déjalo azul"`) y puede marcar mal
`permitido` en órdenes raras. Si hay `DEGRADADAS`, explica por qué (timeout o
servidor saturado).

---

## 7. Checklist de la Pregunta 1

1. [x] PC: Python ≥3.10 → venv → `torch` CUDA → `pip install "laya[serve]"` (§4.2).
2. [x] PC: firewall :8000 (§4.4) y `laya-serve` con `0.0.0.0` + `LAYA_MODELS=multilingual` (§4.3).
3. [x] PC: `curl /health` OK y `probar_laya.py` muestra `answers.*` con campo reales (§4.5).
4. [x] Jetson: `colcon build` de `arm_broker_interfaces` + `arm_broker` (§5.1).
5. [x] Jetson: `interprete_ordenes` con `-p laya_url:=http://<IP_PC>:8000` (§5.3).
6. [x] `ros2 service call` normal y con `forzar_clasificador` (§5.4).
7. [x] Corte de red: demostrar `degradada=True` sin LAYA (§5.5).
8. [x] Anotar predicción de mediana/p95 **antes** de medir.
9. [x] `medir_item1.py` con las 8 frases → luego 50 frases, calma y carga (§6).
10. [ ] Tablas (latencia calma/carga + exactitud) y media página de comentarios.
