# ITEM 3 — Guía paso a paso: de la voz al movimiento

> Esta carpeta (`docs/item3/`) trae **el código y la guía** de la Pregunta 3 del Parcial
> (6 pts): **voz → texto → decisión (Ítem 1) → cola del broker (Ítem 2) → brazo**.
> Asume que **ya tienes el Ítem 1 funcionando** (`interprete_ordenes` + LAYA) y tu
> **API key de Google AI Studio**.
>
> Modelo usado en todo: **`gemini-2.5-flash`**.
> Contexto general: `docs/CONTEXTO.md` · detalle de la P0: `docs/ITEM_1.md`,
> `docs/ITEM_2.md`, `docs/ITEM_3.md`.

---

## 0. Qué hay en esta carpeta y a dónde va cada archivo

| Archivo aquí (`docs/item3/`) | Cópialo a (ruta destino) | Qué es |
|---|---|---|
| `voz_google.py` | `src/arm_broker/arm_broker/` | Cliente HTTP a Google AI Studio (Gemini 2.5). Único que sabe HTTP. |
| `transcriptor_voz.py` | `src/arm_broker/arm_broker/` | Nodo ROS 2: audio → texto → `/interpretar_orden`. Fallback a teclado. |
| `orquestador.py` | `src/arm_broker/arm_broker/` | Orquestador mínimo: decisión → rechazo o goal `move_arm`. |
| `probar_transcripcion.py` | `herramientas/` | Prueba Gemini **sin ROS 2** (córrelo primero). |
| `graficar_tiempos.py` | `herramientas/` | CSV `etapa,mediana_s` → figura `.png` del desglose. |
| `setup_entrypoints.txt` | (referencia) | Las 2 líneas que agregas a `src/arm_broker/setup.py`. |
| `transcripciones.csv` | (evidencia) | Cabecera del registro audio+transcripción. |
| `plantilla_ordenes.csv` | (evidencia) | Plantilla de la tabla de las 5 órdenes. |

> **Flujo que vamos a construir**
> `orden.wav → Gemini 2.5-flash (nube) → texto → /interpretar_orden (Ítem 1) →
> /orden_decidida → orquestador → (rechazo | goal move_arm) → broker → brazo`

---

## 1. Requisitos y qué corre en cada dispositivo

| Dispositivo | Corre aquí |
|---|---|
| **Tu PC Windows** | `laya-serve` (decisión, funciona **sin internet**) |
| **Jetson (ROS 2 Humble)** | driver `sync_plan_nx`, `broker`, `interprete_ordenes`, **`transcriptor_voz`** (nuevo) y **`orquestador`** (nuevo), bags |
| **Internet (nube)** | **Google AI Studio**: transcripción del audio |

Dato del enunciado que guía el diseño: *la transcripción depende de internet; la decisión
y el movimiento, no*. Por eso LAYA es local y solo la transcripción sale a la nube.

En la Jetson necesitas además:
```bash
python3 -m pip install requests        # si no está ya (lo usa interprete_ordenes/cliente_laya)
# opcional, solo para el gráfico:
python3 -m pip install matplotlib
```

---

## 2. Seguridad: la clave de Google AI Studio

> **Nunca** pegues la clave en un `.py` ni la subas al repo (el docx descuenta puntos).
> En este repo hay una clave escrita en `docs/ITEM_3.md` y audios (`orden.wav`,
> `orden.aac`): **rótala** en <https://aistudio.google.com/apikey> y borra cualquier copia
> de la clave del repositorio antes de entregar.

Expórtala **solo como variable de entorno**:

```powershell
# Windows (PowerShell)
$env:GOOGLE_API_KEY = "TU_CLAVE_NUEVA"
```
```bash
# Jetson (bash)
export GOOGLE_API_KEY="TU_CLAVE_NUEVA"
```

El código lee la clave con `voz_google.clave_desde_entorno()` → `os.environ['GOOGLE_API_KEY']`.

---

## 3. Prueba Gemini ANTES de tocar ROS 2 (paso clave)

Primero copia el probador a su sitio y prepara un audio de prueba en la Jetson (o en tu PC):

```bash
# Grabar 8 s por micrófono en la Jetson (ajusta -D con `arecord -l`)
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav
```

```bash
# Copia del código y prueba SIN ROS 2
cp docs/item3/probar_transcripcion.py herramientas/
python3 herramientas/probar_transcripcion.py orden_01.wav            # usa gemini-2.5-flash
python3 herramientas/probar_transcripcion.py orden_01.wav gemini-2.5-flash
```

Salida esperada: `Transcripción (… ms): 'agarra el cubo rojo'`.

Si el nombre del modelo no existe, lista los modelos disponibles:
```bash
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY" | head
```
Usa cualquiera que soporte audio (p. ej. `gemini-2.5-flash`) y pásalo con `-p google_model:=…`.

> El probador importa `voz_google` desde `src/arm_broker/`; por eso el `probar_transcripcion.py`
> debe quedar en `herramientas/` (un nivel bajo la raíz del repo), como `probar_laya.py`.

---

## 4. Copiar el código a su sitio, entry points y build

```bash
# 1) Copiar los 3 nodos/módulos al paquete
cp docs/item3/voz_google.py     src/arm_broker/arm_broker/
cp docs/item3/transcriptor_voz.py src/arm_broker/arm_broker/
cp docs/item3/orquestador.py    src/arm_broker/arm_broker/

# 2) Agregar los entry points en src/arm_broker/setup.py (ver setup_entrypoints.txt)
#    dentro de entry_points['console_scripts'], junto a 'interprete_ordenes = ...':
#      'transcriptor_voz = arm_broker.transcriptor_voz:main',
#      'orquestador = arm_broker.orquestador:main',
```

Verifica que `setup.py` quede así:
```python
    entry_points={
        'console_scripts': [
            'broker = arm_broker.broker:main',
            'cliente = arm_broker.cliente:main',
            'interprete_ordenes = arm_broker.interprete_ordenes:main',
            'transcriptor_voz = arm_broker.transcriptor_voz:main',   # <-- nuevo
            'orquestador = arm_broker.orquestador:main',             # <-- nuevo
        ],
    },
```

```bash
# 3) Compilar (Jetson)
source /opt/ros/humble/setup.bash
cd ~/rb2_ws                                    # ajusta a la ruta real de tu clone
colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

---

## 5. Arranque de la cadena completa (por terminal)

**Terminal A — tu PC Windows (fuera de ROS 2): LAYA**
```powershell
cd C:\laya ; .\.venv\Scripts\Activate.ps1
$env:LAYA_HOST="0.0.0.0"; $env:LAYA_PORT="8000"; $env:LAYA_DEVICE="cuda"
$env:LAYA_MODELS="multilingual"; $env:LAYA_PRELOAD="1"
laya-serve
```

**Jetson — Terminal 0 (driver):**
```bash
source /opt/ros/humble/setup.bash
ros2 run jetcobot_driver sync_plan_nx
```

**Jetson — Terminal 1 (broker, prioridad con envejecimiento):**
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=43                 # UNIFICAR en todas las máquinas
cd ~/rb2_ws && source install/setup.bash
ros2 run arm_broker broker --ros-args -p politica:=prioridad -p tau_envejecimiento_s:=12.0
```

**Jetson — Terminal 2 (intérprete del Ítem 1, ya lo tienes):**
```bash
cd ~/rb2_ws && source install/setup.bash
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000
```

**Jetson — Terminal 3 (orquestador NUEVO):**
```bash
cd ~/rb2_ws && source install/setup.bash
ros2 run arm_broker orquestador --ros-args \
  -p client_id:=voz -p escala_prioridad:=85 \
  -p topico_decision:=orden_decidida
```
> Las poses por color de `mapa_poses` son **placeholder** (no hay cámara todavía). Ajústalas
> a poses seguras de tu kit si quieres ver movimiento real.

**Jetson — Terminal 4 (transcriptor de voz NUEVO):**
```bash
cd ~/rb2_ws && source install/setup.bash
export GOOGLE_API_KEY="TU_CLAVE_NUEVA"
ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p google_model:=gemini-2.5-flash \
  -p timeout_transcripcion_s:=5.0 -p n_ordenes:=1
```

Verifica en **otra** terminal que hay un solo publicador de `/joint_states` (regla eliminatoria):
```bash
python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt
```

---

## 6. Parte B — Las 5 órdenes habladas

1. Graba 5 audios `orden_01.wav … orden_05.wav` con el docente. **Incluye obligatoriamente**:
   - una con **objeto que no está sobre la mesa** (→ el modelo lo marca desconocido/no permitido),
   - una **no permitida** (→ rechazo `no_permitida` antes de encolar).
2. Procesa cada uno (vuelve a lanzar el nodo por orden, o usa `-p n_ordenes:=5` con la
   misma `ruta_audio`; para 5 audios distintos relanza con `-p ruta_audio:=orden_0X.wav`):
   ```bash
   ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_02.wav -p n_ordenes:=1
   ```
3. Llena `plantilla_ordenes.csv` (→ `ordenes_demo.csv`):

| n | se dijo (audio) | transcribió | acción/objeto/color/prioridad/permitido | rechazo/encolado | qué hizo el brazo | ¿correcto? |
|---|---|---|---|---|---|---|
| 1 | `orden_01.wav` | … | … | … | … | sí/no |
| 2 | `orden_02.wav` | … | … | … | … | … |
| … | | | | | | |

Criterio de acierto (del enunciado): resultado **final** esperado, **incluido el rechazo**:
- objeto inexistente → no se mueve;
- no permitida → rechazo **antes de encolar** con causa (fila en `rechazos_orquestador.csv`);
- válidas → el brazo va a la zona/pose correcta.

Evidencia del registro: `transcripciones.csv` (audio, texto, método, tiempos).

---

## 7. Parte C — Desglose de tiempos

### 7.1 Instantes que el código ya registra
- `t0` fin de habla / apertura del archivo, `t1` audio listo, `t2` transcripción recibida,
  `t3` decisión recibida → **columnas de `transcripciones.csv`**.
- `t4` goal aceptado por el broker, `t5` fin de ejecución y `wait_time_s` (espera en cola)
  → **columnas de `tiempos_acciones.csv`** (las escribe el orquestador).

### 7.2 Arma `etapas.csv` (para la figura)
Calcula la mediana de cada etapa sobre las 5 órdenes y escribe:
```csv
etapa,mediana_s
Captura de audio,0.05
Transcripcion en la nube,0.90
Decision del modelo,0.42
Espera en la cola,1.10
Percepcion,0.08
Cinematica inversa,0.12
Planificacion,0.20
```
- Captura = `t1 - t0`; Transcripción = `t2 - t1`; Decisión = `t3 - t2`;
  Cola = `wait_time_s`; Total voz→movimiento = `t5 - t0`.
- Percepción / IK / planificación son marcas del orquestador (placeholder mientras no haya
  cámara; decláralo).

```bash
python3 herramientas/graficar_tiempos.py etapas.csv --salida desglose_tiempos.png
```
Salida: tabla por etapa (ms y %) + `desglose_tiempos.png`.

### 7.3 Las dos preguntas (respóndelas con TUS números)
1. **¿Etapa dominante?** la de mayor mediana (suele ser transcripción en la nube o espera en cola).
2. **¿Cómo reducir a la mitad el total y qué se pierde?** Atacar la transcripción (modelo de voz
   local) pierde calidad ASR multilingüe y suma mantenimiento; atacar la cola (menor `tau`,
   prioridades agresivas) mejora lo urgente pero empeora inanición/equidad de las prioridades bajas.

---

## 8. Demo SIN internet (entregable obligatorio)

```bash
# 1) Corta SOLO internet, dejando viva la LAN con la PC de LAYA:
sudo iptables -A OUTPUT -d 0.0.0.0/0 -j DROP
sudo iptables -I OUTPUT -d <IP_PC_LAYA> -j ACCEPT      # la PC local sigue accesible
# (NO apagues eth0/wlan0: perderías también LAYA)

# 2) Comprueba
ping -c 2 8.8.8.8                            # debe FALLAR
curl -s http://<IP_PC_LAYA>:8000/health      # debe responder (LAN viva)

# 3) Corre la cadena de voz
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_01.wav
#   → Gemini falla por DNS/timeout → loguea y pasa a MODO TEXTO POR TECLADO
# 4) Escribes la orden a mano → decisión (LAYA local) → brazo se mueve

# 5) Al terminar, revierte el iptables
sudo iptables -D OUTPUT -d 0.0.0.0/0 -j DROP
```

Graba ese video: demuestra que **la decisión y el movimiento no dependen de internet**.

---

## 9. Entregables y checklist

| Entregable | Fuente |
|---|---|
| Código del nodo | `src/arm_broker/arm_broker/transcriptor_voz.py`, `voz_google.py`, `orquestador.py` + `setup.py` |
| Audios + transcripción | `orden_0X.wav` + `transcripciones.csv` |
| Tabla de las 5 órdenes | `ordenes_demo.csv` |
| Desglose de tiempos + figura | `etapas.csv` + `desglose_tiempos.png` |
| Demo sin internet | video (modo texto) |
| Rechazos con causa | `rechazos_orquestador.csv` |

- [ ] Clave **solo** en `GOOGLE_API_KEY` (rotar la que está en el repo).
- [ ] `probar_transcripcion.py` OK antes de tocar el nodo (modelo `gemini-2.5-flash`).
- [ ] `voz_google.py`, `transcriptor_voz.py`, `orquestador.py` copiados + entry points + `colcon build` OK.
- [ ] Cadena arriba: driver + broker + `interprete_ordenes` + `orquestador` + `transcriptor_voz`.
- [ ] `verificar_publicadores.py` = exactamente 1 publicador `arm_broker`.
- [ ] 5 órdenes habladas (con objeto inexistente y no permitida) → `ordenes_demo.csv`.
- [ ] `transcripciones.csv` + `tiempos_acciones.csv` → `etapas.csv` → figura.
- [ ] Respuestas numéricas a las dos preguntas de §7.3.
- [ ] Video de la demo con internet desconectado (modo texto).

---

## 10. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta GOOGLE_API_KEY` | no exportaste la variable en la sesión | `export GOOGLE_API_KEY=...` en la misma terminal |
| Gemini `404 model not found` | nombre de modelo | usa `gemini-2.5-flash` o lista modelos (§3) |
| Siempre cae a MODO TEXTO | sin internet o timeout bajo | sube `-p timeout_transcripcion_s:=8.0`; revisa `ping 8.8.8.8` |
| `el broker no aparece` | broker no está corriendo | arranca `ros2 run arm_broker broker ...` |
| Todo se rechaza | `permitido=False` o `objeto=desconocido` | normal para las órdenes de prueba; revisa `rechazos_orquestador.csv` |
| Poses raras | `mapa_poses` es placeholder | ajusta a poses seguras de tu kit |
