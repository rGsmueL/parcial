#!/usr/bin/env python3
"""Métricas del ítem 3 + figura comparativa, sin ROS 2.

    python3 metricas_directo.py [--datos datos_analisis] [--salida ...]

Lee los queue_state.csv que genera exportar_csv_directo.py (una subcarpeta por
política dentro de --datos), imprime el resumen, lo guarda en
resumen_metricas.txt y genera comparacion_politicas.png.

La lógica de cálculo es la de metricas.py (espera media/p95, inanición, equidad
de Jain, exclusión mutua, contadores del broker): este script sólo cambia la
entrada (CSV ya exportados, no bags) y agrega el guardado en archivo.
"""

import argparse
import contextlib
import io
import os
import sys

import metricas


def politicas(datos):
    """Subcarpetas de --datos que contienen un queue_state.csv, en orden estable."""
    if not os.path.isdir(datos):
        sys.exit(f'No encuentro la carpeta de datos: {datos}')
    encontradas = []
    for nombre in sorted(os.listdir(datos)):
        ruta = os.path.join(datos, nombre, 'queue_state.csv')
        if os.path.isfile(ruta):
            encontradas.append((nombre, ruta))
    if not encontradas:
        sys.exit(f'No hay ningún queue_state.csv dentro de {datos}. '
                 'Corré antes exportar_csv_directo.py o generar_datos_analisis.py.')
    return encontradas


def run(datos='datos_analisis', salida=None, figura=None):
    salida = salida or os.path.join(datos, 'resumen_metricas.txt')
    figura = figura or os.path.join(datos, 'comparacion_politicas.png')

    rutas = politicas(datos)

    # resumen() imprime por stdout: lo capturamos para poder guardarlo igual.
    buffer = io.StringIO()
    resumenes = []
    with contextlib.redirect_stdout(buffer):
        for nombre, ruta in rutas:
            r = metricas.resumen(nombre, ruta)
            if r:
                resumenes.append(r)

    texto = buffer.getvalue()
    print(texto, end='')

    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with open(salida, 'w', encoding='utf-8') as f:
        f.write('Métricas del ítem 3 — broker arm_broker\n')
        f.write('=' * 60 + '\n')
        f.write(texto)
    print(f'Resumen: {salida}')

    if len(resumenes) >= 2:
        metricas.figura(resumenes, figura)
    elif resumenes:
        print('\nCon un solo CSV no hay comparación: hace falta una corrida '
              'por política (fifo/ y prioridad/).')
    return resumenes


def main():
    ap = argparse.ArgumentParser(
        description='Métricas y figura comparativa a partir de CSV ya exportados.')
    ap.add_argument('--datos', default='datos_analisis',
                    help='carpeta con una subcarpeta por política (default: datos_analisis)')
    ap.add_argument('--salida', default=None,
                    help='ruta del resumen .txt (default: <datos>/resumen_metricas.txt)')
    ap.add_argument('--figura', default=None,
                    help='ruta de la figura .png (default: <datos>/comparacion_politicas.png)')
    args = ap.parse_args()
    run(args.datos, args.salida, args.figura)


if __name__ == '__main__':
    main()
