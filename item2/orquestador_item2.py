""" Orquestador de la cadena de agarre autónomo — Pregunta 2 """

""" Puente entre la decisión tipada (Pregunta 1) y el broker del RB-2, con la regla de oro:
SOLO el worker del broker publica comandos al brazo. Este nodo no publica /joint_states:
únicamente escucha la decisión, espera la confirmación de la cámara, elige la pose fija, y
envía la secuencia de goals a la acción move_arm (con la prioridad del modelo) y a la pinza.

Flujo por orden:
  /orden_decidida → ¿permitida? no → rechazo con causa (CSV), sin encolar
                  → sí → espera /objeto_detectado (color) → secuencia:
                       pinza abrir → busqueda → recogida → pinza cerrar
                       → busqueda → reparto → destino[color] → pinza abrir → home
                  → registra intento + error por FK del RB-2 """

import csv
import json
import math
import os
import queue
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from control_msgs.action import GripperCommand
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from arm_broker_interfaces.action import MoveArm

from arm_broker import intentos as intentos_mod
from arm_broker import poses as poses_mod
from arm_broker.gripper import Pinza


class OrquestadorItem2(Node):

    def __init__(self):
        super().__init__('orquestador_item2')

        self.declare_parameter('client_id', 'p2')
        self.declare_parameter('escala_prioridad', 85)         # priority = prioridad * 85 (0..3 → 0..255)
        self.declare_parameter('paso_max_rad', 1.6)            # trocea los movimientos largos
        self.declare_parameter('usar_camara', True)            # si no, confía en la decisión
        self.declare_parameter('espera_deteccion_s', 3.0)
        self.declare_parameter('timeout_goal_s', 30.0)
        self.declare_parameter('gripper_action', 'gripper_command')
        self.declare_parameter('gripper_abierto', 0.0)
        self.declare_parameter('gripper_cerrado', 0.04)
        self.declare_parameter('gripper_esfuerzo', 50.0)
        self.declare_parameter('topico_decision', 'orden_decidida')
        self.declare_parameter('topico_deteccion', 'objeto_detectado')
        self.declare_parameter('archivo_rechazos', 'rechazos_orquestador.csv')
        self.declare_parameter('archivo_intentos', 'intentos.csv')

        self.client_id = str(self.get_parameter('client_id').value)
        self.escala = int(self.get_parameter('escala_prioridad').value)
        self.paso_max = float(self.get_parameter('paso_max_rad').value)
        self.usar_camara = bool(self.get_parameter('usar_camara').value)
        self.espera_deteccion = float(self.get_parameter('espera_deteccion_s').value)
        self.timeout_goal = float(self.get_parameter('timeout_goal_s').value)
        self.archivo_rechazos = str(self.get_parameter('archivo_rechazos').value)
        self.archivo_intentos = str(self.get_parameter('archivo_intentos').value)

        self._preparar_csv()

        grupo = ReentrantCallbackGroup()
        self.cli_mover = ActionClient(self, MoveArm, 'move_arm', callback_group=grupo)
        self.pinza = Pinza(
            self,
            accion=str(self.get_parameter('gripper_action').value),
            abierto=float(self.get_parameter('gripper_abierto').value),
            cerrado=float(self.get_parameter('gripper_cerrado').value),
            esfuerzo=float(self.get_parameter('gripper_esfuerzo').value),
            timeout=self.timeout_goal,
        )

        self.create_subscription(String, str(self.get_parameter('topico_decision').value),
                                 self._on_decision, 10, callback_group=grupo)
        self.create_subscription(String, str(self.get_parameter('topico_deteccion').value),
                                 self._on_deteccion, 10, callback_group=grupo)
        # Suscripción de SOLO LECTURA: captura la pose alcanzada para el error de FK
        self.create_subscription(JointState, '/joint_states', self._on_joint_states, 10,
                                 callback_group=grupo)

        self.lock = threading.Lock()
        self.q_actual = [0.0] * 6
        self.deteccion = None
        self.cola = queue.Queue()
        self._parar = threading.Event()
        self.intento = 0

        self.hilo = threading.Thread(target=self._trabajador, daemon=True)
        self.hilo.start()

        self.get_logger().info('=' * 60)
        self.get_logger().info('  ORQUESTADOR ITEM2 LISTO')
        self.get_logger().info(f'  escala prioridad : x{self.escala}')
        self.get_logger().info(f'  paso_max_rad     : {self.paso_max}')
        self.get_logger().info(f'  usar_camara      : {self.usar_camara}')
        self.get_logger().info(f'  pinza (acción)   : {self.get_parameter("gripper_action").value}')
        self.get_logger().info('=' * 60)

    # 1. Utilidades de CSV y espera
    def _preparar_csv(self):
        intentos_mod.preparar_csv(self.archivo_intentos)
        if not os.path.exists(self.archivo_rechazos):
            with open(self.archivo_rechazos, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['t_unix', 'client_id', 'priority', 'causa', 'motivo', 'frase'])

    @staticmethod
    def _esperar(futuro, timeout):
        evento = threading.Event()
        futuro.add_done_callback(lambda _: evento.set())
        if not evento.wait(timeout):
            return None
        return futuro.result()

    # 2. Callbacks de suscripción
    def _on_joint_states(self, msg):
        with self.lock:
            if len(msg.position) >= 6:
                self.q_actual = [float(v) for v in msg.position[:6]]

    def _on_deteccion(self, msg):
        try:
            datos = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        with self.lock:
            self.deteccion = datos

    def _on_decision(self, msg):
        try:
            self.cola.put(json.loads(msg.data))
        except json.JSONDecodeError:
            self.get_logger().error(f'decisión inválida: {msg.data!r}')

    # 3. Hilo trabajador: procesa una orden completa a la vez
    def _trabajador(self):
        while not self._parar.is_set():
            try:
                decision = self.cola.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._atender(decision)
            except Exception as e:
                self.get_logger().error(f'error atendiendo la orden: {e!r}')

    def _rechazar(self, decision, causa, motivo):
        with open(self.archivo_rechazos, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                f'{time.time():.3f}', self.client_id, int(decision.get('prioridad', 0)),
                causa, motivo, decision.get('frase', ''),
            ])
        self.get_logger().warn(
            f'⛔ RECHAZADA ({causa}) sin encolar: "{decision.get("frase", "")}" — {motivo}')

    # 4. Espera de la confirmación visual del color
    def _esperar_deteccion(self, color):
        limite = time.time() + self.espera_deteccion
        while time.time() < limite and rclpy.ok():
            with self.lock:
                det = dict(self.deteccion) if self.deteccion else None
            if det and det.get('presente') and det.get('color') == color and det.get('estable'):
                return det
            time.sleep(0.05)
        return None

    # 5. Envío de un movimiento al broker (una meta, ya troceada por escalonar)
    def _enviar_pose(self, q_rad, prioridad):
        if not self.cli_mover.wait_for_server(timeout_sec=self.timeout_goal):
            self.get_logger().error('el broker no aparece (¿corre arm_broker?)')
            return False
        goal = MoveArm.Goal()
        goal.joint_positions = [float(v) for v in q_rad]
        goal.client_id = self.client_id
        goal.priority = prioridad
        handle = self._esperar(self.cli_mover.send_goal_async(goal, feedback_callback=self._feedback),
                               self.timeout_goal)
        if handle is None or not handle.accepted:
            self.get_logger().warn('el broker RECHAZÓ el goal (ver rechazos.csv del broker)')
            return False
        resultado = self._esperar(handle.get_result_async(), self.timeout_goal)
        if resultado is None:
            self.get_logger().warn('sin resultado del broker (timeout)')
            return False
        r = resultado.result
        self.get_logger().info(
            f'   🦾 success={r.success} espera={r.wait_time_s:.2f}s ejec={r.exec_time_s:.2f}s')
        return bool(r.success)

    def _mover_a(self, grados, prioridad):
        """Mueve hacia la pose destino (en grados), troceando en metas que respeten paso_max"""
        destino = poses_mod.a_radianes(grados)
        exito = True
        with self.lock:
            origen = list(self.q_actual)
        for meta in poses_mod.escalonar(origen, destino, self.paso_max):
            if not self._enviar_pose(meta, prioridad):
                exito = False
                break
            with self.lock:
                origen = list(self.q_actual)
        return exito, destino

    def _feedback(self, msg):
        f = msg.feedback
        self.get_logger().info(
            f'   {f.state} pos={f.queue_position} t={f.elapsed_s:.1f}s',
            throttle_duration_sec=1.0)

    # 6. Atención de una decisión válida
    def _atender(self, decision):
        frase = decision.get('frase', '')
        objeto = decision.get('objeto', 'desconocido')
        color = (decision.get('color') or 'ninguno').lower()
        motivo = decision.get('motivo', '')

        if not decision.get('permitido', False):
            self._rechazar(decision, 'no_permitida', motivo or 'el modelo marcó permitido=False')
            return
        if objeto == 'desconocido' or color == 'ninguno':
            self._rechazar(decision, 'objeto_desconocido',
                           'objeto o color no reconocidos; no hay pose de agarre')
            return

        if self.usar_camara:
            det = self._esperar_deteccion(color)
            if det is None:
                self._rechazar(decision, 'sin_deteccion',
                               f'la cámara no confirmó un objeto {color} estable sobre la mesa')
                return

        prioridad = max(0, min(255, int(decision.get('prioridad', 0)) * self.escala))
        self.intento += 1
        self.get_logger().info(
            f'▶️  intento {self.intento}: "{frase}" ({objeto}/{color}) priority={prioridad}')

        q_recogida_pedida = poses_mod.a_radianes(poses_mod.POSE_RECOGIDA)
        q_recogida_alcanzada = list(q_recogida_pedida)
        exito = True

        for paso in poses_mod.plan_pick_and_place(color):
            if paso[0] == 'gripper':
                ok = self.pinza.abrir() if paso[1] == 'abrir' else self.pinza.cerrar()
                exito = exito and ok
            else:
                ok, destino = self._mover_a(paso[2], prioridad)
                exito = exito and ok
                if paso[1] == 'recogida':
                    with self.lock:
                        q_recogida_alcanzada = list(self.q_actual)

        error = intentos_mod.error_mm(q_recogida_pedida, q_recogida_alcanzada)
        intentos_mod.registrar(self.archivo_intentos, self.intento, frase, objeto, color,
                               f'zona_{color}', exito, q_recogida_pedida, q_recogida_alcanzada, error)
        self.get_logger().info(
            f'🏁 intento {self.intento}: exito={exito} error_FK={error:.2f} mm')

    # 7. Cierre
    def destroy_node(self):
        self._parar.set()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    nodo = OrquestadorItem2()
    ejecutor = MultiThreadedExecutor(num_threads=4)
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
