""" Nodo de percepción por color de la cámara — Pregunta 2 """

""" usb_cam publica sensor_msgs/Image en el tópico de imagen (por defecto /camera/image_raw,
pero OJO: usb_cam_node_exe publica en /image_raw relativo si no se le remapea con -r __ns:=/camera
o -r image_raw:=/camera/image_raw; confirmar con `ros2 topic info <topico> -v` antes de asumir).
Este nodo lo suscribe, convierte el fotograma con cv_bridge a OpenCV y detecta el color del
objeto por HSV (misma lógica que docs/agarrar_cubo_sin_rastreo.py). SOLO publica la detección
por un tópico: no mueve el brazo.

Salida: /objeto_detectado (std_msgs/String, JSON) con
    {color, presente, estable, cx, cy, t}

Este nodo es deliberadamente silencioso frame a frame (publicar a 20-30 Hz con un log por
frame inundaría la terminal). Para que SÍ se note cuando algo anda mal, trae dos avisos:
  - un watchdog que avisa si no llega ninguna imagen en 'watchdog_s' segundos (típico cuando
    'topico_imagen' no coincide con lo que usb_cam realmente publica), y
  - un log (no un print silencioso) cada vez que la detección "estable" cambia de color,
    para ver en vivo que sí está viendo la mesa sin inundar la consola. """

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

        self.declare_parameter('topico_imagen', '/image_raw')
        self.declare_parameter('topico_salida', '/objeto_detectado')
        self.declare_parameter('area_min', 300)          # píxeles mínimos del manchón de color
        self.declare_parameter('confirmaciones', 5)      # fotogramas iguales para marcar "estable"
        self.declare_parameter('watchdog_s', 5.0)        # avisa si no llegan imágenes en este tiempo
        self.declare_parameter('log_estado_periodico_s', 0.0)  # 0 = desactivado; >0 = log cada N s

        self.area_min = float(self.get_parameter('area_min').value)
        self.confirmaciones = int(self.get_parameter('confirmaciones').value)
        self.watchdog_s = float(self.get_parameter('watchdog_s').value)
        self.log_periodico_s = float(self.get_parameter('log_estado_periodico_s').value)

        self.bridge = CvBridge()
        self.ultimo_color = None
        self.racha = 0
        self.estable_anterior = False
        self.n_frames = 0
        self.ultima_imagen_t = None       # None = todavía no llegó ninguna imagen
        self._watchdog_avisado = False
        self.pub = self.create_publisher(
            String, str(self.get_parameter('topico_salida').value), 10)
        self.create_subscription(
            Image, str(self.get_parameter('topico_imagen').value), self._on_imagen, 10)

        # Watchdog: si en 'watchdog_s' segundos no llegó ninguna imagen, es casi siempre un
        # tópico mal configurado (usb_cam publicando en otro nombre). Se revisa cada segundo.
        self.create_timer(1.0, self._chequear_watchdog)

        self.get_logger().info('=' * 60)
        self.get_logger().info('  PERCEPCION_CAMARA LISTO')
        self.get_logger().info(f'  imagen : {self.get_parameter("topico_imagen").value}')
        self.get_logger().info(f'  salida : {self.get_parameter("topico_salida").value}')
        self.get_logger().info('=' * 60)

    def _chequear_watchdog(self):
        """Avisa UNA vez si nunca llegó una imagen, o si dejaron de llegar por watchdog_s."""
        ahora = time.time()
        if self.ultima_imagen_t is None:
            # Nunca llegó nada: probablemente el tópico no coincide con el que usb_cam publica
            if not self._watchdog_avisado and self.watchdog_s > 0:
                self._watchdog_avisado = True
                topico = self.get_parameter('topico_imagen').value
                self.get_logger().error(
                    f'⚠️  no llegó NINGUNA imagen en {topico} tras {self.watchdog_s:.0f}s. '
                    f'Verifica con: ros2 topic list | grep -i image  ·  ros2 topic hz {topico}  '
                    f'·  ros2 topic info {topico} -v. '
                    f'(usb_cam_node_exe publica por defecto en /image_raw, NO en /camera/image_raw, '
                    f'salvo que lo remapees con -r __ns:=/camera)')
            return
        # Ya llegaron imágenes alguna vez: avisar si el flujo se cortó
        if ahora - self.ultima_imagen_t > self.watchdog_s:
            self.get_logger().warn(
                f'⚠️  sin imágenes nuevas hace {ahora - self.ultima_imagen_t:.1f}s '
                f'(¿se cayó usb_cam o la cámara?)',
                throttle_duration_sec=self.watchdog_s)

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
        # Se marca la llegada de ESTA imagen de inmediato: así el watchdog ya no se queja
        # aunque la conversión o la detección fallen más abajo.
        self.ultima_imagen_t = time.time()
        self.n_frames += 1
        if self.n_frames == 1:
            self.get_logger().info(
                f'📷 primera imagen recibida en {self.get_parameter("topico_imagen").value} '
                f'({msg.width}x{msg.height}, encoding={msg.encoding})')

        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'no pude convertir la imagen: {e!r}', throttle_duration_sec=2.0)
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

        # Log de TRANSICIÓN (no de cada frame): se ve en la terminal cada vez que la cámara
        # empieza o deja de confirmar un color de forma estable. Es lo que orquestador_item2
        # está esperando en _esperar_deteccion, así que es la señal más útil para depurar.
        if estable != self.estable_anterior:
            if estable:
                self.get_logger().info(f'🎯 color ESTABLE confirmado: {color} (cx={cx}, cy={cy})')
            else:
                self.get_logger().info('…ya no hay color estable sobre la mesa')
            self.estable_anterior = estable

        # Log periódico opcional (apagado por defecto): útil para ver que el nodo sigue vivo
        # y qué está viendo, sin esperar a una transición.
        if self.log_periodico_s > 0:
            self.get_logger().info(
                f'estado: color={color} presente={color is not None} estable={estable}',
                throttle_duration_sec=self.log_periodico_s)

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

