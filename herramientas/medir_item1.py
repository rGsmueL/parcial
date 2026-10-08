#!/usr/bin/env python3
""" Mide latencia y exactitud del servicio /interpretar_orden — evidencia de la Pregunta 1 """
""" Requiere que interprete_ordenes.py ya esté corriendo en otra terminal """

""" Uso:
    python3 medir_item1.py frases_50.csv resultados_item1.csv

El CSV de entrada necesita al menos una columna "frase". Si además trae las columnas
esperado_accion, esperado_objeto, esperado_color, esperado_permitido (la respuesta correcta
que el equipo definió para cada una de las 50 frases del docente), el script también calcula
la tabla de exactitud de LAYA vs. el clasificador. Sin esas columnas, solo mide latencia.

Por cada frase se hacen DOS llamadas al servicio: una normal (deja que LAYA conteste, y si no
llega a tiempo cae al clasificador) y otra forzando el clasificador puro — así se puede medir
la exactitud de cada método por separado sobre exactamente el mismo conjunto de frases, tal
como pide el enunciado.

Repitan la corrida completa dos veces: una con el laboratorio en calma y otra con los 4 equipos
preguntando a la vez, guardando cada corrida en un CSV de salida distinto (ej. resultados_calma.csv
y resultados_carga.csv) para poder compararlas.
"""

import csv
import statistics
import sys

import rclpy
from rclpy.node import Node

from arm_broker_interfaces.srv import InterpretarOrden


# 1. Cliente del servicio
class Medidor(Node):
    def __init__(self):
        super().__init__('medidor_item1')
        self.cli = self.create_client(InterpretarOrden, 'interpretar_orden')

    def esperar_servicio(self):
        if not self.cli.wait_for_service(timeout_sec=10.0):
            self.get_logger().error('no aparece /interpretar_orden. ¿Está corriendo interprete_ordenes?')
            return False
        return True

    def preguntar(self, frase, forzar_clasificador):
        req = InterpretarOrden.Request()
        req.frase = frase
        req.forzar_clasificador = forzar_clasificador
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut)
        return fut.result()


# 2. Percentil con interpolación lineal (mismo criterio que usa NumPy por defecto)
def percentil(datos, p):
    datos = sorted(datos)
    if not datos:
        return float('nan')
    k = (len(datos) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(datos) - 1)
    if f == c:
        return datos[f]
    return datos[f] + (datos[c] - datos[f]) * (k - f)


def main():
    if len(sys.argv) < 2:
        print('uso: python3 medir_item1.py frases.csv [salida.csv]', file=sys.stderr)
        sys.exit(2)

    ruta_entrada = sys.argv[1]
    ruta_salida = sys.argv[2] if len(sys.argv) > 2 else 'resultados_item1.csv'

    with open(ruta_entrada, newline='', encoding='utf-8') as f:
        filas = list(csv.DictReader(f))
    if not filas:
        print(f'{ruta_entrada} está vacío', file=sys.stderr)
        sys.exit(2)

    tiene_esperado = all(
        c in filas[0] for c in ('esperado_accion', 'esperado_objeto', 'esperado_color', 'esperado_permitido'))

    rclpy.init()
    nodo = Medidor()
    if not nodo.esperar_servicio():
        rclpy.shutdown()
        sys.exit(1)

    columnas = [
        'frase',
        'laya_accion', 'laya_objeto', 'laya_color', 'laya_prioridad', 'laya_permitido', 'laya_degradada',
        'laya_tiempo_total_s', 'laya_tiempo_red_s', 'laya_tiempo_computo_s',
        'clasif_accion', 'clasif_objeto', 'clasif_color', 'clasif_prioridad', 'clasif_permitido',
    ]
    if tiene_esperado:
        columnas += ['acierto_laya', 'acierto_clasificador']

    tiempos_total, tiempos_red, tiempos_computo = [], [], []
    aciertos_laya = aciertos_clasif = 0
    filas_salida = []

    print(f'\n{"=" * 70}\n  MIDIENDO {len(filas)} FRASES — ÍTEM 1\n{"=" * 70}\n')

    for n, fila in enumerate(filas, start=1):
        frase = fila['frase']

        r_laya = nodo.preguntar(frase, forzar_clasificador=False)
        r_clasif = nodo.preguntar(frase, forzar_clasificador=True)

        if not r_laya.degradada:
            tiempos_total.append(r_laya.tiempo_total_s)
            tiempos_red.append(r_laya.tiempo_red_s)
            tiempos_computo.append(r_laya.tiempo_computo_s)

        salida = {
            'frase': frase,
            'laya_accion': r_laya.accion, 'laya_objeto': r_laya.objeto, 'laya_color': r_laya.color,
            'laya_prioridad': r_laya.prioridad, 'laya_permitido': r_laya.permitido,
            'laya_degradada': r_laya.degradada,
            'laya_tiempo_total_s': f'{r_laya.tiempo_total_s:.4f}',
            'laya_tiempo_red_s': f'{r_laya.tiempo_red_s:.4f}',
            'laya_tiempo_computo_s': f'{r_laya.tiempo_computo_s:.4f}',
            'clasif_accion': r_clasif.accion, 'clasif_objeto': r_clasif.objeto, 'clasif_color': r_clasif.color,
            'clasif_prioridad': r_clasif.prioridad, 'clasif_permitido': r_clasif.permitido,
        }

        marca = '✅' if not r_laya.degradada else '⚠️  DEGRADADA'
        print(f'[{n:02d}/{len(filas)}] {marca}  "{frase}"')
        print(f'         LAYA:         {r_laya.accion}/{r_laya.objeto}/{r_laya.color} '
              f'p={r_laya.prioridad} permitido={r_laya.permitido}  ({r_laya.tiempo_total_s * 1000:.0f} ms)')
        print(f'         Clasificador: {r_clasif.accion}/{r_clasif.objeto}/{r_clasif.color} '
              f'p={r_clasif.prioridad} permitido={r_clasif.permitido}')

        if tiene_esperado:
            ok_laya = (r_laya.accion == fila['esperado_accion'] and r_laya.objeto == fila['esperado_objeto']
                       and r_laya.color == fila['esperado_color']
                       and str(r_laya.permitido) == fila['esperado_permitido'])
            ok_clasif = (r_clasif.accion == fila['esperado_accion'] and r_clasif.objeto == fila['esperado_objeto']
                         and r_clasif.color == fila['esperado_color']
                         and str(r_clasif.permitido) == fila['esperado_permitido'])
            aciertos_laya += int(ok_laya)
            aciertos_clasif += int(ok_clasif)
            salida['acierto_laya'] = ok_laya
            salida['acierto_clasificador'] = ok_clasif
            print(f'         acierto  →  LAYA={"sí" if ok_laya else "no"}   '
                  f'clasificador={"sí" if ok_clasif else "no"}')

        print()
        filas_salida.append(salida)

    with open(ruta_salida, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas_salida)

    def resumen(nombre, datos):
        if not datos:
            print(f'  {nombre}: sin datos (LAYA no respondió a tiempo ninguna vez)')
            return
        print(f'  {nombre}: mediana={statistics.median(datos) * 1000:.0f} ms   '
              f'p95={percentil(datos, 95) * 1000:.0f} ms')

    print(f'{"=" * 70}\n  RESUMEN DE LATENCIA  (n={len(tiempos_total)} respuestas de LAYA sin degradar)\n{"=" * 70}')
    resumen('tiempo total             ', tiempos_total)
    resumen('tiempo de red (aprox.)   ', tiempos_red)
    resumen('tiempo de cómputo (aprox.)', tiempos_computo)

    if tiene_esperado:
        print(f'\n{"=" * 70}\n  EXACTITUD  (sobre {len(filas)} frases)\n{"=" * 70}')
        print(f'  LAYA:         {aciertos_laya}/{len(filas)}  ({100 * aciertos_laya / len(filas):.0f}%)')
        print(f'  Clasificador: {aciertos_clasif}/{len(filas)}  ({100 * aciertos_clasif / len(filas):.0f}%)')
    else:
        print('\n(no hay columnas esperado_* en el CSV de entrada — no se calculó exactitud)')

    print(f'\nResultados completos guardados en: {ruta_salida}\n')

    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
