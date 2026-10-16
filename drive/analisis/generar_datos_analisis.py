#!/usr/bin/env python3
"""Genera datos_analisis/ completa con un solo comando, sin ROS 2.

    python3 generar_datos_analisis.py

Pasos:
  1. crea datos_analisis/ (y datos_analisis/fifo, datos_analisis/prioridad);
  2. exporta ./fifo y ./prioridad (.db3) a CSV con exportar_csv_directo;
  3. calcula métricas con metricas_directo y guarda resumen + figura.

Los bags se leen de la carpeta actual (RETO2): ./fifo y ./prioridad.
"""

import os
import sys

import exportar_csv_directo
import metricas_directo

BAGS = ['fifo', 'prioridad']
DATOS = 'datos_analisis'


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(raiz)
    print(f'Carpeta de trabajo: {raiz}')

    faltantes = [b for b in BAGS if not os.path.isdir(b)]
    if faltantes:
        sys.exit(f'Faltan las carpetas de bag en {raiz}: {", ".join(faltantes)}')

    for bag in BAGS:
        salida = os.path.join(DATOS, bag)
        print(f'\n--- Exportando {bag}/ -> {salida}/')
        n_cola, n_joint = exportar_csv_directo.exportar(bag, salida)
        if n_cola == 0:
            sys.exit(f'{bag}: sin mensajes /arm/queue_state, no hay métricas.')

    print(f'\n--- Métricas y figura en {DATOS}/')
    metricas_directo.run(datos=DATOS)

    print(f'\nListo: todo lo de análisis quedó en {os.path.join(raiz, DATOS)}')


if __name__ == '__main__':
    main()
