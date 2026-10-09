""" Cliente de la pinza del JetCobot (GripperCommand) — Pregunta 2 """

""" El broker mueve poses pero NO controla la pinza: la pinza se comanda con la acción estándar
control_msgs/action/GripperCommand que expone el driver/controlador del kit. Este módulo es lo
único que sabe cómo abrir y cerrar; el orquestador solo llama a abrir()/cerrar().

Las posiciones (abierto/cerrado) y el esfuerzo dependen del controlador: se calibran con
herramientas/probar_pinza.py """

import threading
import time

from control_msgs.action import GripperCommand
from rclpy.action import ActionClient


class Pinza:
    """Envoltura del ActionClient de GripperCommand con espera por evento (segura con
    MultiThreadedExecutor: los callbacks corren en otros hilos)"""

    def __init__(self, nodo, accion='gripper_command', abierto=0.0, cerrado=0.04,
                 esfuerzo=50.0, timeout=5.0):
        self.nodo = nodo
        self.cli = ActionClient(nodo, GripperCommand, accion)
        self.abierto = float(abierto)
        self.cerrado = float(cerrado)
        self.esfuerzo = float(esfuerzo)
        self.timeout = float(timeout)

    def _esperar(self, futuro, timeout):
        evento = threading.Event()
        futuro.add_done_callback(lambda _: evento.set())
        if not evento.wait(timeout):
            return None
        return futuro.result()

    def disponible(self, timeout=5.0):
        return self.cli.wait_for_server(timeout_sec=timeout)

    def _comandar(self, posicion):
        if not self.cli.wait_for_server(timeout_sec=self.timeout):
            self.nodo.get_logger().error('la acción de la pinza no aparece (¿driver arriba?)')
            return False
        goal = GripperCommand.Goal()
        goal.position = float(posicion)
        goal.max_effort = self.esfuerzo
        envio = self.cli.send_goal_async(goal)
        handle = self._esperar(envio, self.timeout)
        if handle is None or not handle.accepted:
            self.nodo.get_logger().warn('la pinza rechazó el goal')
            return False
        self._esperar(handle.get_result_async(), self.timeout)
        return True

    def abrir(self):
        self.nodo.get_logger().info(f'🖐  pinza abrir ({self.abierto})')
        ok = self._comandar(self.abierto)
        time.sleep(0.5)
        return ok

    def cerrar(self):
        self.nodo.get_logger().info(f'✊ pinza cerrar ({self.cerrado})')
        ok = self._comandar(self.cerrado)
        time.sleep(0.5)
        return ok
