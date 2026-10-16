#!/usr/bin/env python3
"""Verifica la coherencia de la cadena de decisión SIN ROS 2 ni un LAYA real.

Se enfoca en los arreglos: que nunca se ejecute una orden "desconocida", que una frase con
algo prohibido (p.ej. tijera) jamás quede permitida aunque el modelo diga que sí, y que una
respuesta ilegible de LAYA haga fallar la llamada (para caer al clasificador local) en vez de
colarse con valores por defecto.

    python herramientas/verificar_decisiones.py

Corre en cualquier máquina con Python: no importa rclpy. Si `requests` no está instalado, los
casos que hablan con cliente_laya se saltan y el resto se comprueba igual.
"""

import os
import sys
import unittest.mock as mock

# La consola de Windows suele ser cp1252 y no sabe imprimir '→' ni '✅'; forzamos UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'src', 'arm_broker'))
from arm_broker import clasificador_palabras_clave as clasificador   # noqa: E402
from arm_broker import decisiones                                    # noqa: E402

try:
    from arm_broker import cliente_laya
    HAY_CLIENTE = True
except ImportError as e:            # p.ej. sin `requests`
    HAY_CLIENTE = False
    print(f'aviso: no se pudo importar cliente_laya ({e!r}); sus casos se saltan')

_res = []


def comprobar(nombre, condicion):
    _res.append((nombre, bool(condicion)))
    print(f'  [{"ok" if condicion else "MAL"}] {nombre}')


# Respuesta HTTP falsa para probar preguntar() sin servidor real
class _RespuestaFalsa:
    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def raise_for_status(self):
        pass

    def json(self):
        return self._cuerpo


OBJETOS = ['cubo', 'cilindro', 'esfera']
COLORES = ['rojo', 'verde', 'azul', 'amarillo']
ACCIONES = ['agarrar', 'soltar', 'mover', 'detener']


def preguntar_con(cuerpo):
    """Llama a cliente_laya.preguntar() con un requests.post simulado"""
    with mock.patch.object(cliente_laya.requests, 'post',
                           return_value=_RespuestaFalsa(cuerpo)):
        return cliente_laya.preguntar('http://x', '', 'frase', 1.0,
                                      OBJETOS, COLORES, ACCIONES)


def main():
    print('1) Red de seguridad de decisiones.aplicar_reglas()')
    # Una frase con palabra prohibida nunca queda permitida, aunque el modelo diga que sí
    d = {'accion': 'agarrar', 'objeto': 'desconocido', 'color': 'ninguno',
         'prioridad': 1, 'permitido': True, 'motivo': ''}
    decisiones.aplicar_reglas(d, 'agarra la tijera')
    comprobar('"agarra la tijera" con permitido=True de LAYA → permitido=False',
              d['permitido'] is False and bool(d['motivo']))

    # Acción no reconocida → no permitida (es el caso que antes se colaba)
    d = {'accion': 'desconocido', 'objeto': 'cubo', 'color': 'azul',
         'prioridad': 1, 'permitido': True, 'motivo': ''}
    decisiones.aplicar_reglas(d, 'texto raro')
    comprobar('acción "desconocido" con permitido=True → permitido=False',
              d['permitido'] is False and bool(d['motivo']))

    # Una orden válida sigue permitida (no rompimos nada)
    d = {'accion': 'mover', 'objeto': 'cubo', 'color': 'azul',
         'prioridad': 1, 'permitido': True, 'motivo': ''}
    decisiones.aplicar_reglas(d, 'mueve el cubo azul')
    comprobar('"mueve el cubo azul" válida → sigue permitida',
              d['permitido'] is True)

    print('2) decisiones.accion_reconocida() (gate para descartar la respuesta de LAYA)')
    comprobar('mover → True', decisiones.accion_reconocida({'accion': 'mover'}) is True)
    comprobar('DESCONOCIDO (mayúsculas) → False',
              decisiones.accion_reconocida({'accion': 'DESCONOCIDO'}) is False)
    comprobar('"llevar" (no está en la lista cerrada) → False',
              decisiones.accion_reconocida({'accion': 'llevar'}) is False)

    print('3) Clasificador local (regresión)')
    d = clasificador.clasificar('agarra el cubo rojo')
    comprobar('"agarra el cubo rojo" → agarrar/cubo/rojo permitido',
              d['accion'] == 'agarrar' and d['objeto'] == 'cubo'
              and d['color'] == 'rojo' and d['permitido'] is True)
    # "lleva el cubo azul" con el clasificador local SÍ se reconoce como mover: por eso, si LAYA
    # no la reconoce, el respaldo la ejecuta con una decisión coherente (no "desconocido")
    d = clasificador.clasificar('lleva el cubo azul')
    comprobar('"lleva el cubo azul" → mover/cubo/azul permitido (respaldo)',
              d['accion'] == 'mover' and d['permitido'] is True)
    d = clasificador.clasificar('detente')
    comprobar('"detente" → detener permitido',
              d['accion'] == 'detener' and d['permitido'] is True)
    d = clasificador.clasificar('tijera')
    comprobar('"tijera" → permitido=False',
              d['permitido'] is False)

    if HAY_CLIENTE:
        print('4) cliente_laya.preguntar() con respuestas simuladas')
        # Respuesta correcta: se normaliza (mayúsculas/espacios) contra las listas cerradas
        dec, _ = preguntar_con({'answers': {
            'accion': 'Mover', 'objeto': ' Cubo ', 'color': 'AZUL',
            'prioridad': 2, 'permitido': 'sí'}})
        comprobar('normaliza accion/objeto/color y lee permitido="sí"',
                  dec['accion'] == 'mover' and dec['objeto'] == 'cubo'
                  and dec['color'] == 'azul' and dec['permitido'] is True)

        # Un valor fuera de la lista nunca se acepta a ciegas
        dec, _ = preguntar_con({'answers': {
            'accion': 'desconocida', 'objeto': 'libro', 'color': 'fucsia',
            'prioridad': 1, 'permitido': True}})
        comprobar('acción/objeto/color inventados → desconocido/desconocido/ninguno',
                  dec['accion'] == 'desconocido' and dec['objeto'] == 'desconocido'
                  and dec['color'] == 'ninguno')

        # Faltando el campo permitido, el fail-safe es False (nunca True)
        dec, _ = preguntar_con({'answers': {
            'accion': 'mover', 'objeto': 'cubo', 'color': 'azul', 'prioridad': 1}})
        comprobar('sin campo permitido → permitido=False (fail-safe)',
                  dec['permitido'] is False and bool(dec['motivo']))

        # JSON que no trae ninguno de los campos pedidos → excepción (dispara el respaldo local)
        lanzo = False
        try:
            preguntar_con({'status': 'ok', 'mensaje': 'no entendí nada'})
        except ValueError:
            lanzo = True
        comprobar('JSON sin ninguno de los 5 campos → lanza excepción', lanzo)

    malos = [n for n, ok in _res if not ok]
    print()
    print(f'{len(_res) - len(malos)}/{len(_res)} comprobaciones OK')
    if malos:
        print('FALLARON:')
        for n in malos:
            print(f'  - {n}')
        return 1
    print('Todo coherente ✅')
    return 0


if __name__ == '__main__':
    sys.exit(main())
