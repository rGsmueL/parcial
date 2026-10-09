# EVIDENCIAS — Ítem 1 (Pregunta 1): interpretación de órdenes

> Mapa de **qué archivo es la evidencia, qué lo genera, con qué comando y en qué
> equipo**. El paso a paso completo está en `ITEM_1.md`.
>
> **Ruta base:** todos los comandos se corren desde la **raíz del workspace
> `~/rb2_ws`** (donde están `herramientas/`, `analisis/` y `src/`). El archivo
> `frases_50.csv` vive en esa raíz.

## 0. Quién es quién

| Etiqueta | Equipo |
|---|---|
| **PC-LAYA** | Tu PC Windows (RTX 3050) que corre `laya-serve`. |
| **Jetson** | La Jetson (ROS 2 Humble): nodos, herramientas y grabación. |
| **PC-integrante** | Otras PC del equipo (para la corrida "bajo carga"). |
| **Equipo** | Trabajo manual: informe, tablas, videos. |
| **repo** | Fuente de código versionado (evidencia de implementación). |

---

## 1. Mapa de evidencias

| Evidencia | La genera | Comando (desde `~/rb2_ws`) | Dispositivo / quién | Responsable |
|---|---|---|---|---|
| `frases_50.csv` (50 frases + columnas `esperado_*`) | Equipo (a mano; ya incluido) | — | cualquiera |  |
| `evidencia/laya_prueba.txt` (health + JSON crudo de LAYA) | `herramientas/probar_laya.py` | `python herramientas/probar_laya.py http://127.0.0.1:8000 "agarra el cubo rojo"` | PC-LAYA |  |
| `evidencia/servicio_interpretar.txt` (log normal + `DEGRADADA`) | nodo `interprete_ordenes` | `ros2 service call /interpretar_orden …` | Jetson |  |
| `resultados_calma.csv` | `herramientas/medir_item1.py` | `python3 herramientas/medir_item1.py frases_50.csv resultados_calma.csv` | Jetson |  |
| `resultados_carga.csv` | `herramientas/medir_item1.py` (4 equipos a la vez) | `python3 herramientas/medir_item1.py frases_50.csv resultados_carga.csv` | Jetson + PC-integrante |  |
| `evidencia/resumen_calma.txt`, `evidencia/resumen_carga.txt` | stdout de `medir_item1.py` | (redirigir la salida; abajo) | Jetson |  |
| Tablas de latencia (calma / carga) | Equipo (desde los resúmenes) | — | Equipo |  |
| Tabla de exactitud LAYA vs clasificador | `medir_item1.py` (sección `EXACTITUD`) | (misma corrida) | Jetson |  |
| Media página: qué falla cada método | Equipo | filtrar `acierto_laya` / `acierto_clasificador` | Equipo |  |

**Código que es evidencia de implementación** (lo pone el repo):

- `src/arm_broker_interfaces/srv/InterpretarOrden.srv`
- `src/arm_broker/arm_broker/interprete_ordenes.py`
- `src/arm_broker/arm_broker/cliente_laya.py`
- `src/arm_broker/arm_broker/clasificador_palabras_clave.py`
- `herramientas/medir_item1.py`, `herramientas/probar_laya.py`
- entry point `interprete_ordenes` en `src/arm_broker/setup.py`

---

## 2. Comandos exactos y captura de salida

**PC-LAYA** — comprobar que LAYA responde (guarda la evidencia):

```powershell
# Desde la raíz del repo en tu PC (crea la carpeta de evidencia una vez)
mkdir evidencia
python herramientas\probar_laya.py http://127.0.0.1:8000 "agarra el cubo rojo" | Tee-Object evidencia\laya_prueba.txt
```

**Jetson** — log del servicio en las dos rutas (normal y respaldo):

```bash
mkdir -p evidencia

# Normal (va a LAYA)
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo'}" 2>&1 | tee evidencia/servicio_interpretar.txt

# Respaldo: detén laya-serve en tu PC y repite -> debe salir DEGRADADA
ros2 service call /interpretar_orden arm_broker_interfaces/srv/InterpretarOrden \
  "{frase: 'agarra el cubo rojo'}" 2>&1 | tee -a evidencia/servicio_interpretar.txt
```

**Jetson** — corridas de medición (la evidencia principal de la P1):

```bash
# Corrida 1 — laboratorio en calma
python3 herramientas/medir_item1.py frases_50.csv resultados_calma.csv \
  2>&1 | tee evidencia/resumen_calma.txt

# Corrida 2 — con los 4 equipos preguntando a la vez
python3 herramientas/medir_item1.py frases_50.csv resultados_carga.csv \
  2>&1 | tee evidencia/resumen_carga.txt
```

De cada resumen salen las tres tablas del entregable (latencia calma, latencia
carga y exactitud). La media página de comentarios se arma comparando en el CSV
las filas con `acierto_laya=False` contra `acierto_clasificador=False`.

---

## 3. Checklist de entrega (P1)

- [ ] `frases_50.csv` en la raíz (con `frase` + `esperado_*`).
- [ ] `resultados_calma.csv` y `resultados_carga.csv`.
- [ ] `evidencia/resumen_calma.txt` y `evidencia/resumen_carga.txt` (mediana/p95 + exactitud).
- [ ] `evidencia/laya_prueba.txt` y `evidencia/servicio_interpretar.txt`.
- [ ] Tablas de latencia (calma/carga) y de exactitud en el informe.
- [ ] Media página de comentarios sobre qué frases falla cada método.
