""" Prueba de la pinza por la acción GripperCommand — Pregunta 2 """

""" Abre y cierra la pinza para comprobar el nombre de la acción, las posiciones (abierto/
cerrado) y el esfuerzo antes de la demo. NO mueve el brazo.

Uso (Jetson, con el driver arriba):
    ros2 run arm_broker probar_pinza --ros-args -p accion:=gripper_command
    # o directamente, si copias este script a herramientas/ y lo corres con python3
"""

import threading
import time

import rclpy
from control_msgs.action import GripperCommand
from rclpy.action import ActionClient
from rclpy.node import Node


class ProbarPinza(Node):

    def __init__(self):
        super().__init__('probar_pinza')
        self.declare_parameter('accion', 'gripper_command')
        self.declare_parameter('abierto', 0.0)
        self.declare_parameter('cerrado', 0.04)
        self.declare_parameter('esfuerzo', 50.0)

        self.cli = ActionClient(self, GripperCommand, str(self.get_parameter('accion').value))

    def _esperar(self, futuro, timeout=5.0):
        ev = threading.Event()
        futuro.add_done_callback(lambda _: ev.set())
        if not ev.wait(timeout):
            return None
        return futuro.result()

    def comandar(self, posicion):
        posicion = float(posicion)
        self.get_logger().info(f'enviando GripperCommand position={posicion}')
        if not self.cli.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('la acción de la pinza no aparece')
            return
        goal = GripperCommand.Goal()
        goal.position = posicion
        goal.max_effort = float(self.get_parameter('esfuerzo').value)
        handle = self._esperar(self.cli.send_goal_async(goal))
        if handle is None or not handle.accepted:
            self.get_logger().warn('goal rechazado')
            return
        res = self._esperar(handle.get_result_async())
        if res is not None:
            r = res.result
            self.get_logger().info(
                f'resultado: position={r.position:.3f} effort={r.effort:.3f} '
                f'reached={r.reached_goal} stalled={r.stalled}')

    def correr(self):
        self.get_logger().info('abriendo...')
        self.comandar(self.get_parameter('abierto').value)
        time.sleep(1.0)
        self.get_logger().info('cerrando...')
        self.comandar(self.get_parameter('cerrado').value)


def main(args=None):
    rclpy.init(args=args)
    nodo = ProbarPinza()
    try:
        nodo.correr()
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
