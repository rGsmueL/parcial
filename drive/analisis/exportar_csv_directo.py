#!/usr/bin/env python3
"""Lee un bag de ROS 2 (.db3) SIN ROS 2 y escribe dos CSV: /arm/queue_state y /joint_states.

    python3 exportar_csv_directo.py <carpeta_del_bag> [--salida .]

Alternativa a exportar_csv.py para máquinas sin ROS 2 (sin rosbag2_py, sin
rclpy, sin terminal de ROS). El bag de rosbag2 es un SQLite (.db3) y la
serialización CDR de estos dos mensajes se decodifica a mano con la stdlib.

El resultado es el mismo CSV que produce exportar_csv.py, así que metricas.py
y metricas_directo.py lo leen igual.
"""

import argparse
import csv
import glob
import os
import sqlite3
import struct
import sys


class LectorCDR:
    """Decodificador CDR mínimo para los dos mensajes del bag.

    La alineación se mide desde el byte 4 (después del encapsulation header
    `00 01 00 00`), que es como lo escribe rosbag2 en Humble. Validado contra
    el 100% de los mensajes de fifo/ y prioridad/.
    """

    def __init__(self, datos):
        self.b = datos
        self.pos = 4

    def _alinear(self, n):
        while (self.pos - 4) % n:
            self.pos += 1

    def u32(self):
        self._alinear(4)
        v = struct.unpack_from('<I', self.b, self.pos)[0]
        self.pos += 4
        return v

    def i32(self):
        self._alinear(4)
        v = struct.unpack_from('<i', self.b, self.pos)[0]
        self.pos += 4
        return v

    def f64(self):
        self._alinear(8)
        v = struct.unpack_from('<d', self.b, self.pos)[0]
        self.pos += 8
        return v

    def u8(self):
        v = self.b[self.pos]
        self.pos += 1
        return v

    def string(self):
        n = self.u32()
        v = self.b[self.pos:self.pos + n - 1].decode('utf8', 'replace')
        self.pos += n
        return v

    def fin(self):
        return self.pos == len(self.b)


def decodificar_queue_state(d):
    """arm_broker_interfaces/msg/QueueState -> dict."""
    c = LectorCDR(d)
    sec = c.u32()
    ns = c.u32()
    msg = {
        't_ns': sec * 10**9 + ns,
        'executing_client': c.string(),
        'executing_goal_id': c.string(),
        'executing_elapsed_s': c.f64(),
        'queue_length': c.i32(),
    }
    msg['queued_goal_ids'] = [c.string() for _ in range(c.u32())]
    msg['queued_clients'] = [c.string() for _ in range(c.u32())]
    n = c.u32()
    msg['queued_priorities'] = [c.u8() for _ in range(n)]
    n = c.u32()
    msg['queued_wait_s'] = [c.f64() for _ in range(n)]
    msg['total_accepted'] = c.i32()
    msg['total_rejected'] = c.i32()
    msg['total_completed'] = c.i32()
    if not c.fin():
        raise ValueError(f'QueueState: se esperaba fin en {len(d)}, leyó {c.pos}')
    return msg


def decodificar_joint_state(d):
    """sensor_msgs/msg/JointState -> dict (solo position)."""
    c = LectorCDR(d)
    sec = c.u32()
    ns = c.u32()
    c.string()  # frame_id
    [c.string() for _ in range(c.u32())]  # name
    n = c.u32()
    pos = [c.f64() for _ in range(n)]
    for _ in range(2):  # velocity, effort
        n = c.u32()
        for _ in range(n):
            c.f64()
    if not c.fin():
        raise ValueError(f'JointState: se esperaba fin en {len(d)}, leyó {c.pos}')
    return {'t_ns': sec * 10**9 + ns, 'position': pos}


def abrir_bag(carpeta):
    """Abre el .db3 de la carpeta del bag y devuelve (conexion, {nombre: id})."""
    dbs = glob.glob(os.path.join(carpeta, '*.db3'))
    if not dbs:
        sys.exit(f'No encuentro ningún .db3 en: {carpeta}')
    con = sqlite3.connect(f'file:{dbs[0]}?mode=ro', uri=True)
    topicos = {nombre: tid for tid, nombre in
               con.execute('SELECT id, name FROM topics')}
    return con, topicos


def exportar(carpeta, salida):
    os.makedirs(salida, exist_ok=True)
    con, topicos = abrir_bag(carpeta)

    ruta_cola = os.path.join(salida, 'queue_state.csv')
    ruta_joint = os.path.join(salida, 'joint_states.csv')
    f_cola = open(ruta_cola, 'w', newline='')
    w_cola = csv.writer(f_cola)
    w_cola.writerow(['t_ns', 'executing_client', 'executing_goal_id',
                     'executing_elapsed_s', 'queue_length', 'queued_goal_ids',
                     'queued_clients', 'queued_priorities', 'queued_wait_s',
                     'total_accepted', 'total_rejected', 'total_completed'])
    f_joint = open(ruta_joint, 'w', newline='')
    w_joint = csv.writer(f_joint)
    w_joint.writerow(['t_ns', 'j1', 'j2', 'j3', 'j4', 'j5', 'j6'])

    n_cola = n_joint = 0
    print(f'Tópicos en {carpeta}:')
    for nombre, tid in sorted(topicos.items(), key=lambda x: x[1]):
        n = con.execute('SELECT COUNT(*) FROM messages WHERE topic_id=?',
                        (tid,)).fetchone()[0]
        print(f'  {nombre}  ({n} mensajes)')

    for nombre, tid in topicos.items():
        filas = con.execute(
            'SELECT timestamp, data FROM messages WHERE topic_id=? '
            'ORDER BY timestamp', (tid,))
        for t_ns, data in filas:
            if nombre.endswith('queue_state'):
                m = decodificar_queue_state(data)
                w_cola.writerow([
                    m['t_ns'], m['executing_client'], m['executing_goal_id'],
                    f"{m['executing_elapsed_s']:.3f}", m['queue_length'],
                    '|'.join(m['queued_goal_ids']),
                    '|'.join(m['queued_clients']),
                    '|'.join(str(p) for p in m['queued_priorities']),
                    '|'.join(f'{v:.3f}' for v in m['queued_wait_s']),
                    m['total_accepted'], m['total_rejected'],
                    m['total_completed']])
                n_cola += 1
            elif nombre.endswith('joint_states'):
                m = decodificar_joint_state(data)
                pos = list(m['position']) + [0.0] * 6
                w_joint.writerow([m['t_ns']] +
                                 [f'{v:.5f}' for v in pos[:6]])
                n_joint += 1

    f_cola.close()
    f_joint.close()
    con.close()
    print(f'\nqueue_state.csv   {n_cola} filas  -> {ruta_cola}')
    print(f'joint_states.csv  {n_joint} filas  -> {ruta_joint}')
    if n_cola == 0:
        print('\nOJO: no hay /arm/queue_state en este bag. '
              'Sin él no hay métricas del ítem 3.')
    return n_cola, n_joint


def main():
    ap = argparse.ArgumentParser(
        description='Exporta un bag .db3 a CSV sin necesidad de ROS 2.')
    ap.add_argument('bag', help='carpeta del bag (ej. fifo)')
    ap.add_argument('--salida', default='.', help='carpeta destino de los CSV')
    args = ap.parse_args()

    if not os.path.isdir(args.bag):
        sys.exit(f'No encuentro la carpeta del bag: {args.bag}')
    exportar(args.bag, args.salida)


if __name__ == '__main__':
    main()
