# Terminales: bolsa y métrica

Todo se ejecuta **dentro de esta carpeta** (`RETO2`). Ajustá el `cd` a la ruta
real donde clone el repo (`cd ~/RETO2`).

---

## Terminal 1 — grabar la bolsa

```bash
cd ~/RETO2
set -a; source config/equipo.env; set -a
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="$JETSON:11811"
source /opt/ros/humble/setup.bash
ros2 daemon stop; ros2 daemon start
```

Verificar que se vean los tópicos antes de grabar:

```bash
python3 analisis/verificar_publicadores.py
```

Grabar (un bag por política, el nombre de la carpeta es el rótulo de la métrica):

```bash
ros2 bag record -o fifo /arm/queue_state /joint_states
ros2 bag record -o prioridad /arm/queue_state /joint_states
```

Con `Ctrl+C` se detiene la grabación. Los bags quedan en `./fifo/` y `./prioridad/`.

---

## Terminal 2 — exportar el bag y calcular la métrica

```bash
cd ~/RETO2
source /opt/ros/humble/setup.bash
```

Exportar cada bag a CSV (va dentro de la misma carpeta de la política):

```bash
python3 analisis/exportar_csv.py fifo/ --salida fifo/
python3 analisis/exportar_csv.py prioridad/ --salida prioridad/
```

Calcular métricas y figura comparativa:

```bash
python3 analisis/metricas.py fifo/queue_state.csv prioridad/queue_state.csv \
  --salida comparacion_politicas.png
```

La figura queda en `./comparacion_politicas.png`.

---

## Notas

- `metricas.py` recibe los CSV **posicionales** y usa `--salida`. La línea 49 de
  `PASOS.txt` (`--fifo/--prio/--outdir`) está desactualizada.
- Cada CSV hay que exportarlo **dentro** de la carpeta de su política:
  `metricas.py` toma el nombre de la política del nombre de la carpeta que
  contiene el CSV, no de una columna.
- `config/equipo.env` define `ROS_DOMAIN_ID=47` (equipo 5), mientras que
  `PASOS.txt` y el informe usan `43`. Confirmar cuál rige antes de medir:
  las cinco máquinas tienen que tener el mismo valor.
- Si `ros2 node list` sale vacío, reiniciar el daemon
  (`ros2 daemon stop; ros2 daemon start`) tras exportar las variables.
