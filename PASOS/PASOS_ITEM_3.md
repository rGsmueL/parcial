# PASOS ITEM 3 — voz a texto (transcripción) + modo texto de respaldo

Guía completa desde `git clone`: grabar el audio, transcribir con Google, encadenar con la
decisión (P1) y el orquestador (P2), y la demo **sin internet**.

---

## 0. Qué hace este ítem

Cadena: `audio .wav → Google AI Studio (gemini-2.5-flash) → texto → /interpretar_orden (P1) →
/orden_decidida → orquestador_item2 → broker → brazo`.

- **Por audio**: `transcriptor_voz` sube el `.wav` a Gemini con `GOOGLE_API_KEY` y publica la
  decisión en `/orden_decidida`.
- **Por texto**: si no hay internet / clave / timeout, el nodo falla a `input()` por teclado
  (modo texto de respaldo).
- La decisión la sigue tomando **LAYA local** (no depende de internet).

---

## 1. Prerrequisitos

- ROS 2 Humble en la Jetson; LAYA en tu PC Windows.
- Internet para Google AI Studio + una clave `GOOGLE_API_KEY`.
- Micrófono e `arecord` (`alsa-utils`) en la Raspberry/Jetson que graba.

Dependencias:

```bash
pip3 install requests --break-system-packages
pip3 install matplotlib --break-system-packages   # solo para graficar_tiempos.py
sudo apt install alsa-utils                       # provee arecord
```

> No se usan `SpeechRecognition`/`pyaudio`: el nodo lee un `.wav` y habla HTTP con Gemini.

---

## 2. Desde `git clone`, en la Jetson

```bash
git clone https://github.com/rGsmueL/parcial.git ~/rb2_ws
cd ~/rb2_ws

source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID + 1))   # = 43 (5 máquinas iguales)
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
ros2 daemon stop; ros2 daemon start

pip3 install requests --break-system-packages

colcon build --packages-select arm_broker_interfaces arm_broker --symlink-install
source install/setup.bash
```

- Entry points ya registrados: `transcriptor_voz` y `orquestador_item2` (el `orquestador`
  mínimo del item3 **no está registrado** → usa `orquestador_item2`).
- **Modelo**: los audios del repo no existen; el default del código (`voz_google.py`) es
  `gemini-3.8-flash`, pero la guía usa `gemini-2.5-flash`. **Verifica el nombre real**:
  ```bash
  curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY" | head
  ```

---

## 3. Grabar y transferir el audio (en la Raspberry)

```bash
arecord -l                                                # lista dispositivos, anota plughw:X,Y
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 8 orden_01.wav

# Copiar a la raíz del workspace donde se correrá el nodo (la ruta es relativa al CWD)
scp orden_01.wav usuario@<jetson-o-raspberry>:~/rb2_ws/
```

> Los `.wav` **no están en el repo**: se generan en el examen. El nodo escribe
> `transcripciones.csv` en el directorio desde donde se lanza (corre desde `~/rb2_ws`).

---

## 4. Probar la transcripción SIN ROS (rápido)

```bash
cd ~/rb2_ws
export GOOGLE_API_KEY="TU_CLAVE_DE_GOOGLE_AI_STUDIO"
python3 herramientas/probar_transcripcion.py orden_01.wav gemini-2.5-flash
# → Transcripción (... ms): 'agarra el cubo rojo'
```

Si falta la clave o Gemini falla, probar el **modo texto** del nodo directamente (sección 6).

---

## 5. Arranque por terminal — VÍA AUDIO

**PC Windows**: `laya-serve` (ver `PASOS_ITEM_1.md` §3).

**Jetson, terminal por terminal:**

```bash
# T0 — driver
ros2 run jetcobot_driver sync_plan_nx

# T1 — broker
cd ~/rb2_ws && source install/setup.bash; export ROS_DOMAIN_ID=42; export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID+1)); export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_DISCOVERY_SERVER="172.51.1.28:11811"; ros2 daemon stop; ros2 daemon start
ros2 run arm_broker broker --ros-args \
  -p politica:=prioridad -p tau_envejecimiento_s:=12.0 \
  -p paso_max_rad:=1.6 -p duracion_movimiento_s:=5.0 -p pasos_interpolacion:=1

# T2 — intérprete P1
ros2 run arm_broker interprete_ordenes --ros-args -p laya_url:=http://<IP_PC>:8000

# T3 — orquestador definitivo (Item 2)
ros2 run arm_broker orquestador_item2 --ros-args \
  -p escala_prioridad:=85 -p paso_max_rad:=1.6 -p usar_camara:=true \
  -p gripper_action:=gripper_command

# T4 — transcriptor de voz (desde la raíz del workspace donde está el .wav)
cd ~/rb2_ws && source install/setup.bash
export ROS_DOMAIN_ID=42; export ROS_DOMAIN_ID=$((ROS_DOMAIN_ID+1)); export RMW_IMPLEMENTATION=rmw_fastrtps_cpp; export ROS_DISCOVERY_SERVER="172.51.1.28:11811"
export GOOGLE_API_KEY="TU_CLAVE_DE_GOOGLE_AI_STUDIO"

ros2 run arm_broker transcriptor_voz --ros-args \
  -p fuente:=archivo -p ruta_audio:=orden_01.wav \
  -p google_model:=gemini-2.5-flash \
  -p timeout_transcripcion_s:=5.0 -p n_ordenes:=1 \
  -p topico_decision:=orden_decidida
```

Repite por cada audio:

```bash
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_02.wav -p n_ordenes:=1
```

---

## 6. MODO TEXTO (respaldo y entregable obligatorio)

1. **Forzando** el teclado dentro del nodo:

```bash
ros2 run arm_broker transcriptor_voz --ros-args -p fuente:=teclado -p n_ordenes:=5
```

2. **Alternativa** (vía Item 2): `cliente_texto` por terminal:

```bash
ros2 run arm_broker cliente_texto --ros-args -r __node:=cliente_<nombre> \
  -p client_id:=<nombre> -p n_ordenes:=0
```

3. **Fallback automático**: si falla Gemini (sin `GOOGLE_API_KEY`, sin internet, timeout), el
   nodo imprime el aviso y lee `input()` por teclado.

---

## 7. Demo SIN internet (obligatoria)

Corta **solo** internet (WAN), dejando viva la LAN con la PC de LAYA:

```bash
# 1) Bloquear salida WAN, permitir la IP de la PC de LAYA
sudo iptables -A OUTPUT -d 0.0.0.0/0 -j DROP
sudo iptables -I OUTPUT -d <IP_PC_LAYA> -j ACCEPT     # no apagues eth0/wlan0

# 2) Comprobar: internet si falla, LAYA si responde
ping -c 2 8.8.8.8
curl -s http://<IP_PC_LAYA>:8000/health

# 3) Correr la cadena de voz: Gemini falla → cae a MODO TEXTO
ros2 run arm_broker transcriptor_voz --ros-args -p ruta_audio:=orden_01.wav

# 4) Escribir la orden a mano → decisión (LAYA local) → brazo

# 5) Restaurar internet
sudo iptables -D OUTPUT -d 0.0.0.0/0 -j DROP
```

---

## 8. Evidencias / métricas

- `transcripciones.csv` — una fila por audio: `t_unix,ruta_audio,texto_transcrito,metodo,tiempo_transcripcion_s,tiempo_decision_s,t0,t1,t2,t3`.
- Instantes: `t0` fin de habla, `t1` audio capturado, `t2` transcripción, `t3` decisión,
  `t4` goal aceptado, `t5` inicio real del movimiento.
- `tiempos_acciones.csv` (orquestador) — `wait_time_s`, `exec_time_s`, `exito`.
- `rechazos_orquestador.csv` — rechazos con causa.
- Tabla de 5 órdenes (`ordenes_demo.csv`, plantilla en `docs/item3/plantilla_ordenes.csv`).
- Etapas y gráfico:
  ```bash
  # arma el CSV etapa,mediana_s y luego:
  python3 herramientas/graficar_tiempos.py etapas.csv --salida desglose_tiempos.png
  ```
- Bag de la cadena: `ros2 bag record -o demo_p3 /arm/queue_state /joint_states`.
- Video del modo **texto sin internet**.

Respuestas numéricas: (1) etapa dominante = mayor mediana; (2) cómo reducir el total a la
mitad y qué se pierde (ataque la transcripción → pierdes el ASR multilingüe; ataca la cola →
mejoras urgencia pero empeoras equidad/inanición).

---

## 9. Problemas comunes

- **Falta `GOOGLE_API_KEY`** → el nodo avisa y usa teclado (no es error fatal).
- **Modelo `404`** → `gemini-3.8-flash` no existe; usa `gemini-2.5-flash` (o el que liste Gemini).
- **Siempre cae a texto** → sin internet o timeout bajo: sube `-p timeout_transcripcion_s:=8.0`.
- **`probar_transcripcion.py` debe vivir en `herramientas/`** (sube a `src/arm_broker` por ruta relativa).
- **CSV en el CWD** → lanza el nodo desde `~/rb2_ws`.
- **Aislar internet mal** → si apagas `eth0/wlan0` pierdes también LAYA; usa `iptables` con `ACCEPT` a la IP de tu PC.
- **Publicador único** → `python3 analisis/verificar_publicadores.py --salida evidencia/publicadores.txt`.

---

## 10. Checklist de entrega

- [ ] `probar_transcripcion.py orden_01.wav gemini-2.5-flash` devuelve la frase.
- [ ] Cadena por audio funciona (5 órdenes, incluye un rechazo no_permitida).
- [ ] Demo sin internet → modo texto → brazo se mueve.
- [ ] `transcripciones.csv` + tabla `ordenes_demo.csv`.
- [ ] `etapas.csv` + `desglose_tiempos.png` + respuestas a las 2 preguntas.
- [ ] `rechazos_orquestador.csv`, bag y video.