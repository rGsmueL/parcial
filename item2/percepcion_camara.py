""" Nodo de percepción por color de la cámara — Pregunta 2 """

""" usb_cam publica sensor_msgs/Image en /camera/image_raw. Este nodo lo suscribe, convierte el
fotograma con cv_bridge a OpenCV y detecta el color del objeto por HSV (misma lógica que
docs/agarrar_cubo_sin_rastreo.py). SOLO publica la detección por un tópico: no mueve el brazo.

Salida: /objeto_detectado (std_msgs/String, JSON) con
    {color, presente, estable, cx, cy, t} """

import json
import time

import cv2 as cv
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


# Rangos HSV de cada color sobre la mesa (los del script probado con el kit)
COLORES_HSV = {
    'rojo': [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    'amarillo': [((20, 100, 100), (35, 255, 255))],
    'verde': [((40, 70, 70), (85, 255, 255))],
    'azul': [((90, 100, 70), (130, 255, 255))],
}


class PercepcionCamara(Node):

    def __init__(self):
        super().__init__('percepcion_camara')

        self.declare_parameter('topico_imagen', '/camera/image_raw')
        self.declare_parameter('topico_salida', '/objeto_detectado')
        self.declare_parameter('area_min', 300)          # píxeles mínimos del manchón de color
        self.declare_parameter('confirmaciones', 5)      # fotogramas iguales para marcar "estable"

        self.area_min = float(self.get_parameter('area_min').value)
        self.confirmaciones = int(self.get_parameter('confirmaciones').value)

        self.bridge = CvBridge()
        self.ultimo_color = None
        self.racha = 0
        self.pub = self.create_publisher(
            String, str(self.get_parameter('topico_salida').value), 10)
        self.create_subscription(
            Image, str(self.get_parameter('topico_imagen').value), self._on_imagen, 10)

        self.get_logger().info('=' * 60)
        self.get_logger().info('  PERCEPCION_CAMARA LISTO')
        self.get_logger().info(f'  imagen : {self.get_parameter("topico_imagen").value}')
        self.get_logger().info(f'  salida : {self.get_parameter("topico_salida").value}')
        self.get_logger().info('=' * 60)

    def _detectar(self, cv_img):
        """Devuelve (color, cx, cy) del manchón de color más grande, o (None, 0, 0)"""
        hsv = cv.cvtColor(cv_img, cv.COLOR_BGR2HSV)
        kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (5, 5))
        mejor_color, mejor_area, mejor_centro = None, self.area_min, None

        for nombre, rangos in COLORES_HSV.items():
            mascara = None
            for bajo, alto in rangos:
                m = cv.inRange(hsv, np.array(bajo), np.array(alto))
                mascara = m if mascara is None else cv.bitwise_or(mascara, m)
            mascara = cv.morphologyEx(mascara, cv.MORPH_OPEN, kernel)
            contornos, _ = cv.findContours(mascara, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            if not contornos:
                continue
            c = max(contornos, key=cv.contourArea)
            area = cv.contourArea(c)
            if area > mejor_area:
                m = cv.moments(c)
                if m['m00'] != 0:
                    mejor_area = area
                    mejor_color = nombre
                    mejor_centro = (int(m['m10'] / m['m00']), int(m['m01'] / m['m00']))

        if mejor_centro is None:
            return None, 0, 0
        return mejor_color, mejor_centro[0], mejor_centro[1]

    def _on_imagen(self, msg):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'no pude convertir la imagen: {e!r}')
            return

        color, cx, cy = self._detectar(cv_img)

        # Se cuenta la racha de fotogramas con el mismo color para declararlo "estable"
        if color is not None and color == self.ultimo_color:
            self.racha += 1
        elif color is not None:
            self.ultimo_color = color
            self.racha = 1
        else:
            self.ultimo_color = None
            self.racha = 0

        estable = self.racha >= self.confirmaciones
        salida = String()
        salida.data = json.dumps({
            'color': color,
            'presente': color is not None,
            'estable': bool(estable),
            'cx': int(cx),
            'cy': int(cy),
            't': time.time(),
        })
        self.pub.publish(salida)


def main(args=None):
    rclpy.init(args=args)
    nodo = PercepcionCamara()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
