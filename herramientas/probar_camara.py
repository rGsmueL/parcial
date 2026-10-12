""" Prueba de la cámara por OpenCV, SIN ROS 2 — Pregunta 2 """

""" Sirve para encontrar el /dev/videoN correcto y comprobar la detección HSV antes de usar
usb_cam. Muestra en consola el color detectado y guarda un fotograma de referencia.

Uso (desde la raíz del repo):
    python herramientas/probar_camara.py               # prueba índices 0,1,2,8
    python herramientas/probar_camara.py 0             # solo el índice 0
    python herramientas/probar_camara.py 0 --guardar frame.png
"""

import argparse
import sys

import cv2 as cv
import numpy as np

COLORES_HSV = {
    'rojo': [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    'amarillo': [((20, 100, 100), (35, 255, 255))],
    'verde': [((40, 70, 70), (85, 255, 255))],
    'azul': [((90, 100, 70), (130, 255, 255))],
}


def detectar(frame, area_min=300):
    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (5, 5))
    mejor, mejor_area = None, float(area_min)
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
            mejor_area = area
            mejor = nombre
    return mejor


def abrir(indice):
    cap = cv.VideoCapture(indice)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            return cap, frame
        cap.release()
    return None, None


def main():
    ap = argparse.ArgumentParser(description='Prueba de cámara por OpenCV (sin ROS 2)')
    ap.add_argument('indice', nargs='?', type=int, default=None, help='índice de /dev/videoN')
    ap.add_argument('--guardar', default=None, help='guarda un fotograma en esta ruta')
    args = ap.parse_args()

    indices = [args.indice] if args.indice is not None else [0, 1, 2, 8]
    for idx in indices:
        cap, frame = abrir(idx)
        if cap is None:
            print(f'/dev/video{idx}: no disponible')
            continue
        color = detectar(frame)
        print(f'/dev/video{idx}: OK  forma={frame.shape}  color_detectado={color}')
        if args.guardar:
            cv.imwrite(args.guardar, frame)
            print(f'   fotograma guardado en {args.guardar}')
        cap.release()
        return 0

    print('Ningún índice funcionó. Revisa `ls -l /dev/video*` y los permisos de usuario.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
