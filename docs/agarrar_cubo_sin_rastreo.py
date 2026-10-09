import time
import threading
import cv2 as cv
import numpy as np
import ipywidgets as widgets
from IPython.display import display
from pymycobot.mycobot import MyCobot

# ── Configuración e Inicialización ──────────────────────────────────
robot = MyCobot("/dev/ttyUSB0", 1000000)
VELOCIDAD = 50

POSE_HOME = [0, 0, 0, 0, 0, -45]
POSE_BUSQUEDA = [10.81, -25.57, 15.9, -72.33, 2.02, -32.69]
ANGLES_RECOGIDA = [18.28, -36.65, -76.37, 10.45, -0.26, -22.76]
DESTINO_REPARTO = [93.51, -4.04, -71.54, -12.83, -1.75, -36.29]

DESTINOS = {
    "AMARILLO": [65.12, -72.15, -8.87, -11.77, 5.18, -66.18],
    "ROJO":     [80.15, -45.35, -61.78, 12.39, 5.27, -51.24],
    "VERDE":    [96.15, -35.15, -81.73, 23.37, 5.27, -36.56],
    "AZUL":     [113.29, -35.15, -81.73, 23.37, 5.27, -18.63],
}

COLORES_HSV = {
    "ROJO":     [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    "AMARILLO": [((20, 100, 100), (35, 255, 255))],
    "VERDE":    [((40, 70, 70), (85, 255, 255))],
    "AZUL":     [((90, 100, 70), (130, 255, 255))],
}

# Control de estado de hilos
camara_activa = threading.Event()
loop_activo = threading.Event()
candado = threading.Lock()
ultima_deteccion = None


# ── Búsqueda Segura de Cámara ──────────────────────────────────────
def obtener_camara():
    for idx in [0, 1, 2, 8]:
        cap = cv.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                return cap
            cap.release()
    return None


# ── Detección de Color ──────────────────────────────────────────────
def procesar_frame(frame):
    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (5, 5))
    mejor_color, mejor_area, mejor_centro = None, 300, None

    for nombre, rangos in COLORES_HSV.items():
        mascara = None
        for bajo, alto in rangos:
            m = cv.inRange(hsv, np.array(bajo), np.array(alto))
            mascara = m if mascara is None else cv.bitwise_or(mascara, m)

        mascara = cv.morphologyEx(mascara, cv.MORPH_OPEN, kernel)
        contornos, _ = cv.findContours(mascara, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        
        if contornos:
            c = max(contornos, key=cv.contourArea)
            area = cv.contourArea(c)
            if area > mejor_area:
                m = cv.moments(c)
                if m["m00"] != 0:
                    mejor_area = area
                    mejor_color = nombre
                    mejor_centro = (int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]))

    if mejor_centro:
        cx, cy = mejor_centro
        cv.circle(frame, (cx, cy), 8, (0, 255, 0), -1)
        cv.putText(frame, mejor_color, (cx + 10, cy), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return mejor_color, cx, cy
    return None


# ── Hilo de Cámara ──────────────────────────────────────────────────
def flujo_camara(widget_display, log_widget):
    cap = obtener_camara()
    if cap is None:
        with log_widget:
            print("[ERROR] No se pudo conectar a la cámara.")
        camara_activa.clear()
        return

    with log_widget:
        print("[OK] Transmisión de cámara iniciada.")

    while camara_activa.is_set():
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.03)
            continue

        resultado = procesar_frame(frame)
        with candado:
            global ultima_deteccion
            ultima_deteccion = resultado

        ok, jpeg = cv.imencode('.jpg', frame)
        if ok:
            widget_display.value = jpeg.tobytes()
        
        time.sleep(0.03)

    cap.release()
    with log_widget:
        print("Cámara liberada.")


# ── Control del Robot ───────────────────────────────────────────────
def controlar_pinza(abrir=True):
    val = 100 if abrir else 15
    robot.set_gripper_value(val, 50)
    time.sleep(1.5)

def mover(angulos, pausa=2.5):
    robot.send_angles(angulos, VELOCIDAD)
    time.sleep(pausa)

def ejecutar_pick_and_place(color):
    if color not in DESTINOS:
        return
    controlar_pinza(abrir=True)
    mover(ANGLES_RECOGIDA, pausa=1.5)
    controlar_pinza(abrir=False)
    mover(POSE_BUSQUEDA)
    mover(DESTINO_REPARTO)
    mover(DESTINOS[color])
    controlar_pinza(abrir=True)
    mover(POSE_HOME)


# ── Hilo de Bucle Automático Continuous ─────────────────────────────
def flujo_bucle(log_widget):
    with log_widget:
        print("[BUCLE] Modo automático iniciado.")
    
    mover(POSE_BUSQUEDA)
    color_previo = None
    tiempo_estable = None

    while loop_activo.is_set():
        with candado:
            det = ultima_deteccion

        if det:
            color = det[0]
            if color == color_previo:
                # Requiere que el objeto se mantenga estable 1 segundo antes de recoger
                if time.time() - tiempo_estable >= 1.0:
                    with log_widget:
                        print(f"[BUCLE] {color} detectado de forma estable. Procesando...")
                    
                    ejecutar_pick_and_place(color)
                    
                    color_previo = None
                    tiempo_estable = None
                    
                    if loop_activo.is_set():
                        mover(POSE_BUSQUEDA)
            else:
                color_previo = color
                tiempo_estable = time.time()
        else:
            color_previo = None
            tiempo_estable = None

        time.sleep(0.05)

    with log_widget:
        print("[BUCLE] Modo automático detenido.")


# ── Interfaz de Usuario ─────────────────────────────────────────────
widget_video = widgets.Image(format="jpeg", width=480, height=360)
out_log = widgets.Output()

btn_cam_start  = widgets.Button(description="Iniciar Cámara", button_style="success")
btn_cam_stop   = widgets.Button(description="Cerrar Cámara", button_style="warning")
btn_ejecutar   = widgets.Button(description="Ejecutar Una Vez", button_style="primary")
btn_loop_start = widgets.Button(description="Iniciar Bucle", button_style="info")
btn_loop_stop  = widgets.Button(description="Parar Bucle", button_style="danger")

def on_cam_start(_):
    if not camara_activa.is_set():
        camara_activa.set()
        threading.Thread(target=flujo_camara, args=(widget_video, out_log), daemon=True).start()

def on_cam_stop(_):
    loop_activo.clear()
    camara_activa.clear()

def on_ejecutar(_):
    if loop_activo.is_set():
        with out_log:
            print("[AVISO] Detén el bucle automático antes de ejecutar manualmente.")
        return
    btn_ejecutar.disabled = True
    with out_log:
        mover(POSE_BUSQUEDA)
        time.sleep(1.0)
        with candado:
            det = ultima_deteccion
        if det:
            print(f"Objeto detectado: {det[0]}. Moviendo...")
            ejecutar_pick_and_place(det[0])
        else:
            print("No se detectó ningún objeto.")
    btn_ejecutar.disabled = False

def on_loop_start(_):
    if not camara_activa.is_set():
        with out_log:
            print("[AVISO] Enciende la cámara antes de iniciar el bucle.")
        return
    if not loop_activo.is_set():
        loop_activo.set()
        threading.Thread(target=flujo_bucle, args=(out_log,), daemon=True).start()

def on_loop_stop(_):
    loop_activo.clear()

btn_cam_start.on_click(on_cam_start)
btn_cam_stop.on_click(on_cam_stop)
btn_ejecutar.on_click(on_ejecutar)
btn_loop_start.on_click(on_loop_start)
btn_loop_stop.on_click(on_loop_stop)

display(
    widgets.VBox([
        widgets.HBox([btn_cam_start, btn_cam_stop]),
        widgets.HBox([btn_ejecutar, btn_loop_start, btn_loop_stop]),
        widget_video,
        out_log
    ])
)