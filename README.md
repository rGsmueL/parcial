# Reto Brazo 2 – Ítems 2 y 3

Broker ROS 2 para serializar el acceso de varios clientes al JetCobot. Ejecuta los goals **uno a uno** (worker único + grupo `MutuallyExclusive`), valida con cinemática directa (`fk.py`) y compara dos políticas de cola.

## 1. Arquitectura

- **ActionServer**: `arm_broker_interfaces.action.MoveArm` (goal único por solicitud).
- **Worker único**: grupo de callbacks mutuamente excluyente. Garantiza **exclusión mutua** por construcción (nunca hay dos goals en ejecución simultánea).
- **Cola única**: lista de pedidos aceptados, protegida con `threading.Lock`.
- **Publicación de estado articular**: **exactamente un publicador** del tópico `/joint_states`, con nombre de nodo `arm_broker`. Esto es requisito eliminatorio (ver `analisis/verificar_publicadores.py`).
- **Telemetría**: `QueueState.msg` (tamaño de cola, ejecutando, completados, rechazados y política activa).
- **Driver esperado en Jetson**: `sync_plan_nx` (control de trayectoria/articulaciones). El broker publica `/joint_states` con la secuencia de referencia durante la ejecución.

## 2. Políticas de cola

### FIFO (línea base)
- Atiende en orden estricto de llegada: `min(t_llegada)`.
- Ignora prioridad. Sirve para aislar el efecto del envejecimiento.

### Prioridad con envejecimiento (segunda política)
Se implementa en `SegundaPolitica` (archivo `src/arm_broker/arm_broker/politicas.py`):

```text
puntuación = priority + espera_s / tau
```

- **`tau_envejecimiento_s = 12.0`** (inyectado desde el broker). Valor por defecto en código `8.0`, pero **obligatoriamente 12.0** para las mediciones.
- **Desempate**: ante empate de puntuación, sale el pedido **más antiguo** (`-t_llegada`).
- **Efecto**: prioridades altas se atienden antes, pero un pedido de prioridad baja que envejece lo suficiente termina siendo atendido (acota la inanición).
- **Contrato con la política**: `siguiente(pendientes)` devuelve el **índice** del candidato (igual que usa el broker). `espera_s` se calcula con `t_inicio_ejec` si ya empezó, o con el instante actual en caso contrario.

## 3. Validación de goals (admisión)

El broker rechaza un goal **antes** de encolarlo, en este orden (`broker.py`):

1. **Valores finitos**: todos los `q_i` deben ser `float` finitos.
2. **Límites articulares** (`fk.JOINT_LIMITS`): cada articulación dentro de `[min,max]`.
3. **Workspace** (`fk.dentro_del_workspace`): posición cartésiana válida según el filtro del kit (se exige `z >= 0` y alcance 3D entre ~80 mm y ~480 mm).
4. **Paso articular** (`fk.paso_articular(q_actual, q)`): salto entre configuración actual y objetivo **<= `paso_max_rad`**. Para las corridas comparativas se usa **`paso_max_rad := 1.6`** (justificado por los 4 saltos consecutivos > 1.2 en `carga.csv`: máximo 1.454 rad).
5. **Cola llena**: si `len(pendientes) >= cola_max` → rechazo `cola_llena`.

Durante la ejecución también puede producirse `paso_al_ejecutar` si la pose de referencia cambió mientras el pedido esperaba (revalidación en `desencolar`).

Causas registradas: `limite`, `workspace`, `paso`, `cola_llena`, `paso_al_ejecutar`.

## 4. Traza de carga

- Archivo: `carga.csv` (40 poses, **semilla 7**). Generado con `herramientas/generar_carga.py`.
- Se utiliza para las corridas FIFO y prioridad con **misma traza e idéntico orden temporal** (requisito de reproducibilidad).
- Modo recomendado para comparar políticas sin introducir asimetrías: **secuencial** (`duracion_movimiento_s = 1.5 s`, `pausa_s = 2.0 s`).

## 5. Verificación y herramientas

- `analisis/verificar_publicadores.py`: comprueba **exactamente 1** nodo publicando `/joint_states` llamado `arm_broker`. Fallo → medición inválida.
- `herramientas/validar_rechazos.py`: valida causas de rechazo sobre poses conocidas (`limite`, `workspace`, `paso`) con `paso_max_rad` 1.2 y 1.6.
- `herramientas/simular_corrida.py`: simulador por eventos (usa `politicas.py` tal cual). Genera `prediccion.md` **antes de medir**.
- `analisis/exportar_csv.py`: exporta rosbags a CSV.
- `analisis/metricas.py`: calcula métricas y genera gráfica comparativa (esperas, p95, equidad Jain, inanición por prioridad).

## 6. Configuración de red/equipo

- `config/equipo.env`: `ROS_DOMAIN_ID=47` (Grupo 5). `JETSON` debe actualizarse con la **IP real del Jetson** al conectar (se deja `172.51.9.5` como ejemplo marcado).
- `conectar_reto.sh`: prepara entorno ROS 2 y Discovery Server para comunicación con Jetson.

## 7. Nota sobre tabla DH

`fk.py` utiliza parámetros DH coherentes con el andamiaje del kit (`d5=75.55`, `d6=50`). `mi_info.txt` declara `d5=75.05`, `d6=60`. Esta discrepancia **no se resuelve por código**: debe **verificarse físicamente** en el Jetson (comparar con `get_coords()` / poses de referencia). La predicción y las validaciones usan `fk.py` tal como corre el broker.

## 8. Predicción previa a medición

La predicción del **p95** se genera y documenta **antes de las mediciones reales** (`prediccion.md`, reproducible con `simular_corrida.py --ambos --tau 12.0 --paso-max 1.6 --modo secuencial`). El contraste entre predicho y medido se registra en `DISENO_PREVIO.md` (sección 6).
