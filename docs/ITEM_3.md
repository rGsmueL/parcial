# ÍTEM 3 — Pregunta 3 (6 pts): de la voz al movimiento

> El operador **habla** y el sistema completo funciona de extremo a extremo:
> **voz → texto → decisión (P1) → cola del broker (P2) → brazo**. No se
> construye nada nuevo aguas abajo: solo se **antepone** la transcripción.
> Aquí está el paso a paso, comando por comando y por dispositivo, incluida la
> integración con **Google AI Studio** y el **modo texto por teclado** cuando
> no hay internet.
>
> Enunciado: `Parcial_Gran_Reto_JetCobot.docx`. Lo de aguas abajo:
> `ITEM_1.md` (servicio) e `ITEM_2.md` (cola y brazo).

---

## 1. Qué pide el enunciado (resumen)

### Parte A — Transcripción
- Nodo **`transcriptor_voz`**: toma audio (micrófono o archivo) y obtiene la
  transcripción **en español** consultando a **Google AI Studio**; el texto se
  entrega al servicio `/interpretar_orden` de la Pregunta 1.
- La **clave de la API** se lee de **variable de entorno**: nunca en el
  código ni en el repositorio.
- **Su propio tiempo límite**: si la transcripción no llega a tiempo o no hay
  internet → **modo texto por teclado** y se **informa**. El brazo nunca queda
  esperando.
- **Registrar** la transcripción junto con el audio original.

### Parte B — La cadena completa
- Demo con **5 órdenes habladas** por el docente. Entre ellas habrá:
  una con **objeto que no está sobre la mesa** y una **no permitida**.
- Tabla por orden: *lo que se dijo → lo que transcribió → la decisión del
  modelo → lo que hizo el brazo*. Cuenta como correcta solo si el resultado
  final es el esperado, **incluido el rechazo** cuando corresponde.

### Parte C — Dónde se va el tiempo
- Medir desde que el operador **termina de hablar** hasta que el brazo
  **inicia el movimiento**, descomponiéndolo: captura de audio,
  transcripción en la nube, decisión del modelo, espera en la cola,
  percepción, cinemática inversa y planificación.
- **Tabla + figura**, con sus propios números: ¿cuál es la etapa dominante?
  Si hay que reducir a la mitad el tiempo voz→movimiento, ¿sobre qué etapa se
  trabaja y qué se deja de obtener a cambio?

### Entregables
Código del nodo · archivos de audio con su transcripción · tabla de las 5
órdenes · desglose de tiempos con su figura · demo del **modo texto funcionando
con internet desconectado**.

---

## 2. Arquitectura de la P3 y qué corre en qué dispositivo

```
   OPERADOR (habla)
        │ audio .wav (micrófono o archivo)
        ▼
┌─────────────────────────────── JETSON (grafo ROS 2) ───────────────────────────────┐
│  transcriptor_voz  ──HTTPS+clave──► Google AI Studio (nube, internet)              │
│      │  timeout / sin internet                                                     │
│      ├─► texto ──► /interpretar_orden (interprete_ordenes, P1) ──► decisión        │
│      └─► MODO TEXTO: el operador escribe por teclado ─────────────┐                │
│                                                                    ▼                │
│                              orquestador (P2): permitido? prioridad? pose           │
│                                        │ goal move_arm                              │
│                                        ▼                                             │
│                              broker (worker único) ──► /joint_states ──► driver      │
└────────────────────────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ HTTP /v1/systemone (decisión)
                     ┌─────────────┴──────────────┐
                     │  TU PC WINDOWS: laya-serve │  ← LAYA local, no depende de internet
                     └────────────────────────────┘
```

| Dispositivo | Qué corre aquí en la P3 |
|---|---|
| **Tu PC Windows** | `laya-serve` (decisión) — sigue funcionando **sin internet** |
| **Jetson** | `sync_plan_nx`, `broker`, `interprete_ordenes`, **`transcriptor_voz` (nuevo)**, orquestador, grabación de bags |
| **Internet (nube)** | **Google AI Studio**: transcripción del audio. Descarga inicial de checkpoints de LAYA (ya hecha) |
| **PC del operador/evaluador** | grabar el audio de las órdenes (si el micrófono está en otra máquina) y el video final |

Dato clave del enunciado que confirma el diseño: *"la transcripción depende de
internet; la decisión y el movimiento, no"* — por eso LAYA corre **local** en
tu PC y solo la transcripción sale a la nube.

---

## 3. Google AI Studio paso a paso (Parte A, nube)

### 3.1 Crear la clave (una vez)
1. Entra a <https://aistudio.google.com/apikey> con la cuenta del equipo.
2. **Create API key** → copia la clave (empieza tipo `AIza…`).
3. Ver modelos disponibles (opcional):
   ```powershell
   curl.exe -s "https://generativelanguage.googleapis.com/v1beta/models?key=AIzaTU_CLAVE" | findstr name
   ```
   Se usa un modelo multimodal rápido, p. ej. `gemini-2.5-flash` (si no
   aparece, usa el primero de la lista que soporte audio).

> **Nunca** pegues la clave en un `.py` ni la subas al repo. Solo variable de
> entorno. El docx descuenta puntos si está publicada.

### 3.2 Probar la transcripción con curl ANTES de escribir el nodo

Prepara un audio de prueba (en tu PC): graba 3 s con cualquier app y guárdalo
como `orden.wav` (PCM 16 kHz mono sirve bien; `mp3`/`m4a` también los toma
Gemini). Conviértelo a base64:

```powershell
# PowerShell, en la carpeta del audio
$wav  = [Convert]::ToBase64String([IO.File]::ReadAllBytes("orden.wav"))
$body = @{
  contents = @(@{ parts = @(
      @{ text = "Transcribe exactamente lo que se dice en español. Solo la transcripción, sin comentarios." },
      @{ inline_data = @{ mime_type = "audio/wav"; data = $wav } }
  )})
} | ConvertTo-Json -Depth 10

curl.exe -s -X POST `
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" `
  -H "content-type: application/json" `
  -H "x-goog-api-key: AIzaTU_CLAVE" `
  -d $body
```

La respuesta viene en `candidates[0].content.parts[0].text` — eso es la
transcripción. Si el modelo devuelve también comentarios, refuerza el prompt
(*"solo la transcripción"*).

### 3.3 Desde la Jetson (sin `curl` de PowerShell)

```bash
python3 - <<'EOF'
import base64, json, os, requests
clave = os.environ["GOOGLE_API_KEY"]
audio = base64.b64encode(open("orden.wav", "rb").read()).decode()
r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    headers={"x-goog-api-key": clave, "content-type": "application/json"},
    json={"contents": [{"parts": [
        {"text": "Transcribe exactamente lo que se dice en español. Solo la transcripción."},
        {"inline_data": {"mime_type": "audio/wav", "data": audio}}]}]},
    timeout=15)
print(r.json()["candidates"][0]["content"]["parts"][0]["text"])
EOF
```

---

## 4. El nodo `transcriptor_voz` (Parte A, código nuevo)

Es el **único nodo nuevo** de esta pregunta. Va dentro del paquete existente
`src/arm_broker/arm_broker/transcriptor_voz.py`, con su entry point en
`setup.py`:

```python
# src/arm_broker/setup.py → console_scripts
'transcriptor_voz = arm_broker.transcriptor_voz:main',
```

### 4.1 Qué debe hacer (especificación mínima)

```
parámetros del nodo:
  fuerte:        'archivo' | 'microfono'        (default archivo)
  ruta_audio:    ruta a un .wav                 (modo archivo)
  google_model:  'gemini-2.5-flash'
  timeout_transcripcion_s: 5.0                  ← SU tiempo límite
  modo_texto_tras_fallo: true                   ← cae a teclado si falla

arranque:
  1. leer GOOGLE_API_KEY de os.environ  (si falta, avisar y arrancar igual en modo texto)
  2. crear cliente del servicio /interpretar_orden (ya existe en la P1)

cada orden:
  a. t0 = fin de habla (o apertura del archivo)
  b. capturar audio (arecord / leer .wav)
  c. t1 = audio listo  →  POST a Google AI Studio (con timeout)
     ├─ OK  → texto = candidates[0].content.parts[0].text
     └─ timeout/error/sin internet → avisar en el log
                    → MODO TEXTO: pedir por teclado input('Escriba la orden: ')
  d. t2 = texto listo  →  guarda (audio, transcripción, t1, t2) en transcripciones.log
  e. llamar a /interpretar_orden con ese texto  →  decisión   (t3)
  f. entregar la decisión al orquestador (P2): goal con prioridad del modelo
  g. con el Result del goal: espera en cola (wait_time_s) y tiempos (t4…)
```

### 4.2 Captura de audio

**Opción 1 — archivo (la más reproducible para la evidencia):** el evaluador
dicta, se guarda el `.wav` y se lo pasa al nodo:
```bash
# Grabar en la Jetson (ALSA, 16 kHz mono, 8 segundos):
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav
# (ajusta -D plughw:1,0 al micrófono: lista con arecord -l)
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_01.wav
```

**Opción 2 — micrófono en vivo:** dentro del nodo, capturar con
`sounddevice`/`pyaudio` hasta detectar silencio, o grabar con `arecord` en un
hilo y pasar la ruta. Para el examen, lo robusto es **grabar y reproducir el
archivo** (además deja la evidencia `audio + transcripción`).

**Opción 3 — grabar desde la PC del operador** y copiar el `.wav` a la Jetson
(`scp`), si el micrófono cómodo está ahí.

### 4.3 Modo texto por teclado (el fallback obligatorio)

Cuando `timeout_transcripcion_s` expira o no hay internet, el nodo **no
falla**: imprime algo visible como
```
⚠️ [TRANSCRIPTOR] sin respuesta de Google AI Studio en 5.0 s → MODO TEXTO POR TECLADO
   (el brazo NO queda esperando; escriba la orden a continuación)
```
y lee `input()`. Ese texto sigue el mismo camino (`/interpretar_orden` →
orquestador → broker). **Eso es lo que hay que mostrar con internet
desconectado** en el video del entregable.

### 4.4 Registro audio + transcripción (requisito)

Un CSV/LOG, por ejemplo `transcripciones.csv`:
`t_unix, ruta_audio, texto_transcrito, metodo (google|teclado), tiempo_transcripcion_s, tiempo_decision_s`
— es la mitad de la evidencia de la Parte B.

### 4.5 Build y arranque

```bash
cd ~/rb2_ws
colcon build --packages-select arm_broker --symlink-install
source install/setup.bash

export GOOGLE_API_KEY="AIzaTU_CLAVE"       # SOLO variable de entorno
ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p timeout_transcripcion_s:=5.0 -p google_model:=gemini-2.5-flash
```

---

## 5. Parte B — La cadena completa con 5 órdenes habladas

### 5.1 Arriba de todo (antes de la demo)
1. `laya-serve` en tu PC (`ITEM_1.md` §4.3).
2. En la Jetson: `sync_plan_nx` → `broker` (`politica:=prioridad`,
   `tau:=12.0`) → `interprete_ordenes` (`laya_url:=http://<IP_PC>:8000`) →
   orquestador (P2) → `transcriptor_voz`.
3. Bag + verificación de publicador único (`ITEM_2.md` §Fase B-D).

### 5.2 Las 5 órdenes
El docente dicta 5 órdenes en vivo; **entre ellas**: una con **objeto que no
está en la mesa** y una **no permitida**. Para cada una:

| # | Se dijo (audio) | Transcribió | Decisión (acción/objeto/color/prioridad/permitido) | Rechazo/encolado | Qué hizo el brazo | ¿Correcto? |
|---|---|---|---|---|---|---|
| 1 | `orden_01.wav` | … | … | … | … | sí/no |
| 2 | … | … | … | … | … | … |
| … (5) | | | | | | |

Criterio de acierto (del enunciado): resultado **final** esperado, **incluido
el rechazo** cuando corresponde rechazar:
- objeto inexistente → la decisión lo marca (`objeto=desconocido` o
  `permitido=False`) y **no se mueve**;
- orden no permitida → rechazo **antes de encolarse** con causa
  (`ITEM_2.md` §4.1);
- órdenes válidas → el brazo deposita el objeto correcto en la zona correcta.

Grabar: el bag, `transcripciones.csv` y el video.

---

## 6. Parte C — Desglose de tiempos (voz → movimiento)

### 6.1 Qué medir (instantes)
`t0` fin de habla · `t1` audio capturado · `t2` transcripción recibida ·
`t3` decisión recibida (`/interpretar_orden` respondió) · `t4` goal aceptado
por el broker · `t5` **inicio real del movimiento** (primer
`/joint_states` de ejecución, o `t4 + wait_time_s`).

Las etapas se obtienen por diferencia:

| Etapa | Cómo sale |
|---|---|
| Captura de audio | `t1 − t0` (si el archivo ya existe: tiempo de escritura/lectura) |
| Transcripción en la nube | `t2 − t1` |
| Decisión del modelo (incluye red a LAYA) | `t3 − t2` (parte red/cómputo la da `tiempo_red_s`/`tiempo_computo_s` del srv) |
| Espera en la cola del broker | `wait_time_s` del `MoveArm.Result` (= `t5 − t4`) |
| Percepción (cámara) | marca de tiempo propia en el orquestador |
| Cinemática inversa | marca de tiempo propia |
| Planificación (MoveIt2) | marca de tiempo propia |
| **Total voz → movimiento** | `t5 − t0` |

Instrumentación mínima: el orquestador/transcriptor loguea `t0..t4` con
`time.time()`; `t3` también puede salir de los metadatos `tiempo_total_s` del
servicio; la percepción/IK/planificación son marcas dentro del orquestador.

### 6.2 Tabla y figura
Tabla: `etapa | mediana (ms) | % del total` sobre las 5 órdenes.
Figura: barras apiladas (o gantt) del porcentaje por etapa — un `.png` hecho
con cualquier herramienta (a mano en la lámina, o `matplotlib` desde un CSV
`etapa,mediana_s`).

### 6.3 Las dos preguntas que hay que responder con números
1. **¿Cuál es la etapa dominante?** (la de mayor mediana; en la práctica
   casi siempre la **transcripción en la nube** o la **espera en la cola**,
   según carga — pero responde con **tus** medidos).
2. **Si hay que reducir a la mitad el tiempo voz→movimiento, ¿sobre qué etapa
   trabajas y qué dejas de obtener?** Ejemplo de respuesta esperada: atacar la
   transcripción (dejar de ir a la nube: modelo local de voz) mejora mucho el
   total, pero **pierdes** la calidad del ASR multilingüe de Google y
   añades mantenimiento de un modelo local; atacar la cola (prioridades más
   agresivas, `tau` menor) mejora la espera de las órdenes urgentes **pero
   empeora** la equidad/inanición de las prioridades bajas. La respuesta
   correcta es la que salga de **tus números**, con ese trade-off explicitado.

---

## 7. Demo sin internet (entregable obligatorio)

```bash
# 1) Corta SOLO el internet, dejando viva la red local con la PC de LAYA:
#    - desenchufa el cable WAN del router / apaga el módem, o
#    - en la Jetson bloquea la salida a internet sin tocar la LAN:
#        sudo iptables -A OUTPUT -d 0.0.0.0/0 -j DROP    # (revierte con -D tras la prueba)
#        sudo iptables -I OUTPUT -d <IP_PC_LAYA> -j ACCEPT   # la PC local sigue accesible
#    ⚠️ NO apagues la interfaz completa (eth0/wlan0): perderías también
#       la conexión a LAYA, que está en la red local de tu PC.
# 2) LAYA sigue arriba en tu PC (red local, no necesita internet)
# 3) Comprueba que efectivamente no hay internet en la Jetson:
        ping -c 2 8.8.8.8          # debe fallar
        curl -s http://<IP_PC_LAYA>:8000/health   # debe responder (LAN viva)
# 4) Corre la cadena:
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_01.wav
#    → DNS/timeout de Google AI Studio falla → loguea y pasa a MODO TEXTO POR TECLADO
# 5) Se escribe la orden a mano y el brazo la ejecuta normalmente
```
Graba ese video: demuestra que **decisión y movimiento no dependen de
internet**, solo la transcripción.

---

## 8. Entregables de la Pregunta 3

| Entregable | Fuente |
|---|---|
| Código del nodo | `src/arm_broker/arm_broker/transcriptor_voz.py` + entry point en `setup.py` |
| Audios con su transcripción | `orden_0X.wav` + `transcripciones.csv` |
| Tabla de las 5 órdenes | §5.2 (llenada con la demo real) |
| Desglose de tiempos + figura | §6.1–6.2 |
| Demo modo texto sin internet | video de §7 |
| (complemento) video de la cadena | lo mismo que la P2, ahora hablada |

---

## 9. Checklist de la Pregunta 3

1. [ ] Clave de Google AI Studio creada y **solo** en `GOOGLE_API_KEY`.
2. [ ] Prueba de transcripción con `curl`/PowerShell **antes** del nodo (§3.2).
3. [ ] `transcriptor_voz.py` implementado con `timeout_transcripcion_s`,
      registro audio+transcripción y fallback a teclado (§4).
4. [ ] Entry point agregado en `setup.py` y `colcon build` OK (§4.5).
5. [ ] Cadena completa arriba: LAYA (tu PC) + broker + intérprete + orquestador (§5.1).
6. [ ] 5 órdenes habladas con su tabla (incluyen objeto inexistente y no permitida) (§5.2).
7. [ ] Instrumentación de `t0..t5` + percepción/IK/planificación; tabla y figura (§6).
8. [ ] Respuestas numéricas a las dos preguntas de §6.3.
9. [ ] Demo con internet desconectado en modo texto, en video (§7).
