""" Orquestador mínimo de la cadena voz → decisión → cola del broker → brazo — Preguntas 2/3 """

""" Puente entre la decisión tipada (que produce la Pregunta 1) y el broker del RB-2.
NO es un nodo nuevo de la Pregunta 3 estrictamente: es el andamiaje mínimo del orquestador de
la Pregunta 2, suficiente para cerrar la cadena de voz ANTES de tener cámara + IK + MoveIt2.

Qué hace:
  1. escucha la decisión en /orden_decidida (la publica transcriptor_voz)
  2. si la orden NO está permitida (o el objeto es desconocido) la RECHAZA antes de encolar
     y lo deja escrito en rechazos_orquestador.csv con su causa y motivo
  3. si es válida, escala la prioridad del modelo (0..3 × 85 → uint8), elige una pose y
     envía el goal a la acción move_arm del broker
Nunca publica /joint_states: solo envía goals (regla eliminatoria del publicador único) """

import csv
import json
import os
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from std_msgs.msg import String

from arm_broker_interfaces.action import MoveArm


class Orquestador(Node):

    def __init__(self):
        super().__init__('orquestador')

        self.declare_parameter('client_id', 'voz')
        self.declare_parameter('escala_prioridad', 85)          # priority = prioridad * 85 (0..3 → 0..255)
        self.declare_parameter('pose_defecto', [0.3, 0.0, 0.0, 0.0, 0.0, 0.0])
        # Poses por color/objeto como texto "clave=a,b,c,d,e,f"; placeholder hasta tener cámara+IK
        self.declare_parameter('mapa_poses', [
            'rojo=0.30,0.0,0.0,0.0,0.0,0.0',
            'verde=-0.30,0.0,0.0,0.0,0.0,0.0',
            'azul=0.30,0.3,0.0,0.0,0.0,0.0',
            'amarillo=-0.30,0.3,0.0,0.0,0.0,0.0',
        ])
        self.declare_parameter('archivo_rechazos', 'rechazos_orquestador.csv')
        self.declare_parameter('archivo_intentos', 'intentos.csv')
        self.declare_parameter('archivo_tiempos', 'tiempos_acciones.csv')
        self.declare_parameter('topico_decision', 'orden_decidida')

        self.client_id = str(self.get_parameter('client_id').value)
        self.escala = int(self.get_parameter('escala_prioridad').value)
        self.pose_defecto = [float(v) for v in self.get_parameter('pose_defecto').value]
        self.mapa = self._parsear_poses(self.get_parameter('mapa_poses').value)
        self.archivo_rechazos = str(self.get_parameter('archivo_rechazos').value)
        self.archivo_intentos = str(self.get_parameter('archivo_intentos').value)
        self.archivo_tiempos = str(self.get_parameter('archivo_tiempos').value)

        self._preparar_csv()

        grupo = ReentrantCallbackGroup()
        self.cli = ActionClient(self, MoveArm, 'move_arm', callback_group=grupo)
        self.sub = self.create_subscription(
            String, str(self.get_parameter('topico_decision').value),
            self._procesar, 10, callback_group=grupo)

        self.intento = 0
        self.get_logger().info('=' * 60)
        self.get_logger().info('  ORQUESTADOR (mínimo) LISTO')
        self.get_logger().info(f'  escala prioridad : x{self.escala}')
        self.get_logger().info(f'  poses conocidas  : {sorted(self.mapa)}')
        self.get_logger().info('=' * 60)

    # 1. Utilidades
    @staticmethod
    def _parsear_poses(lista):
        """Convierte ['rojo=q1,q2,...', ...] en {'rojo': [q1,...], ...}"""
        mapa = {}
        for item in lista:
            if '=' not in item:
                continue
            clave, valores = item.split('=', 1)
            try:
                q = [float(v) for v in valores.split(',')]
            except ValueError:
                continue
            if len(q) == 6:
                mapa[clave.strip().lower()] = q
        return mapa

    def _pose(self, decision):
        """Elige la pose por color, luego por objeto, y si no, la de defecto (placeholder)"""
        for clave in (decision.get('color', '').lower(), decision.get('objeto', '').lower()):
            if clave in self.mapa:
                return self.mapa[clave]
        return self.pose_defecto

    def _preparar_csv(self):
        if not os.path.exists(self.archivo_rechazos):
            with open(self.archivo_rechazos, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['t_unix', 'client_id', 'priority', 'causa', 'motivo', 'frase'])
        if not os.path.exists(self.archivo_intentos):
            with open(self.archivo_intentos, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([
                    'intento', 'frase', 'objeto', 'color', 'zona', 'exito',
                    'q_solicitada', 'q_alcanzada', 'error_mm',
                ])
        if not os.path.exists(self.archivo_tiempos):
            with open(self.archivo_tiempos, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow([
                    't_unix', 'frase', 'prioridad', 't3', 't4', 't5',
                    'wait_time_s', 'exec_time_s', 'exito',
                ])

    # 2. Rechazo antes de encolar
    def _rechazar(self, decision, causa, motivo):
        with open(self.archivo_rechazos, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                f'{time.time():.3f}', self.client_id, int(decision.get('prioridad', 0)),
                causa, motivo, decision.get('frase', ''),
            ])
        self.get_logger().warn(
            f'⛔ RECHAZADA ANTES DE ENCOLAR ({causa}): "{decision.get("frase", "")}" — {motivo}')

    # 3. Procesamiento de una decisión
    def _procesar(self, msg):
        try:
            decision = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'decisión inválida (no es JSON): {msg.data!r}')
            return

        frase = decision.get('frase', '')
        motivo = decision.get('motivo', '')

        # Regla del enunciado: no permitida → rechazo ANTES de encolar, con causa
        if not decision.get('permitido', False):
            self._rechazar(decision, 'no_permitida', motivo or 'el modelo marcó permitido=False')
            return
        if decision.get('objeto', 'desconocido') == 'desconocido' or decision.get('color', 'ninguno') == 'ninguno':
            self._rechazar(decision, 'objeto_desconocido',
                           'objeto o color no reconocidos; no hay pose de agarre')
            return

        if not self.cli.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('el broker no aparece: ¿está corriendo arm_broker?')
            return

        pose = self._pose(decision)
        # La prioridad viene del modelo (no se escribe a mano); se escala al rango uint8 del goal
        prioridad = max(0, min(255, int(decision.get('prioridad', 0)) * self.escala))

        goal = MoveArm.Goal()
        goal.joint_positions = pose
        goal.client_id = self.client_id
        goal.priority = prioridad
        decision['pose'] = pose

        self.get_logger().info(
            f'➡️  goal move_arm: "{frase}" pose={pose} priority={prioridad}')

        envio = self.cli.send_goal_async(goal, feedback_callback=self._feedback)
        envio.add_done_callback(lambda fut, d=decision: self._aceptado(fut, d))

    def _aceptado(self, futuro, decision):
        handle = futuro.result()
        if handle is None or not handle.accepted:
            self.get_logger().warn(
                f'⚠️  el broker RECHAZÓ el goal por geometría: "{decision.get("frase", "")}" '
                f'(ver rechazos.csv del broker)')
            return
        t4 = time.time()
        decision['t4'] = t4
        resultado = handle.get_result_async()
        resultado.add_done_callback(lambda fut, d=decision: self._resultado(fut, d))

    def _resultado(self, futuro, decision):
        r = futuro.result().result
        t5 = time.time()
        self.intento += 1

        self.get_logger().info(
            f'🏁 intento {self.intento}: success={r.success} '
            f'espera_en_cola={r.wait_time_s:.2f}s ejec={r.exec_time_s:.2f}s — {r.message}')

        with open(self.archivo_intentos, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                self.intento, decision.get('frase', ''), decision.get('objeto', ''),
                decision.get('color', ''), 'zona_placeholder', bool(r.success),
                decision.get('pose', ''), '', '',
            ])

        with open(self.archivo_tiempos, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                f'{time.time():.3f}', decision.get('frase', ''),
                int(decision.get('prioridad', 0)),
                f"{decision.get('t3', 0.0):.3f}", f"{decision.get('t4', 0.0):.3f}", f'{t5:.3f}',
                f'{r.wait_time_s:.3f}', f'{r.exec_time_s:.3f}', bool(r.success),
            ])

    def _feedback(self, msg):
        f = msg.feedback
        self.get_logger().info(
            f'   {f.state} pos={f.queue_position} t={f.elapsed_s:.1f}s',
            throttle_duration_sec=1.0)


def main(args=None):
    rclpy.init(args=args)
    nodo = Orquestador()
    ejecutor = MultiThreadedExecutor()
    ejecutor.add_node(nodo)
    try:
        ejecutor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
