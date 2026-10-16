""" Verifica las poses fijas con la FK del RB-2 — Pregunta 2 """

""" Comprueba, SIN mover el brazo, que cada pose pasa límites articulares y workspace, y que
ninguna transición del plan de agarre supera el paso_max_rad del broker (si lo supera, el
orquestador la trocea con waypoints, pero conviene saberlo).

Con las 4 posiciones (ver zonas.py) hay una pose de agarre por POSICIÓN (RECOGIDAS[1..4]); el
plan de agarre depende del slot y el de transporte del color.

Uso (desde la raíz del repo):
    python herramientas/verificar_poses.py
    python herramientas/verificar_poses.py --paso-max 1.6
"""

import argparse
import os
import sys

_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_raiz, 'src', 'arm_broker'))
sys.path.insert(0, os.path.join(_raiz, 'item2'))

from arm_broker import fk
try:
    from arm_broker import poses as P          # si ya copiaste poses.py al paquete
except ImportError:
    import poses as P                          # o desde item2/ directamente


def revisar_pose(nombre, grados):
    q = P.a_radianes(grados)
    ok_lim, m_lim = fk.dentro_de_limites(q)
    ok_ws, m_ws = fk.dentro_del_workspace(q)
    x, y, z = fk.fk(q)
    estado = 'OK' if (ok_lim and ok_ws) else 'RECHAZA'
    print(f'{estado:7s} {nombre:20s} xyz=({x:7.1f},{y:7.1f},{z:7.1f}) mm'
          + ('' if estado == 'OK' else f'  -> {m_lim or m_ws}'))
    return ok_lim and ok_ws


def paso(a, b):
    return max(abs(x - y) for x, y in zip(P.a_radianes(a), P.a_radianes(b)))


def _transiciones(plan, paso_max):
    """Imprime los saltos entre poses consecutivas de una lista [(nombre, grados), ...]."""
    for (n1, g1), (n2, g2) in zip(plan, plan[1:]):
        p = paso(g1, g2)
        print(f'  {n1:16s} -> {n2:16s} paso={p:5.2f} rad'
              + ('  (> paso_max: se trocea con waypoints)' if p > paso_max else ''))


def poses_de_plan(pasos):
    """Extrae las poses (nombre, grados) de las tuplas ('pose', nombre, grados) de un plan."""
    return [(resto[0], resto[1]) for tipo, *resto in pasos if tipo == 'pose']


def main():
    ap = argparse.ArgumentParser(description='Verifica poses fijas con la FK del RB-2')
    ap.add_argument('--paso-max', type=float, default=1.6, dest='paso_max',
                    help='paso_max_rad del broker')
    args = ap.parse_args()

    print('== Poses individuales ==')
    todas_ok = True
    todas_ok &= revisar_pose('HOME', P.POSE_HOME)
    todas_ok &= revisar_pose('BUSQUEDA', P.POSE_BUSQUEDA)
    for slot in sorted(P.RECOGIDAS):
        todas_ok &= revisar_pose(f'RECOGIDA_{slot}', P.RECOGIDAS[slot])
    todas_ok &= revisar_pose('REPARTO', P.POSE_REPARTO)
    for color, grados in P.DESTINOS.items():
        todas_ok &= revisar_pose(f'DESTINO_{color}', grados)

    print(f'\n== Transiciones de AGARRE por posición (paso_max={args.paso_max}) ==')
    for slot in sorted(P.RECOGIDAS):
        print(f'-- slot {slot} --')
        # busqueda -> recogida[slot] -> busqueda
        plan = poses_de_plan(P.plan_agarrar(slot))
        _transiciones(plan, args.paso_max)

    print(f'\n== Transiciones de TRANSPORTE por color (paso_max={args.paso_max}) ==')
    for color in P.DESTINOS:
        print(f'-- color {color} --')
        # busqueda -> reparto -> destino -> home
        plan = [('busqueda', P.POSE_BUSQUEDA)] + poses_de_plan(P.plan_transportar(color))
        _transiciones(plan, args.paso_max)

    return 0 if todas_ok else 1


if __name__ == '__main__':
    sys.exit(main())
