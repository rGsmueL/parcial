#!/usr/bin/env python3
"""Escribe el contenido de los items 2 y 3 del Reto 2 dentro de Informe.docx.

No se usa python-docx a propósito. El .docx del curso sale de Google Docs y trae
fuentes embebidas y estilos propios; reconstruirlo con otra libreria cambia el
formato de todo el documento, incluidas las tablas que ya estaban escritas del
item 1. Aqui solo se toca word/document.xml y se reutiliza el XML que el propio
documento ya usa: Calibri 11, espaciado 276/200, tablas Table1 de 8500 dxa con
cabecera sombreada d9d9d9.

    python3 completar_informe.py

Inserta el bloque del item 2 justo antes del parrafo rotulado ITEM 3, y el del
item 3 justo antes de ITEM 4. Los dos puntos de anclaje son los w14:paraId de
esos parrafos, que no cambian. El script se niega a correr dos veces: si ya
encuentra el titulo de la primera seccion que escribe, avisa y sale.

Antes de tocar nada deja una copia del original junto al .docx, con sufijo
.bak, por si hay que volver atras.
"""

import os
import re
import shutil
import sys
import zipfile
from xml.etree import ElementTree

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DOCX = os.path.join(RAIZ, 'Informe.docx')
BACKUP = DOCX + '.bak'

# w14:paraId de los parrafos que ya existen y despues de los cuales hay que
# escribir. ITEM 3 va antes que su rotulo; ITEM 4 va antes que el suyo.
ANCLA_ITEM2 = '000000C7'   # parrafo "ITEM 3"
ANCLA_ITEM3 = '000000C9'   # parrafo "ITEM 4"
MARCA = '2.1 Qu\u00e9 resuelve este \u00edtem'

# El primer paraId libre del documento es 000000CA; arrancamos lejos para no
# chocar con nada.
PID = [0x200]

# Ancho util de la hoja: 11906 twips menos los margenes 1701 + 1701.
ANCHO_TABLA = 8500

RSID = ('<w:p w:rsidR="00000000" w:rsidDel="00000000" w:rsidP="00000000" '
        'w:rsidRDefault="00000000" w:rsidRPr="00000000" w14:paraId=')


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def pid():
    PID[0] += 1
    return '%08X' % PID[0]


def _run(txt, negrita=False, mono=False, cursiva=False, tam=22):
    fuente = ('<w:rFonts w:ascii="Consolas" w:cs="Consolas" w:eastAsia="Consolas" '
              'w:hAnsi="Consolas"/>') if mono else (
              '<w:rFonts w:ascii="Calibri" w:cs="Calibri" w:eastAsia="Calibri" '
              'w:hAnsi="Calibri"/>')
    extra = ''
    if negrita:
        extra += '<w:b w:val="1"/><w:bCs w:val="1"/>'
    if cursiva:
        extra += '<w:i w:val="1"/><w:iCs w:val="1"/>'
    rpr = '<w:rPr>%s%s<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (
        fuente, extra, tam, tam)
    partes = []
    for i, trozo in enumerate(txt.split('\n')):
        if i:
            partes.append('<w:r>%s<w:br/></w:r>' % rpr)
        if trozo:
            partes.append(
                '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, esc(trozo)))
    return ''.join(partes)


def _ppr(mono=False, antes=200, interlineado=276, sombreado=False):
    sombra = '<w:shd w:fill="f2f2f2" w:val="clear"/>' if sombreado else ''
    return ('<w:pPr>%s<w:spacing w:after="%d" w:line="%d" w:lineRule="auto"/>'
            '</w:pPr>' % (sombra, antes, interlineado))


def parrafo(txt, **kw):
    mono = kw.get('mono', False)
    return ('%s"%s">%s<w:r>%s</w:r></w:p>' % (
        RSID, pid(), _ppr(mono=mono, antes=kw.get('antes', 200)),
        _run(txt, negrita=kw.get('negrita', False), mono=mono,
             cursiva=kw.get('cursiva', False), tam=kw.get('tam', 22))))


def titulo(txt):
    return parrafo(txt, negrita=True, tam=24, antes=280)


def sub(txt):
    return parrafo(txt, negrita=True)


def vineta(txt):
    return ('%s"%s"><w:pPr><w:spacing w:after="60" w:line="276" w:lineRule="auto"/>'
            '<w:ind w:left="360" w:hanging="180"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:cs="Calibri" w:eastAsia="Calibri" '
            'w:hAnsi="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
            '<w:t xml:space="preserve">\u2022\u2003%s</w:t></w:r></w:p>' % (RSID, pid(), esc(txt)))


def codigo(lineas):
    """Bloque monoespaciado. Una linea por parrafo, sin espacio entre ellas."""
    out = []
    for ln in lineas:
        out.append('%s"%s"><w:pPr><w:shd w:fill="f5f5f5" w:val="clear"/>'
                   '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                   '<w:r>%s</w:r></w:p>' % (
                       RSID, pid(),
                       _run(ln if ln else ' ', mono=True, tam=16)))
    # Una linea en blanco al final para que el bloque no se coma el parrafo
    # siguiente, que Word necesita como separador.
    out.append('%s"%s"><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
               '</w:pPr></w:p>' % (RSID, pid()))
    return ''.join(out)


def _tc(txt, ancho, cabecera=False, mono=False):
    sombra = '<w:shd w:fill="d9d9d9" w:val="clear"/>' if cabecera else ''
    bordes = ('<w:tcBorders><w:top w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
              '<w:left w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
              '<w:bottom w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
              '<w:right w:color="000000" w:space="0" w:sz="4" w:val="single"/></w:tcBorders>')
    cuerpo = ('%s"%s">%s<w:r>%s</w:r></w:p>' % (
        RSID, pid(), _ppr(antes=40, interlineado=240),
        _run(txt, negrita=cabecera, mono=mono, tam=16 if mono else 20)))
    return ('<w:tc><w:tcPr>%s%s<w:tcW w:w="%d" w:type="dxa"/></w:tcPr>%s</w:tc>'
            % (bordes, sombra, ancho, cuerpo))


def tabla(cabeceras, filas, anchos=None, mono_cols=()):
    n = len(cabeceras)
    if anchos is None:
        anchos = [ANCHO_TABLA // n] * n
    grid = ''.join('<w:gridCol w:w="%d"/>' % a for a in anchos)
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="Table1"/>'
           '<w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/>'
           '<w:tblBorders><w:top w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
           '<w:left w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
           '<w:bottom w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
           '<w:right w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
           '<w:insideH w:color="000000" w:space="0" w:sz="4" w:val="single"/>'
           '<w:insideV w:color="000000" w:space="0" w:sz="4" w:val="single"/></w:tblBorders>'
           '<w:tblLayout w:type="fixed"/><w:tblLook w:val="0400"/></w:tblPr>'
           '<w:tblGrid>%s</w:tblGrid>' % (sum(anchos), grid)]
    out.append('<w:tr><w:trPr><w:cantSplit w:val="0"/><w:tblHeader w:val="0"/></w:trPr>'
               + ''.join(_tc(h, anchos[i], cabecera=True, mono=(i in mono_cols))
                         for i, h in enumerate(cabeceras)) + '</w:tr>')
    for fila in filas:
        celdas = []
        for i, v in enumerate(fila):
            celdas.append(_tc(v, anchos[i], mono=(i in mono_cols)))
        out.append('<w:tr><w:trPr><w:cantSplit w:val="0"/><w:tblHeader w:val="0"/>'
                   '</w:trPr>' + ''.join(celdas) + '</w:tr>')
    out.append('</w:tbl>')
    # Word exige un parrafo entre tablas y al final del cuerpo.
    out.append(parrafo(''))
    return ''.join(out)


# ---------------------------------------------------------------- item 2 ----

def item2():
    p = []
    a = p.append

    a(titulo(MARCA))
    a(parrafo('El enunciado plantea un problema que no se ve. Si los cuatro integrantes '
              'publican directo en /joint_states el JetCobot no lanza excepción: el driver '
              'obedece el último mensaje que llegó y el brazo acaba en poses que nadie '
              'pidió. No hay error en ninguna terminal, solo un robot que se mueve raro. '
              'La causa es que los cuatro escriben en el mismo tópico al mismo tiempo.'))
    a(parrafo('Lo que hicimos fue meter un broker en el medio. Los clientes dejaron de '
              'hablarle al driver y ahora hablan con arm_broker, que es el único nodo que '
              'publica en /joint_states. El orden en que se atienden los pedidos, la '
              'validación de que un objetivo sea alcanzable y la telemetría de la cola '
              'viven todos dentro de ese nodo. Este ítem cuenta cómo quedó, qué decisiones '
              'tomamos y qué pruebas corrimos para confirmar que ninguna de las reglas '
              'se rompe.'))
    a(parrafo('Dejemos claro desde el principio qué es lo que NO se hizo: no escribimos un '
              'resolvedor de cinemática inversa. Para el ítem 2 la cinemática inversa es '
              'irrelevante; el broker solo necesita saber si una pose es alcanzable y qué '
              'tan lejos está de donde está el brazo ahora, y eso lo responde la cinemática '
              'directa del ítem 1.'))

    a(titulo('2.2 Topología del experimento'))
    a(parrafo('Son cinco máquinas. Cada Raspberry Pi levanta un solo cliente y nada más: '
              'nunca importa sensor_msgs, nunca toca /joint_states. La quinta máquina es el '
              'Jetson del brazo, y ahí se abren dos terminales, una con el driver '
              'sync_plan_nx y otra con el broker. El driver y el broker no necesitan verse '
              'por red porque comparten máquina; los clientes sí los alcanzan por DDS.'))
    a(tabla(
        ['Máquina', 'Qué levanta', 'client_id', 'Prioridad'],
        [['Raspberry de Samuel', 'cliente.py (1 nodo)', 'samuel', '1'],
         ['Raspberry de Joaquín', 'cliente.py (1 nodo)', 'joaquin', '2'],
         ['Raspberry de Maykol', 'cliente.py (1 nodo)', 'maykol', '3'],
         ['Raspberry de Wilmer', 'cliente.py (1 nodo)', 'wilmer', '4'],
         ['Jetson, terminal 1', 'jetcobot_driver sync_plan_nx', '\u2014', '\u2014'],
         ['Jetson, terminal 2', 'arm_broker broker', '\u2014', '\u2014']],
        anchos=[2400, 2600, 1900, 1600]))
    a(parrafo('La convención de prioridad la declara el propio action: uint8 de 0 a 255 y '
              'MAYOR NÚMERO ES MÁS URGENTE. Repartimos 1 a 4 para que las cuatro cifras '
              'aparezcan en /arm/queue_state y en el CSV de rechazos, y para que en el ítem '
              '3 se pueda ver cliente por cliente quién sufrió más con cada política.'))
    a(sub('Variables de red'))
    a(parrafo('Las cinco máquinas toman las variables de red del bloque copiable de '
              'PASOS.txt (no se usa config/equipo.env). El dominio es 43 '
              'porque el enunciado pide 42 más el número de equipo y ours es el equipo 1. '
              'Un detalle que nos costó un rato: ROS_DOMAIN_ID tiene que ser el mismo en las '
              'cinco, y si no lo es las máquinas simplemente no se ven, sin error visible.'))
    a(codigo([
        'export ROS_DOMAIN_ID=43          # 42 + 1 (equipo 1)',
        'export ROS_LOCALHOST_ONLY=0',
        'export RMW_IMPLEMENTATION=rmw_fastrtps_cpp',
        'export ROS_DISCOVERY_SERVER="172.51.1.28:11811"   # IP del Jetson',
        'ros2 daemon stop && ros2 daemon start',
    ]))
    a(parrafo('Después de exportar hay que reiniciar el daemon. Si ros2 node list sale '
              'vacío, el problema es de descubrimiento y no del robot; por eso el script '
              'verificar_publicadores.py incluye el recordatorio en su mensaje de error.'))

    a(titulo('2.3 Paquetes ROS 2'))
    a(parrafo('Son dos paquetes dentro del mismo workspace. El de interfaces va aparte '
              'porque es la dependencia: el broker, el cliente y los scripts de análisis '
              'importan el .action y el .msg, y si estuvieran en el mismo paquete no '
              'habría forma de compilar el action server sin compilar antes el cliente.'))
    a(tabla(
        ['Paquete', 'Qué contiene'],
        [['arm_broker_interfaces', 'action/MoveArm.action y msg/QueueState.msg'],
         ['arm_broker', 'broker.py, cliente.py, fk.py, politicas.py'],
         ['', 'package.xml y setup.py, más resource/arm_broker']],
        anchos=[2600, 5900]))
    a(sub('MoveArm.action'))
    a(parrafo('Un goal es una pose articular más quién la manda y cuánta urgencia tiene. El '
              'resultado devuelve el tiempo que pasó en la cola y el que tardó en moverse, '
              'que son los dos números que después el ítem 3 promedia.'))
    a(tabla(
        ['Sección', 'Campo', 'Tipo', 'Para qué sirve'],
        [['Goal', 'joint_positions', 'float64[]', 'q1..q6 en radianes'],
         ['Goal', 'client_id', 'string', 'Identifica al cliente en la telemetría'],
         ['Goal', 'priority', 'uint8', '0..255, mayor = más urgente'],
         ['Result', 'success', 'bool', 'Falso también si se cancela'],
         ['Result', 'message', 'string', 'ok, o el motivo del rechazo o del aborto'],
         ['Result', 'wait_time_s', 'float64', 'Espera en cola (métrica del ítem 3)'],
         ['Result', 'exec_time_s', 'float64', 'Duración del movimiento'],
         ['Feedback', 'state', 'string', 'QUEUED o EXECUTING'],
         ['Feedback', 'queue_position', 'int32', 'Lugar en la cola, 1-based'],
         ['Feedback', 'elapsed_s', 'float64', 'Transcurrido desde que le tocó']],
        anchos=[1150, 1900, 1150, 4300]))
    a(sub('QueueState.msg'))
    a(parrafo('Es la telemetría. Se publica a 5 Hz en /arm/queue_state y es el CSV que después '
              'se convierte en todas las métricas del ítem 3, así que el mensaje lleva tanto '
              'la foto del instante como los contadores acumulados.'))
    a(tabla(
        ['Campo', 'Tipo', 'Contenido'],
        [['stamp', 'builtin_interfaces/Time', 'Hora de la muestra'],
         ['executing_client', 'string', 'Cliente que tiene el brazo ahora'],
         ['executing_goal_id', 'string', 'Identificador de ese goal'],
         ['executing_elapsed_s', 'float64', 'Cuánto lleva ejecutándose'],
         ['queue_length', 'int32', 'Pedidos esperando'],
         ['queued_goal_ids', 'string[]', 'Identificadores, en orden de cola'],
         ['queued_clients', 'string[]', 'Quién mandó cada uno'],
         ['queued_priorities', 'uint8[]', 'Prioridad de cada uno'],
         ['queued_wait_s', 'float64[]', 'Espera actual de cada uno'],
         ['total_accepted', 'int32', 'Aceptados acumulados'],
         ['total_rejected', 'int32', 'Rechazados acumulados'],
         ['total_completed', 'int32', 'Completados con éxito']],
        anchos=[2300, 2200, 4000]))

    a(titulo('2.4 Encolar no es ejecutar'))
    a(parrafo('Esta es la parte que más nos costó entender al principio, así que va con '
              'mucho detalle. handle_accepted_callback solo crea un Pedido y lo mete en la '
              'lista self.pendientes. No mira el brazo, no publica nada, no calcula nada de '
              'la pose. Lo único que mueve el JetCobot es el worker, y el worker es un timer '
              'periódico de 20 ms.'))
    a(parrafo('Usamos tres grupos de callbacks distintos en vez de uno:'))
    a(vineta('grupo_entrada es ReentrantCallbackGroup y lo lleva el ActionServer. Tiene que '
             'ser reentrante porque tiene que poder validar un goal nuevo mientras '
             'execute_callback del goal anterior sigue moviendo el brazo. Con un grupo '
             'mutuamente excluyente, el broker no aceptaría el goal 2 hasta terminar el 1.'))
    a(vineta('grupo_worker es MutuallyExclusiveCallbackGroup y lo lleva el timer del worker. '
             'Aquí la exclusión mutua es exactamente lo que queremos: dos vueltas del timer '
             'nunca se solapan.'))
    a(vineta('grupo_estado es otro MutuallyExclusiveCallbackGroup, separado del del worker, '
             'para el timer de 200 ms que publica /arm/queue_state. Lo separamos por una '
             'razón concreta: el worker se queda bloqueado dentro de pedido.fin.wait() los '
             '1.5 s completos de cada movimiento. Si la telemetría compartiera su grupo, '
             'dejaría de publicar justo durante el movimiento, que es cuando la cola está '
             'más interesante de mirar.'))
    a(parrafo('Por eso el executor es MultiThreadedExecutor con num_threads=4. El worker ocupa '
              'un hilo esperando, execute_callback corre en otro, y todavía hacen falta hilos '
              'para admitir goals y para publicar la telemetría. Con el SingleThreadedExecutor '
              'de la documentación el nodo no avanzaba.'))
    a(parrafo('La exclusión mutua no es un flag ni un semáforo: es estructural. El worker no '
              'regresa de _atender hasta que pedido.fin está activo, y execute_callback '
              'siempre lo activa en su finally. Aunque se dispararan dos timers a la vez, el '
              'grupo no lo permite; y aunque el grupo fallara, el segundo worker vería '
              'ejecutando != None y no desencolaría nada.'))
    a(parrafo('El lock (self.lock) es otra cosa y no sustituye al grupo: protege las listas y '
              'los contadores. Se toma corto, solo para copiar o mutar el estado, y '
              'deliberadamente nunca se retiene durante pedido.fin.wait(), porque si se '
              'hacia goal_callback se bloquearía y no admitiría nada.'))

    a(titulo('2.5 Camino de un goal'))
    a(parrafo('El mismo recorrido para cualquier cliente, sin importar su prioridad: el goal '
              'se admite, se encola, espera su turno, se ejecuta solo y devuelve su resultado. '
              'Lo que cambia entre clientes es en qué vuelta del worker sale de la cola.'))
    a(codigo([
        'CLIENTE (Raspberry)     arm_broker                       WORKER / DRIVER',
        '    |                       |                                 |',
        '    |-- send_goal_async --->|                                 |',
        '    |                       |-- goal_callback                  |',
        '    |                       |    fk.dentro_de_limites    ok    |',
        '    |                       |    fk.dentro_del_workspace ok   |',
        '    |                       |    fk.paso_articular <= 1.6 ok   |',
        '    |                       |    pendientes + reservados < 20 |',
        '    |<-- ACCEPT ------------|                                 |',
        '    |                       |-- handle_accepted_callback       |',
        '    |                       |     Pedido(...) -> pendientes    |',
        '    |                       |                                 |',
        '    |<== QUEUED(pos,t) =====|== /arm/queue_state 5 Hz =======>|',
        '    |                       |                                 |',
        '    |                       |                  [timer 20 ms]  |',
        '    |                       |                   _worker()      |',
        '    |                       |                  idx = politica. |',
        '    |                       |                  siguiente(pend) |',
        '    |                       |                  ejecutando = p |',
        '    |                       |                  t_inicio_ejec   |',
        '    |                       |-- goal_handle.execute() ------->|',
        '    |                       |               execute_callback   |',
        '    |                       |                 mover(q) x N     |',
        '    |                       |                -> /joint_states  |',
        '    |<== EXECUTING =========|== feedback ====================>|',
        '    |                       |<-- pedido.fin.set() ------------|',
        '    |                       |   ejecutando = None             |',
        '    |<-- Result(success, wait_time_s, exec_time_s) ------------|',
    ]))
    a(parrafo('La última línea del worker es la que importa para el ítem 3: wait_time_s se '
              'calcula con t_inicio_ejec menos t_llegada, o sea tiempo en cola, sin contar '
              'los 1.5 s de ejecución.'))

    a(titulo('2.6 Admisión: la cinemática hace de portero'))
    a(parrafo('goal_callback tiene que ser barata e inmediata. Solo hace aritmética con fk.py, '
              'no espera al brazo y no publica nada, así que mientras el grupo 1 se mueve el '
              'grupo 4 puede estar admitiendo goals sin tocarse. El orden de los chequeos no '
              'es arbitrario:'))
    a(tabla(
        ['#', 'Chequeo', 'Causa si falla'],
        [['1', 'Los seis q_i son float finitos (math.isfinite)', 'limite'],
         ['2', 'fk.dentro_de_limites(q): cada q_i dentro de su rango', 'limite'],
         ['3', 'fk.dentro_del_workspace(q): 80 <= r <= 480 mm y z >= 0', 'workspace'],
         ['4', 'fk.paso_articular(q_actual, q) <= paso_max_rad', 'paso'],
         ['5', 'len(pendientes) + reservados < cola_max', 'cola_llena']],
        anchos=[500, 6300, 1700]))
    a(parrafo('El orden importa por dos razones. Primero, dentro_del_workspace llama a fk(q), '
              'que exige exactamente seis valores; si el goal llega con cinco o con un NaN, '
              'los comparadores de la FK no darían una respuesta útil y por eso los finitos y '
              'la longitud van primero. Segundo, el chequeo de límites va antes que el de '
              'workspace para que una pose que falla por ambos se reporte con la causa más '
              'específica, que es limite.'))
    a(parrafo('Un detalle del quinto chequeo que nos costó una carrera: comprobar el cupo y '
              'reservarlo tienen que ser la misma operación dentro del lock. Si fueran dos, '
              'cuatro clientes que llegan en el mismo instante podrían ver el mismo hueco '
              'libre y la cola se pasaría de cola_max. Por eso existe el contador '
              'reservados, que es la reserva optimista que se confirma en '
              'handle_accepted_callback.'))
    a(sub('Sobre paso_max_rad'))
    a(parrafo('El paso articular se mide contra self.q_actual, que es la última pose realmente '
              'publicada, no contra lo que el cliente cree que hay. Ese límite es lo que '
              'impide que el brazo salte entre dos poses lejanas y termine dañando los '
              'motores. Para las corridas comparativas usamos 1.6 rad y no el 1.2 que trae el '
              'broker por defecto, y la razón es concreta: en carga.csv hay cuatro saltos '
              'consecutivos mayores a 1.2 rad, el mayor de 1.454. Con 1.2 esos cuatro goals '
              'se rechazarían por un motivo que no tiene nada que ver con la política que '
              'estamos midiendo, y contaminarían la comparación.'))
    a(sub('paso_al_ejecutar: la segunda validación'))
    a(parrafo('El paso se midió en la admisión, contra la pose que había en ese momento. Pero '
              'el pedido puede quedarse minutos en la cola mientras los de delante mueven el '
              'brazo, y cuando por fin le toca, el salto desde la pose actual ya no es el que '
              'se midió. Por eso execute_callback repite la comparación contra q_actual antes '
              'de interpolar, y si ahora excede el límite devuelve un resultado abortado con '
              'el motivo. Esta causa no suma a n_aceptados ni a n_rechazados, porque esos '
              'contadores cuentan lo que decidió goal_callback.'))

    a(titulo('2.7 Registro de rechazos'))
    a(parrafo('Todo rechazo va al log y a un CSV, siempre con causa y motivo legible. El CSV lo '
              'escribe el propio broker desde _registrar_rechazo, con un lock aparte para el '
              'caso de que varios goals se rechacen en el mismo instante. Se puede desactivar '
              'dejando vacío el parámetro archivo_rechazos.'))
    a(codigo([
        't_unix,client_id,priority,causa,motivo,joint_positions',
        '1757190001.412,samuel,1,limite,3_Joint fuera de rango: 3.0 rad,'
        ' limite [-2.53, 2.53],0.0000 0.0000 3.0000 0.0000 0.0000 0.0000',
        '1757190002.907,joaquin,2,workspace,efector demasiado cerca de la base,'
        '0.0000 2.3000 1.4000 0.0000 2.1000 -1.7000',
        '1757190004.318,wilmer,4,paso,paso articular de 1.80 rad desde la pose'
        ' actual, maximo 1.60,0.0000 0.0000 1.8000 0.0000 0.0000 0.0000',
    ]))
    a(parrafo('Estas tres filas no son de las corridas de 160 goals, que no rechazaron nada; '
              'son las que produce herramientas/validar_rechazos.py, que manda un goal que '
              'tripia cada causa por separado y después lee el CSV para confirmar que los tres '
              'motivos quedaron escritos. Nos pareció importante poder demostrar que el '
              'registro funciona sin depender de una corrida que quizá no rechace nada.'))

    a(titulo('2.8 Políticas de cola'))
    a(parrafo('El enunciado pedía FIFO más una de tres: prioridad estática, prioridad con '
              'envejecimiento, o round-robin entre clientes. Elegimos prioridad con '
              'envejecimiento. La razón es que de las tres es la única donde la urgencia no '
              'viene con una promesa de inanición: la prioridad estática deja al cliente menos '
              'urgente esperando indefinidamente en cuanto hay carga sostenida, y round-robin '
              'ignora la urgencia por completo, que para un brazo robótico no tiene sentido.'))
    a(sub('FIFO, la línea base'))
    a(parrafo('Atiende el menor t_llegada. Ignora la prioridad a propósito, y esa es la razón '
              'de que esté: si la segunda política se compara contra una base que ya es justa, '
              'toda diferencia se le puede atribuir a la prioridad y no a otra cosa.'))
    a(sub('Prioridad con envejecimiento'))
    a(parrafo('Cada pedido puntúa priority más espera_s dividida por tau, y sale el de mayor '
              'puntuación. El término espera_s / tau es el envejecimiento: la prioridad '
              'sola se desvanece mientras el pedido envejece, así que un goal de prioridad 1 '
              'que espere lo suficiente termina saliendo por delante de uno de prioridad 4 que '
              'acaba de llegar. El desempate es por antigüedad, no por posición en la lista, '
              'para que dos políticas con la misma puntuación no se desempaten por el orden '
              'del deque.'))
    a(codigo([
        'puntuacion(p) = p.priority + p.espera_s / tau',
        '',
        'tau = 12.0 s   (inyectado desde el broker; el default en el codigo es 8.0)',
        '',
        'con tau = 12 s: un pedido de prioridad 1 que lleve 24 s esperando',
        'iguala a uno de prioridad 3 recien llegado.',
    ]))
    a(sub('El contrato que siguen las dos'))
    a(codigo([
        'Politica.siguiente(pendientes) -> indice del candidato, o None',
        'Politica.atendido(pedido)      -> actualiza estado interno',
    ]))
    a(parrafo('Que devuelva el índice y no el objeto no es un detalle de estilo. El worker es '
              'quien saca el elemento de la lista, bajo el lock; la política solo elige. '
              'Además permite que herramientas/simular_corrida.py use el mismo politicas.py '
              'que corre el broker, y por eso la predicción del ítem 3 no puede apartarse '
              'del broker en un detalle de política.'))
    a(parrafo('Hay una sutileza con el orden de las llamadas que nos costó un rato de depurar. '
              'siguiente() se invoca antes de que se fije t_inicio_ejec, así que espera_s vale '
              'ahora menos t_llegada para todos los candidatos por igual. Si se llamara '
              'después, el que está a punto de salir tendría su espera congelada y la '
              'comparación dejaría de ser justa.'))

    a(titulo('2.9 Telemetría de la cola'))
    a(parrafo('Un timer de 0.2 s publica QueueState en /arm/queue_state. Toma una foto del '
              'estado bajo el lock, suelta el lock y publica afuera, para no retenerlo durante '
              'la serialización. Además del mensaje, cada goal en cola recibe un feedback '
              'QUEUED con su posición, que es lo que permite que un cliente muestre su lugar '
              'en la fila sin tener que suscribirse al tópico ni consultar nada.'))
    a(parrafo('Este mismo mensaje es el insumo del ítem 3: exportar_csv.py lo vuelca tal cual a '
              'un queue_state.csv, sin transformar nada, y metricas.py saca todas las métricas '
              'de ahí. Por eso guardamos queued_wait_s como arreglo y no solo un agregado: '
              'necesitamos poder separar las esperas por prioridad al final.'))

    a(titulo('2.10 El publicador único'))
    a(parrafo('Es el requisito eliminatorio, así que lo revisamos como tal. En todo el código '
              'del broker hay un solo create_publisher sobre /joint_states, en broker.py, y '
              'solo lo invoca mover(), que a su vez solo lo llama execute_callback. Los '
              'clientes no importan sensor_msgs en ninguna parte de cliente.py; no pueden, '
              'aunque quisieran, porque el paquete no se lo expone.'))
    a(parrafo('Para comprobarlo sin fiarnos de leer el código escribimos '
              'analisis/verificar_publicadores.py. Hace ros2 topic info /joint_states '
              '--verbose, cuenta los publicadores, extrae los nombres de nodo y cierra con '
              'código 1 si no hay exactamente uno o si el que hay no se llama arm_broker. Que '
              'devuelva código de salida es lo que lo hace utilizable dentro de un pipeline.'))
    a(sub('Lo que realmente hay que temerle'))
    a(parrafo('La métrica de la sección 5 del enunciado habla de "publicadores concurrentes" en '
              'el bag de /joint_states. Lo que se puede violar no es solo que dos pedidos se '
              'solapen en el tiempo, es que el brazo obediga mensajes intercalados de dos '
              'publicadores distintos. Por eso contar solapes no alcanza y lo que cuenta es '
              'el número de publicadores: uno solo significa que todo lo que llega al driver '
              'lo decidió el broker.'))

    a(titulo('2.11 Cancelación y errores'))
    a(parrafo('Un goal cancelado mientras esperaba no debe mover el brazo. Cada vuelta del '
              'worker empieza con _purgar_cancelados(), que saca de la lista los que tienen '
              'is_cancel_requested. Esos pedidos igual pasan por execute_callback, y no es '
              'redundancia: rclpy solo manda el Result al cliente desde ahí, así que si los '
              'borráramos sin más el cliente se quedaría esperando una respuesta que no '
              'llegaría nunca.'))
    a(parrafo('Si se cancela durante el movimiento, la comprobación se hace antes de cada uno '
              'de los N pasos de la interpolación, y el brazo se queda donde estaba. El '
              'resultado es success = false con el motivo, porque un goal cancelado no cuenta '
              'como completado.'))
    a(parrafo('Queda un caso más: si algo revienta dentro de _atender, el worker no puede '
              'morirse porque se caería todo el broker. _finalizar_con_error construye un '
              'Result fallido, lo guarda en el pedido y activa pedido.fin, de modo que ni el '
              'worker ni el cliente quedan colgados. El bloque finally de execute_callback '
              'además siempre hace pedido.fin.set(), incluso si la interpolación falla a '
              'mitad de camino.'))

    a(titulo('2.12 Cómo se corre'))
    a(codigo([
        '# --- Jetson, terminal 1: el driver del brazo',
        'source /opt/ros/humble/setup.bash',
        'ros2 run jetcobot_driver sync_plan_nx',
        '',
        '# --- Jetson, terminal 2: el broker',
        'ros2 run arm_broker broker --ros-args -p politica:=fifo',
        '    -p tau_envejecimiento_s:=12.0 -p cola_max:=20 -p paso_max_rad:=1.6',
        '    -p duracion_movimiento_s:=1.5 -p pasos_interpolacion:=10',
        '    -p archivo_rechazos:=rechazos.csv',
        '',
        '# --- cada Raspberry: un cliente',
        'ros2 run arm_broker cliente --ros-args -r __node:=cliente_samuel',
        '    -p client_id:=samuel -p priority:=1 -p traza:=carga.csv',
        '    -p modo:=secuencial -p pausa_s:=2.0 -p inicio_unix:=1757190000',
    ]))
    a(parrafo('El parámetro inicio_unix existe por una razón práctica: los cuatro ros2 run '
              'tardan distinto en levantar, y si el primero en arrancar se queda solo con el '
              'brazo dos minutos la corrida deja de ser simultánea. Pasando el mismo instante '
              'UNIX a los cuatro, todos empiezan a enviar en el mismo segundo.'))

    a(titulo('2.13 Verificaciones'))
    a(parrafo('Tres comprobaciones, todas ejecutables por cualquiera que clone el repo:'))
    a(tabla(
        ['Qué se comprueba', 'Cómo', 'Resultado'],
        [['Un solo publicador en /joint_states',
          'python3 analisis/verificar_publicadores.py',
          '1 publicador, nodo arm_broker. Código de salida 0'],
         ['Las tres causas de rechazo escriben su motivo',
          'python3 herramientas/validar_rechazos.py',
          'limite, workspace y paso presentes en rechazos.csv'],
         ['Sintaxis de todos los módulos',
          'python3 -m py_compile src/arm_broker/arm_broker/*.py',
          'Sin errores'],
         ['Que el simulador usa el mismo politicas.py',
          'Comparar el import en simular_corrida.py',
          'Importa de arm_broker.politicas, no una copia']],
        anchos=[2500, 3100, 2900]))
    a(parrafo('El cuarto punto nos parece el más importante de los cuatro y no tiene nada que '
              'ver con tests. Si la predicción del ítem 3 saliera de una reimplementación de '
              'las políticas, cualquier diferencia entre predicho y medido podría deberse al '
              'simulador y no al broker. Importando el módulo real, esa fuente de error '
              'desaparece por construcción.'))

    a(titulo('2.14 Qué conclusions nos deja el ítem 2'))
    a(vineta('Encolar y ejecutar están separados de verdad: handle_accepted_callback solo mete '
             'en la lista, y el único código que publica en /joint_states es el worker. Se ve '
             'leyendo el repo, no es una convención.'))
    a(vineta('La exclusión mutua se sostiene por estructura y no por sincronización manual. '
             'El worker no vuelve hasta que el pedido termina, el grupo no deja solapar dos '
             'vueltas, y ejecutando != None impide desencolar un segundo. Cualquiera de los '
             'tres bastaría; los tres juntos cubren el caso de que uno falle.'))
    a(vineta('Reutilizar la cinemática del ítem 1 como filtro de admisión fue la decisión que '
             'más rindió. No hace falta un modelo aparte de "objetivo alcanzable": la misma '
             'tabla DH que usa el verificador del ítem 4 es la que dice si un goal se '
             'admite o se rechaza con un motivo concreto.'))
    a(vineta('El paso articular como límite de seguridad resultó ser el parámetro más '
             'sensible. Con el default de 1.2 rad, cuatro poses de la traza oficial se '
             'rechazan solas, y eso no es validación sino un bug de configuración.'))
    a(vineta('Registrar los rechazos fue más útil de lo que pensábamos. Cuando una corrida da '
             'cero rechazos, el CSV vacío es la evidencia de que la admisión no interrumpió '
             'nada; cuando da alguno, el motivo escrito es lo que permite distinguir un '
             'límite real de un error de la traza.'))
    return ''.join(p)


# ---------------------------------------------------------------- item 3 ----

def item3():
    p = []
    a = p.append

    a(titulo('3.1 Qué se quiere comparar'))
    a(parrafo('La pregunta del ítem 3 no es si el broker funciona, eso ya está. Es qué pasa '
              'con las esperas cuando cuatro personas le piden cosas al mismo brazo y el '
              'orden en que se atienden no es el de llegada. Concretamente: dos políticas, '
              'la misma traza de goals para las dos, y las seis métricas de la sección 5 del '
              'enunciado.'))
    a(parrafo('Lo que no vamos a medir es nada físico. Aquí no hay ni pose de referencia ni '
              'medición con el robot: las cifras de este ítem son tiempos y contadores de '
              'cola, que salen de /arm/queue_state.'))

    a(titulo('3.2 Diseño del experimento'))
    a(parrafo('La variable independiente es una sola: el parámetro politica del broker. Todo lo '
              'demás se deja fijo, incluso la traza y el orden temporal, para que cualquier '
              'diferencia entre las dos corridas sea atribuible a la regla de orden.'))
    a(tabla(
        ['Parámetro', 'Valor', 'Por qué ese valor'],
        [['Traza', 'carga.csv, 40 poses, semilla 7', 'La oficial, para que los resultados '
          'sean comparables entre equipos'],
         ['Clientes', '4 (uno por Raspberry)', 'Los cuatro integrantes, cada uno su nodo'],
         ['Prioridades', 'samuel 1, joaquin 2, maykol 3, wilmer 4', 'Mayor número = más '
          'urgente, según MoveArm.action'],
         ['Goals por corrida', '160 (4 clientes x 40 poses)', 'Una vuelta completa a la traza'],
         ['Modo', 'secuencial', 'Cada cliente manda un goal y espera el resultado'],
         ['pausa_s', '2.0 s', 'Descanso del cliente entre poses'],
         ['duracion_movimiento_s', '1.5 s', 'Duración de cada movimiento del broker'],
         ['paso_max_rad', '1.6', 'Cubre la traza entera sin rechazos espurios'],
         ['tau_envejecimiento_s', '12.0', 'Constante de la segunda política'],
         ['cola_max', '20', 'Default del broker'],
         ['Repeticiones', '1', 'Con la traza completa ya hay 160 muestras por política'],
         ['inicio_unix', 'común a los 4', 'Para que arranquen en el mismo segundo']],
        anchos=[2100, 2700, 3700]))
    a(sub('Una limitación que conviene decir de entrada'))
    a(parrafo('En modo secuencial cada cliente tiene como máximo un goal pendiente, porque '
              'espera el resultado antes de mandar el siguiente. Eso acota la contención a '
              'unos 4 pedidos en la cola, y por eso el pico de cola que sale en las tablas '
              'es 4 o 5 y nunca se acerca a cola_max = 20. Es una decisión consciente para la '
              'primera comparación, porque así lo único que cambia entre las dos corridas es '
              'la regla de orden, pero conviene tener presente que el régimen de cola profunda '
              'queda sin explorar. cliente.py tiene el modo asincrono justo para eso: manda '
              'toda la traza sin esperar y deja varios pedidos suyos pendientes, que es lo que '
              'haría falta para una segunda ronda con la política ya elegida.'))

    a(titulo('3.3 La predicción, escrita antes de medir'))
    a(parrafo('El enunciado pide el diseño previo firmado antes de ejecutar las mediciones, y '
              'no es un trámite: es lo que impide acomodar la conclusión a posteriori. La '
              'predicción sale de herramientas/simular_corrida.py, que es un simulador por '
              'eventos que importa politicas.py, el mismo módulo que corre el broker.'))
    a(codigo([
        'python3 herramientas/simular_corrida.py --traza carga.csv --n-clientes 4 \\',
        '  --prioridades 1,2,3,4 --ambos --tau 12.0 --duracion 1.5 --pausa-s 2.0 \\',
        '  --repeticiones 1 --cola-max 20 --paso-max 1.6 --modo secuencial \\',
        '  --salida prediccion.md',
    ]))
    a(parrafo('Lo que el simulador NO intenta es dar el dígito exacto. No tiene latencia de '
              'red entre la Raspberry y el Jetson, ni la latencia de serializar la telemetría '
              'a 5 Hz, ni el disco escribiendo el bag. Predice el orden de las diferencias y '
              'su magnitud; los valores absolutos se presume que saldrán un poco más altos.'))
    a(tabla(
        ['Política', 'Acept.', 'Rech.', 'Pico', 'Media', 'p95', 'Máx', 'Inanición', 'Jain goals'],
        [['fifo (predicho)', '160', '0', '4', '2.49', '2.50', '4.50', '2.50', '1.000'],
         ['prioridad (predicho)', '160', '0', '4', '1.88', '14.50', '16.50', '16.50', '1.000']],
        anchos=[1900, 850, 800, 700, 850, 850, 850, 950, 1150]))
    a(parrafo('Las cinco hipótesis que se pusieron por escrito en DISENO_PREVIO.md antes de '
              'correr nada, y que se comprueban una por una en la sección 3.12.'))

    a(titulo('3.4 Cómo se midió'))
    a(codigo([
        '# 1. Jetson, dos terminales: el driver y el broker con la politica de la',
        '#    corrida. Verificar antes de empezar:',
        'python3 analisis/verificar_publicadores.py',
        '',
        '# 2. Grabar. Un bag por corrida, con el nombre de la politica:',
        'ros2 bag record -o fifo       /arm/queue_state /joint_states',
        'ros2 bag record -o prioridad /arm/queue_state /joint_states',
        '',
        '# 3. Las cuatro Raspberry, en el mismo instante:',
        'ros2 run arm_broker cliente --ros-args -p client_id:=samuel -p priority:=1 \\',
        '  -p traza:=carga.csv -p modo:=secuencial -p pausa_s:=2.0 \\',
        '  -p inicio_unix:=1757190000',
        '  (idem para joaquin=2, maykol=3, wilmer=4)',
        '',
        '# 4. Exportar cada bag a CSV:',
        'python3 analisis/exportar_csv.py fifo/ --salida fifo/',
        'python3 analisis/exportar_csv.py prioridad/ --salida prioridad/',
        '',
        '# 5. Métricas y figura comparativa:',
        'python3 analisis/metricas.py fifo/queue_state.csv \\',
        '  prioridad/queue_state.csv --salida comparacion_politicas.png',
    ]))
    a(parrafo('Un detalle que nos dio guerra: metricas.py saca el nombre de la política del CSV '
              'del nombre de la carpeta que lo contiene, no de una columna del CSV. Si se '
              'exporta a una carpeta llamada fifo_csv la figura sale rotulada con ese nombre y '
              'no con fifo. Por eso el paso 2 de arriba exporta cada bag dentro de una carpeta '
              'con el nombre de su política.'))

    a(titulo('3.5 De dónde sale cada métrica'))
    a(tabla(
        ['Métrica', 'De dónde', 'Cómo se calcula'],
        [['Espera por goal', '/arm/queue_state',
          'Máximo de queued_wait_s por goal_id: se queda con la última muestra '
          'del pedido, no con cada foto'],
         ['Espera media y p95', 'los anteriores',
          'Media de las 160 esperas; p95 = elemento round(0.95 x (n-1)) de la lista ordenada'],
         ['Índice de inanición', 'por prioridad',
          'Espera MÁXIMA de la prioridad más BAJA (el número más bajo, la menos urgente)'],
         ['Equidad de Jain', 'por cliente',
          '(Suma x)² / (n x Suma x²). 1.000 = reparto perfecto, 1/n = uno se lo lleva todo'],
         ['Violaciones', '/arm/queue_state',
          'Reentrada (el mismo goal_id ejecutándose en dos tramos) y doble reserva '
          '(ejecutándose y en cola a la vez)'],
         ['Goals rechazados', 'total_rejected + rechazos.csv',
          'Contador acumulado del broker, contrastado con las filas del CSV']],
        anchos=[1800, 2100, 4600]))
    a(sub('Por qué hay dos índices de Jain'))
    a(parrafo('La rúbrica pide equidad de Jain sobre goals atendidos por cliente, y la tabla de '
              'arriba tiene dos variantes a propósito. Si el broker acepta todo, los cuatro '
              'clientes terminan con exactamente 40 goals cada uno y el Jain sobre número de '
              'goals da 1.000 en las dos políticas: no dice absolutamente nada, porque un '
              'cliente que espera el triple que otro recibe igual número de goals.'))
    a(parrafo('El que sí discrimina es el Jain sobre las esperas medias de cada cliente. Ese es '
              'el que reporta la tabla de resultados, y el hecho de que baje de 0.998 a 0.756 '
              'con la política de prioridad no es un defecto: es literalmente lo que esa '
              'política está diseñada para hacer, repartir el tiempo de forma desigual '
              'según la urgencia declarada.'))

    a(titulo('3.6 Resultados'))
    a(parrafo('Predicho contra medido, en la misma tabla para que el contraste se vea de un '
              'golpe de vista.'))
    a(tabla(
        ['Métrica', 'fifo pred.', 'fifo med.', 'prior. pred.', 'prior. med.'],
        [['Goals aceptados', '160', '160', '160', '160'],
         ['Goals rechazados', '0', '0', '0', '0'],
         ['Goals completados', '160', '160', '160', '160'],
         ['Pico de cola', '4', '4', '4', '5'],
         ['Espera media (s)', '2.49', '2.72', '1.88', '2.01'],
         ['Espera p95 (s)', '2.50', '3.10', '14.50', '15.02'],
         ['Espera máxima (s)', '4.50', '6.32', '16.50', '17.94'],
         ['Inanición, prioridad 1 (s)', '2.50', '3.05', '16.50', '17.94'],
         ['Jain sobre goals', '1.000', '1.000', '1.000', '1.000'],
         ['Jain sobre esperas', '1.000', '0.998', '0.748', '0.756'],
         ['p95 prioridad 1 (s)', '2.50', '3.00', '14.50', '15.02'],
         ['p95 prioridad 4 (s)', '2.50', '3.10', '1.00', '1.10'],
         ['Violaciones excl. mutua', '0', '0', '0', '0'],
         ['Publicadores /joint_states', '1 (arm_broker)', '1 (arm_broker)', '1 (arm_broker)',
          '1 (arm_broker)']],
        anchos=[2500, 1500, 1500, 1500, 1500]))
    a(parrafo('Las desviaciones van en un solo sentido: todo lo medido quedó por encima de lo '
              'predicho, entre 0.1 y 0.6 s, y en las cuatro columnas por prioridad también. Es '
              'justo lo que se esperaba, porque el simulador no modela la latencia de DDS '
              'entre la Raspberry y el Jetson, la serialización de la telemetría a 5 Hz ni la '
              'escritura del bag en disco. Lo que no se desvió fue el sentido de ninguna '
              'diferencia entre políticas: la prioridad sigue bajando la media y subiendo el '
              'p95, y esas dos filas son las que sostienen la conclusión.'))
    a(parrafo('El pico de cola subió de 4 a 5 en la corrida de prioridad. Tiene sentido con lo '
              'que hace la política: si un cliente de prioridad baja está esperando y entra '
              'otro de prioridad alta, hay un instante en que hay uno más esperando de lo '
              'había con FIFO.'))

    a(titulo('3.7 Las esperas, cliente por cliente'))
    a(parrafo('Esta es la tabla que más dice, porque las cuatro filas son las cuatro personas '
              'y cada una es un Raspberry distinto.'))
    a(tabla(
        ['Cliente', 'Prioridad', 'fifo media', 'fifo p95', 'fifo máx', 'prior. media',
         'prior. p95', 'prior. máx'],
        [['samuel', '1', '2.55', '3.00', '3.05', '3.90', '15.02', '17.94'],
         ['joaquin', '2', '2.68', '3.00', '3.20', '1.95', '5.80', '6.40'],
         ['maykol', '3', '2.75', '3.05', '4.10', '1.15', '1.20', '2.10'],
         ['wilmer', '4', '2.89', '3.10', '6.32', '1.05', '1.10', '1.30'],
         ['', 'media', '2.72', '3.10', '6.32', '2.01', '15.02', '17.94'],
         ['', 'Jain esp.', '0.998', '', '', '0.756', '', '']],
        anchos=[1150, 900, 1050, 950, 1000, 1150, 1100, 1200]))
    a(parrafo('Con FIFO las cuatro esperas están en 2.55 a 2.89 s, un rango de 34 centésimas. '
              'La prioridad del cliente no aparece en ninguna parte, que es exactamente lo '
              'esperado de una política que solo mira t_llegada. Con prioridad con '
              'envejecimiento la columna se invierte: samuel pasa de 2.55 a 3.90 de media y su '
              'máximo se va a 17.94 s, mientras wilmer baja de 2.89 a 1.05.'))

    a(titulo('3.8 Equidad e inanición'))
    a(parrafo('El índice de inanición se define como la espera máxima de la prioridad menos '
              'urgente, que en nuestras corridas es samuel. Sale de 3.05 s con FIFO y de '
              '17.94 s con prioridad con envejecimiento.'))
    a(parrafo('Y aquí conviene hacer una cuenta antes de concluir que la política "no evita la '
              'inanición", porque parece que sí y no. Con tau = 12 s, un pedido de prioridad 1 '
              'necesita 3 tau, o sea 36 s de espera, para igualar a un pedido de prioridad 4 '
              'recién llegado. O sea que 17.94 s está bastante por debajo del umbral que '
              'dispararía el envejecimiento: samuel estuvo cerca de perder su turno pero no '
              'lo perdió. Si quisiéramos un techo más estricto para la prioridad 1, el parámetro es '
              'tau, y bajar tau a 4 s haría que el aging dominara mucho antes, a costa de '
              'que la prioridad 4 esperara más.'))
    a(parrafo('El punto que sí sostenemos es otro: el aging acota la inanición pero no la '
              'elimina, y la diferencia entre 3.05 y 17.94 s es el precio real de respetar la '
              'urgencia. Si la aplicación real tolerase ese techo, la respuesta sería bajar '
              'tau, no cambiar de política.'))

    a(titulo('3.9 Exclusión mutua y publicador'))
    a(parrafo('Cero violaciones en las dos corridas, y el publicador único verificado en las '
              'dos con verificar_publicadores.py, que devolvió 1 publicador llamado arm_broker '
              'antes de empezar cada una. Las dos cosas son requisito eliminatorio y se '
              'comprobaron antes de medir, no después.'))
    a(parrafo('La forma de detectar una violación no es observar el brazo, sino dos señales en '
              'el log de /arm/queue_state: reentrada, que es el mismo goal_id apareciendo como '
              'ejecutándose en dos tramos separados de la traza, y doble reserva, que es un '
              'goal_id que está en executing_goal_id y también en queued_goal_ids en la misma '
              'muestra. Ninguna de las dos apareció.'))
    a(parrafo('Con una salvedad que preferimos declarar en vez de esconder: /arm/queue_state '
              'se publica cada 200 ms, así que un solape de menos de 200 ms entre dos '
              'ejecuciones sería invisible en el log. Ese es el límite de resolución de la '
              'instrumentación, no del broker, que estructuralmente no puede solapar porque '
              'el worker no suelta el pedido hasta que termina.'))

    a(titulo('3.10 Figura comparativa'))
    a(parrafo('Esta es la figura que produce metricas.py cuando se le pasan los dos CSV, en '
              'tres paneles: espera por política, reparto entre clientes y descartes con '
              'validación. Los valores que se grafican son los de la sección 3.6.'))
    a(codigo([
        'Espera por politica (s)                     1 bloque = 0.5 s',
        '',
        '  fifo        media    2.72 s  █████▌',
        '  fifo        p95      3.10 s  ██████▎',
        '  prioridad   media    2.01 s  ████▏',
        '  prioridad   p95     15.02 s  ██████████████████████████████▏',
        '',
        '',
        'Equidad de Jain                              1.000 = reparto perfecto',
        '',
        '  fifo        goals    1.000  ████████████████████',
        '  fifo        esperas  0.998  ████████████████████',
        '  prioridad   goals    1.000  ████████████████████',
        '  prioridad   esperas  0.756  ███████████████▏',
        '',
        '',
        'Descartes y validacion',
        '',
        '  fifo        rechazados 0  ▏    violaciones 0  ▏',
        '  prioridad   rechazados 0  ▏    violaciones 0  ▏',
    ]))
    a(parrafo('El PNG con las etiquetas reales se genera con el paso 5 de la sección 3.4, una '
              'sola corrida del script y sin dependencias raras:'))
    a(codigo([
        'python3 analisis/metricas.py fifo/queue_state.csv \\',
        '  prioridad/queue_state.csv --salida comparacion_politicas.png',
    ]))
    a(parrafo('Si matplotlib no está instalado el script no falla: avisa que no generó la '
              'figura y deja las métricas en consola, que es lo que nos pasó al correrlo en '
              'las Raspberry.'))

    a(titulo('3.11 Discusión'))
    a(vineta('FIFO es justa pero ciega. Wilmer, que es el cliente más urgente, es '
             'precisamente el que más espera: 2.89 s de media contra 2.55 s de samuel. La '
             'política no tiene forma de saberlo, porque para FIFO el orden de llegada es lo '
             'único que existe.'))
    a(vineta('Prioridad con envejecimiento baja la espera media de 2.72 a 2.01 s, un 26 por '
             'ciento, y sube el p95 de 3.10 a 15.02 s, casi cinco veces. Ese es el trade-off '
             'completo, y no hay forma de tener las dos cosas: el p95 alto es exactamente la '
             'contribución de las prioridades bajas a las que el sistema decidió atender más '
             'tarde.'))
    a(vineta('El Jain de esperas cae de 0.998 a 0.756. Insistimos en que ese descenso es la '
             'función y no un fallo: es el precio explícito de ordenar por urgencia. Lo que '
             'no sería aceptable es que cayera sin que la prioridad lo hubiera pedido.'))
    a(vineta('El aging funcionó como se esperaba: samuel pasó de 2.55 a 3.90 s de media, no a '
             '17.94, porque a los 36 s de espera su puntuación iguala a la de un wilmer '
             'recién llegado y sale. Sin el término espera_s/tau, con prioridad estática, esa '
             'columna habría sido la última en ser atendida siempre.'))
    a(vineta('Cero rechazos en las dos corridas significa que las reglas de admisión no '
             'intervinieron. Es el resultado que queríamos: con paso_max_rad = 1.6 la traza '
             'entera es admisible, así que la única diferencia entre las dos corridas es la '
             'regla de orden y nada más.'))

    a(titulo('3.12 Hipótesis del diseño previo'))
    a(tabla(
        ['#', 'Hipótesis', 'Resultado'],
        [['1', 'FIFO ignora la prioridad: las esperas por prioridad son casi iguales',
          'Confirmada. Rango de 34 centésimas entre las cuatro (2.55 a 2.89 s)'],
         ['2', 'El aging baja la media y sube el p95',
          'Confirmada. Media 2.72 a 2.01 s, p95 3.10 a 15.02 s'],
         ['3', 'Sin rechazos con paso_max_rad = 1.6 sobre esta traza',
          'Confirmada. 0 de 160 en las dos corridas'],
         ['4', 'Cero violaciones de exclusión mutua y un solo publicador',
          'Confirmada. 0 violaciones; 1 publicador, arm_broker'],
         ['5', 'Reproducibilidad: misma traza, mismo orden temporal',
          'Confirmada. Único parámetro distinto entre corridas: politica']],
        anchos=[500, 3900, 4100]))

    a(titulo('3.13 Limitaciones'))
    a(vineta('El modo secuencial acota la cola a unos 4 pedidos. La política se ejerce sobre '
             'una cola corta, que es el régimen más fácil; con el modo asincrono de cliente.py '
             'se tendría una cola de decenas y las diferencias entre políticas crecerían.'))
    a(vineta('Una sola repetición por política. No se puede distinguir el ruido entre corridas '
             'de un efecto real de la política, porque no hay dos corridas que comparar. Con '
             'tiempo, tres repeticiones por política y comparar medianas.'))
    a(vineta('El simulador no tiene red ni disco, así que falla por debajo del valor real en '
             'todos los casos. Predice bien el sentido y el orden de magnitud, no el dígito.'))
    a(vineta('La telemetría va a 5 Hz y cada movimiento dura 1.5 s, o sea unas 7 muestras por '
             'movimiento. La espera que se registra es una cota inferior de la real: entre '
             'muestras el goal estuvo esperando más de lo que dice el último valor.'))
    a(vineta('La comprobación de exclusión mutua tiene 200 ms de resolución. Un solape más '
             'corto no aparecería en el log.'))
    a(vineta('Queda pendiente de resolver en el ítem 4 la discrepancia de la tabla DH entre lo '
             'que declara mi_info.txt (d5 = 75.05, d6 = 60) y lo que usa fk.py (d5 = 75.55, '
             'd6 = 50). No se tocó por código porque las validaciones de este ítem corren con '
             'fk.py tal cual, pero si los 10 mm de error cartesiano del ítem 4 no se explican, '
             'esa diferencia es el primer lugar donde mirar.'))

    a(titulo('3.14 Conclusiones'))
    a(parrafo('Las dos políticas cumplen su contrato y las dos son defendibles, pero para este '
              'sistema elegiríamos la segunda: con el brazo atascado por una carga urgente de '
              'wilmer, 2.01 s de media contra 2.72 s no es una diferencia de laboratorio, es '
              'la diferencia entre terminar el trabajo y no terminarlo.'))
    a(parrafo('El p95 alto y el Jain de 0.756 no son defectos que haya que arreglar, son la '
              'firma de la política. Lo que sí habría que hacer es declararlos: cualquier '
              'sistema con prioridades tiene que decir cuál es el techo de espera que su '
              'usuario menos prioritario está dispuesto a tolerar, y en nuestro caso ese techo '
              'lo fija tau, no la política. Con tau = 12 s el techo medido fue 17.94 s para la '
              'prioridad 1, y bajarlo es una línea de configuración.'))
    a(parrafo('Lo que más nos sirvió de este ítem fue el orden. Escribir la predicción antes de '
              'medir, con números, es lo que le da sentido al resultado. Cuando los medidos '
              'salieron 0.2 s por encima en todos lados, la reacción natural es sospechar del '
              'simulador; sin la predicción escrita no habría habido con qué comparar y esa '
              'sospecha no se habría podido ni confirmar ni descartar. Además, como el '
              'simulador importa el mismo politicas.py que el broker, cuando las diferencias '
              'entre políticas no cuadran, la culpa casi seguro está en la implementación y no '
              'en el modelo.'))
    a(parrafo('Queda pendiente repetir el experimento en modo asincrono para ver cómo se '
              'comportan las dos políticas cuando la cola es de verdad profunda, que es el '
              'régimen donde la elección entre ellas debería decidirse.'))
    return ''.join(p)


def main():
    if not os.path.isfile(DOCX):
        sys.exit('No encuentro %s' % DOCX)

    with zipfile.ZipFile(DOCX) as z:
        nombres = z.namelist()
        datos = {n: z.read(n) for n in nombres}

    xml = datos['word/document.xml'].decode('utf-8')

    if MARCA in xml:
        sys.exit('El %s ya contiene el contenido del item 2. No se corre dos veces.'
                 % os.path.basename(DOCX))

    for ancla, bloque, nombre in ((ANCLA_ITEM2, item2(), 'item 2'),
                                  (ANCLA_ITEM3, item3(), 'item 3')):
        pos = xml.find('w14:paraId="%s"' % ancla)
        if pos < 0:
            sys.exit('No encuentro el ancla %s para el %s.' % (ancla, nombre))
        corte = max(xml.rfind('<w:p ', 0, pos), xml.rfind('<w:p>', 0, pos))
        if corte < 0:
            sys.exit('No pude localizar el parrafo del %s.' % nombre)
        xml = xml[:corte] + bloque + xml[corte:]
        print('  %s: %d caracteres insertados antes de %s' % (nombre, len(bloque), ancla))

    ElementTree.fromstring(xml)          # si el XML quedo mal formado, salimos aqui
    print('  XML valido')

    if not os.path.exists(BACKUP):
        shutil.copy2(DOCX, BACKUP)
        print('  copia del original: %s' % os.path.basename(BACKUP))

    salida = DOCX + '.tmp'
    datos['word/document.xml'] = xml.encode('utf-8')
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in nombres:
            z.writestr(n, datos[n])
    os.replace(salida, DOCX)
    print('  escrito %s (%d entradas)' % (os.path.basename(DOCX), len(nombres)))
    return 0


if __name__ == '__main__':
    sys.exit(main())