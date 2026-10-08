#!/usr/bin/env python3
""" Prueba rápida y SIN ROS 2 contra el servidor LAYA — correr esto PRIMERO, el día del examen,
apenas tengan la IP y el puerto reales, antes de confiar en interprete_ordenes.py.

Para qué sirve: LAYA no documenta públicamente la forma exacta del JSON que devuelve.
Este script hace una pregunta de prueba y muestra la respuesta cruda completa, para que
puedan confirmar (o ajustar) cómo cliente_laya._extraer() lee los campos accion/objeto/
color/prioridad/permitido.

Uso:
    export LAYA_API_KEY=...   # solo si el servidor del laboratorio pide clave
    python3 probar_laya.py http://IP:PUERTO "agarra el cubo rojo"
"""

import json
import os
import sys
import time

import requests


def main():
    if len(sys.argv) < 3:
        print('uso: python3 probar_laya.py http://IP:PUERTO "frase a probar"', file=sys.stderr)
        sys.exit(2)

    url = sys.argv[1].rstrip('/')
    frase = sys.argv[2]
    api_key = os.environ.get('LAYA_API_KEY', '')
    headers = {'content-type': 'application/json'}
    if api_key:
        headers['authorization'] = f'Bearer {api_key}'

    print(f'\n{"=" * 60}\n1) GET {url}/health\n{"=" * 60}')
    t0 = time.time()
    try:
        r = requests.get(f'{url}/health', headers=headers, timeout=5.0)
        print(f'status={r.status_code}  ({(time.time() - t0) * 1000:.0f} ms)')
        print(r.text[:500])
    except Exception as e:
        print(f'ERROR: no se pudo conectar a {url}/health — {e!r}')
        print('Revisen IP/puerto, que estén en la misma red, y que el server esté arriba.')
        sys.exit(1)

    payload = {
        'state': {'body': frase},
        'questions': {
            'accion': {'type': 'choice', 'instructions': '¿Qué acción pide la frase?',
                       'criteria': ['agarrar', 'soltar', 'mover', 'detener', 'desconocido']},
            'objeto': {'type': 'choice', 'instructions': '¿Sobre qué objeto actúa?',
                       'criteria': ['cubo', 'cilindro', 'esfera', 'desconocido']},
            'color': {'type': 'choice', 'instructions': '¿De qué color es el objeto?',
                      'criteria': ['rojo', 'verde', 'azul', 'amarillo', 'ninguno']},
            'prioridad': {'type': 'score', 'instructions': '¿Qué tan urgente suena, 0 a 3?',
                          'criteria': ['0', '1', '2', '3']},
            'permitido': {'type': 'noul', 'instructions': '¿Es una orden segura de ejecutar?'},
        },
    }

    print(f'\n{"=" * 60}\n2) POST {url}/v1/systemone\n   frase: "{frase}"\n{"=" * 60}')
    t0 = time.time()
    r = requests.post(f'{url}/v1/systemone', json=payload, headers=headers, timeout=10.0)
    dt = time.time() - t0
    print(f'status={r.status_code}  ({dt * 1000:.0f} ms)\n')
    print('--- respuesta cruda completa (revisar aquí los nombres de campo reales) ---')
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    print(f'\n{"=" * 60}\nSi los campos no coinciden con choice/score/noul/label/value/answer,')
    print('ajusten la función _extraer() en arm_broker/cliente_laya.py')
    print(f'{"=" * 60}\n')


if __name__ == '__main__':
    main()
