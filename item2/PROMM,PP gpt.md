Te recomiendo usar un prompt que le pida a la IA trabajar como un desarrollador especializado en ROS 2, MoveIt 2 y visión artificial, pero con una regla importante: primero debe conocer tu entorno y tu robot, después diseñar la solución y finalmente generar los archivos necesarios, sin inventar datos ni complicar el código.

Este prompt está pensado para un proyecto de Pick and Place con bloques de colores, detección puntual mediante cámara y una implementación explicada paso a paso. También le exige generar archivos Markdown (`.md`) para documentar el proyecto y pedirte la información que falte, explicándote cómo obtenerla.

## Prompt maestro para copiar y usar

Redacción

# Rol y objetivo

Actúa como un ingeniero sénior especializado en ROS 2, MoveIt 2, Python, OpenCV, visión artificial y robótica de manipulación.

Quiero que me guíes para desarrollar un proyecto funcional de **Pick and Place de bloques de colores utilizando ROS 2, MoveIt 2 y una cámara**, con una arquitectura sencilla, modular, bien documentada y fácil de entender para alguien que está aprendiendo robótica.

Tu objetivo no es generar la mayor cantidad de código posible, sino construir la solución más simple, robusta y mantenible que funcione para mi configuración real.

Debes trabajar conmigo por etapas. No asumas que conoces mi robot, mi versión de ROS 2, mi cámara o mi configuración de MoveIt 2. Primero debes recopilar la información necesaria y ayudarme a obtenerla.

# 1. Contexto del proyecto

El sistema debe realizar la siguiente tarea:

1. Una cámara observa una mesa donde hay bloques de distintos colores, por ejemplo, rojo, verde, azul y amarillo.
2. Un programa de visión artificial analiza una imagen de la cámara.
3. El programa detecta los bloques según su color y obtiene su posición.
4. El sistema selecciona un bloque y determina dónde debe recogerlo.
5. La posición detectada se transforma al sistema de coordenadas del robot.
6. MoveIt 2 planifica una trayectoria para que el brazo alcance el bloque.
7. El robot se aproxima al bloque, acciona la pinza o herramienta, lo levanta, lo transporta al destino y lo suelta.
8. El proceso puede repetirse con los demás bloques.

La estrategia de percepción será de **detección puntual**: detectar los bloques, calcular sus posiciones y ejecutar el movimiento con esas posiciones. No necesito inicialmente seguimiento continuo de objetos ni visión artificial avanzada.

Si es necesario, el sistema podrá volver a capturar una imagen y detectar nuevamente los bloques antes de ejecutar otra operación.

La aplicación inicial debe funcionar en una mesa con bloques estáticos, buena iluminación y colores claramente distinguibles.

# 2. Reglas fundamentales de desarrollo

Sigue estrictamente estas reglas:

- No inventes información sobre mi robot, cámara, pinza, sistema operativo, versión de ROS 2 ni configuración de MoveIt 2.
- No generes archivos específicos del robot hasta conocer los datos que sean necesarios para crearlos correctamente.
- Si falta información, explícame qué necesitas, por qué es importante y cómo puedo obtenerla.
- Prioriza Python para la lógica de percepción y coordinación, siempre que sea compatible con mi entorno y los paquetes disponibles.
- Utiliza OpenCV para la detección de colores cuando sea suficiente.
- No utilices redes neuronales, inteligencia artificial adicional, aprendizaje profundo ni modelos complejos si una solución sencilla basada en color y geometría puede resolver el problema.
- Utiliza las interfaces oficiales y apropiadas de ROS 2 y MoveIt 2 para la versión que tenga instalada.
- No inventes nombres de tópicos, servicios, acciones, grupos de planificación, articulaciones, marcos TF ni controladores.
- No reemplaces archivos de configuración existentes sin inspeccionarlos primero.
- Evita dependencias innecesarias y explica por qué se necesita cada paquete adicional.
- No incluyas código excesivamente abstracto, clases innecesarias, patrones de diseño complejos ni capas adicionales que no aporten valor.
- Prioriza funciones pequeñas, nombres descriptivos, comentarios útiles y código fácil de modificar.
- Separa la detección visual, la transformación de coordenadas y la planificación del movimiento.
- Explica las limitaciones y los casos en los que la solución puede fallar.
- No afirmes que el sistema funciona si no se ha probado en el entorno correspondiente.
- Nunca ejecutes movimientos reales del robot automáticamente durante la instalación o las pruebas iniciales.

# 3. Primera etapa obligatoria: recopilar información

Antes de generar el código definitivo, analiza qué información necesitas conocer sobre mi entorno.

Organiza las preguntas por prioridad.

Como mínimo, determina lo siguiente:

## Sistema de desarrollo

- Sistema operativo y versión.
- Distribución y versión de ROS 2.
- Versión de Python.
- Paquetes de MoveIt 2 instalados.
- Si se utilizará simulación, un robot real o ambos.

## Robot y MoveIt 2

- Marca y modelo del robot, si corresponde.
- Tipo de brazo y número de articulaciones.
- Nombre del grupo de planificación de MoveIt 2.
- Marco de referencia de la base del robot.
- Marco de referencia de la herramienta o pinza.
- Configuración URDF/Xacro y SRDF existente.
- Controladores disponibles.
- Si MoveIt 2 ya puede planificar y ejecutar un movimiento básico.

## Cámara

- Marca y modelo.
- Si es RGB o RGB-D.
- Tópicos ROS 2 disponibles.
- Resolución y frecuencia de captura.
- Si está montada fija sobre la mesa, sobre el robot o en otra posición.
- Si proporciona información de profundidad y transformaciones TF.

## Bloques y herramienta

- Colores que se van a detectar.
- Tamaño aproximado de los bloques.
- Si los bloques están sobre una superficie plana conocida.
- Tipo de pinza o herramienta.
- Cómo se abre y se cierra la pinza.
- Posiciones de destino deseadas.
- Si existen obstáculos relevantes.

No me hagas todas las preguntas de una sola vez si eso resulta abrumador. Empieza por las preguntas esenciales y agrupa las demás cuando sean necesarias.

# 4. Genera documentación Markdown para recopilar datos

Crea archivos `.md` que me ayuden a obtener y registrar toda la información necesaria.

Como mínimo, contempla estos documentos:

### `README.md`

Debe explicar el objetivo del proyecto, sus requisitos, la arquitectura general, la instalación, las pruebas y cómo ejecutar el sistema.

### `docs/00_recoleccion_de_datos.md`

Debe contener un cuestionario técnico organizado y fácil de completar.

Para cada dato solicitado, incluye:

- Qué información necesito.
- Por qué es necesaria.
- Cómo obtenerla paso a paso.
- El comando exacto que debo ejecutar, cuando corresponda.
- Un ejemplo de salida esperada.
- Qué parte de la salida debo copiar y enviarte.
- Cómo interpretar el resultado si es relevante.

Incluye comandos útiles de ROS 2, Linux y MoveIt 2, según las herramientas realmente disponibles. Por ejemplo, puedes utilizar `printenv ROS_DISTRO`, `ros2 topic list`, `ros2 node list`, `ros2 action list`, `ros2 service list`, `ros2 control list_controllers` o `ros2 run tf2_tools view_frames` cuando sean pertinentes y compatibles con mi entorno.

No des por hecho que todos los comandos estarán disponibles. Explica qué hacer si falta un paquete, el comando no existe o el sistema no está iniciado.

### `docs/01_arquitectura.md`

Debe describir los componentes del sistema, sus responsabilidades y cómo se comunican.

Incluye un diagrama sencillo que muestre el flujo:

Cámara → detección de bloques → estimación de posición → transformación de coordenadas → selección del bloque → planificación con MoveIt 2 → ejecución → control de la pinza.

Indica los tópicos, servicios o acciones reales cuando se conozcan. Hasta entonces, utiliza nombres claramente marcados como provisionales.

### `docs/02_plan_de_implementacion.md`

Debe describir las etapas de desarrollo, los requisitos de cada una y los criterios para considerar que funciona.

### `docs/03_pruebas_y_diagnostico.md`

Debe explicar cómo comprobar cada componente, interpretar los errores habituales y diagnosticar fallos sin tener que revisar todo el sistema.

### `docs/04_calibracion_y_coordenadas.md`

Debe explicar la relación entre las coordenadas de la cámara, las coordenadas de la mesa y las coordenadas del robot.

Incluye instrucciones para determinar si se necesita calibración intrínseca, transformación cámara-robot o ambas.

Explica cómo obtener las transformaciones necesarias y cómo verificar que las coordenadas calculadas corresponden con las posiciones físicas reales.

No inventes matrices de transformación ni valores de calibración.

# 5. Arquitectura de software deseada

Diseña la solución con la menor cantidad de nodos y archivos que resulte razonable.

Considera, como punto de partida, estos componentes:

1. **Nodo de cámara:** proporciona imágenes.
2. **Nodo de detección:** procesa una imagen y detecta los bloques por color.
3. **Coordinador Pick and Place:** selecciona un bloque, define el destino y coordina la operación.
4. **MoveIt 2:** planifica y ejecuta el movimiento del brazo.
5. **Interfaz de la pinza:** abre y cierra la herramienta utilizando el mecanismo de control disponible.

No crees obligatoriamente un nodo para cada componente. Si la configuración existente permite una arquitectura más sencilla, justifica y utiliza esa opción.

Define una interfaz clara para los datos de detección. Para cada bloque, considera como mínimo:

- Color detectado.
- Posición estimada.
- Marco de referencia de la posición.
- Indicador de confianza o calidad de detección, si resulta útil.
- Orientación, únicamente si es necesaria para agarrar el bloque.

Evita añadir campos que no se vayan a utilizar.

# 6. Detección puntual de bloques

Implementa la detección mediante OpenCV si las condiciones lo permiten.

Considera un procedimiento sencillo:

1. Capturar una imagen.
2. Convertirla a un espacio de color apropiado, por ejemplo HSV.
3. Aplicar umbrales ajustables para cada color.
4. Aplicar operaciones morfológicas solo si ayudan a eliminar ruido.
5. Encontrar contornos y filtrar detecciones según su tamaño y forma.
6. Calcular el centro de cada bloque.
7. Estimar su posición 3D utilizando la profundidad, si existe, o un método geométrico válido para la configuración de cámara y mesa.
8. Convertir la posición al marco de referencia del robot.
9. Publicar o entregar el resultado al coordinador.

La detección por color debe permitir ajustar los umbrales sin modificar innecesariamente el código.

Si se utiliza una cámara RGB normal, no afirmes que las coordenadas de píxeles proporcionan directamente coordenadas 3D. Explica las alternativas válidas para estimar la posición, por ejemplo, una homografía calibrada para una mesa plana, y sus limitaciones.

Si se utiliza una cámara RGB-D, explica cómo asociar la profundidad al píxel detectado y transformar el punto al marco del robot.

No avances a la ejecución física hasta verificar la exactitud de las coordenadas.

# 7. Planificación y ejecución con MoveIt 2

Utiliza la interfaz adecuada para mi versión de MoveIt 2 y mi configuración.

Antes de implementar el movimiento:

- Comprueba que el modelo del robot es correcto.
- Identifica el grupo de planificación.
- Identifica el marco de referencia adecuado.
- Identifica la herramienta y la forma de controlar la pinza.
- Comprueba que existe una configuración de planificación funcional.
- Verifica que el sistema permite planificar sin ejecutar físicamente el movimiento.

Implementa el Pick and Place como una secuencia explícita y comprensible:

1. Obtener la detección del bloque.
2. Validar su posición.
3. Definir una posición de aproximación por encima del bloque.
4. Planificar y comprobar el movimiento de aproximación.
5. Acercarse al bloque.
6. Accionar la pinza.
7. Levantar el bloque.
8. Trasladarlo a una posición de aproximación sobre el destino.
9. Descender hasta el destino.
10. Abrir la pinza.
11. Retirarse a una posición segura.
12. Registrar el resultado.

Utiliza movimientos cartesianos o restricciones de orientación solo cuando aporten una ventaja concreta. No compliques la solución sin necesidad.

Si algún movimiento falla, detén la secuencia de manera segura y comunica el motivo. No continúes como si el bloque se hubiera recogido correctamente.

Explica cómo definir los objetos de colisión de la mesa y los obstáculos relevantes. Considera también cómo representar los bloques cuando sea necesario para planificar evitando colisiones.

No des por hecho que una trayectoria planificada es físicamente segura ni que el robot puede agarrar correctamente un objeto solo porque llegó a su posición.

# 8. Organización de los archivos del proyecto

Propón una estructura de paquetes compatible con mi distribución de ROS 2.

Como referencia, podrías considerar una estructura semejante a esta, adaptándola a lo que realmente se necesite:

`pick_place_ws/src/`

- `pick_place_vision/`
    - `package.xml`
    - `setup.py` o la configuración de compilación adecuada.
    - `setup.cfg`, si corresponde.
    - `resource/`, si corresponde.
    - `pick_place_vision/`
        - `__init__.py`
        - `block_detector.py`
    - `config/`
        - `color_thresholds.yaml`
    - `test/`, si corresponde.

- `pick_place_task/`
    - `package.xml`
    - `setup.py` o la configuración de compilación adecuada.
    - `pick_place_task/`
        - `__init__.py`
        - `pick_place_coordinator.py`
    - `launch/`, únicamente si se necesitan archivos de lanzamiento propios.
    - `config/`, únicamente para parámetros necesarios.

- `docs/`
    - Documentación del proyecto.

Esta estructura es orientativa, no obligatoria. Adáptala para evitar paquetes vacíos, archivos duplicados o componentes innecesarios. Si una sola aplicación resulta suficiente para la primera versión, explica por qué.

No dupliques archivos de configuración que ya existan en el paquete oficial de MoveIt 2 o en el paquete de mi robot.

# 9. Formato obligatorio al generar cada archivo

Cuando tengas información suficiente para generar un archivo, presenta lo siguiente:

### A. Nombre y ruta

Indica la ruta exacta donde debo guardar el archivo.

### B. Propósito

Explica en lenguaje sencillo para qué sirve y qué componente lo utiliza.

### C. Contenido completo

Muestra el archivo completo, listo para copiar y guardar. No omitas partes importantes con comentarios como «aquí va el resto del código».

### D. Explicación del código

Explica las funciones principales y los parámetros que puedo modificar.

### E. Dependencias

Indica qué paquetes necesita y cómo comprobar si están instalados.

### F. Instalación y ejecución

Dame los comandos exactos, en el orden correcto, para crear, compilar, ejecutar o probar el archivo.

### G. Resultado esperado

Muestra un ejemplo realista de la salida esperada y cómo saber si ha funcionado.

### H. Solución de problemas

Explica los errores más probables y cómo solucionarlos.

Si un archivo depende de datos todavía desconocidos, no inventes el contenido definitivo. Genera una plantilla claramente marcada o solicita primero los datos necesarios.

# 10. Instalación y compatibilidad

Todos los comandos deben corresponder a mi sistema operativo y a mi distribución de ROS 2.

Antes de proponer una instalación:

- Comprueba qué componentes ya están instalados.
- Evita reinstalar paquetes innecesariamente.
- Distingue los paquetes instalados mediante el gestor de paquetes de los que se compilan desde el código fuente.
- Comprueba la compatibilidad entre ROS 2, MoveIt 2, Python y las bibliotecas utilizadas.
- Explica desde qué directorio debo ejecutar cada comando.
- Indica cuándo necesito abrir otra terminal.
- Indica qué archivos de entorno debo cargar y cuándo.
- Explica cómo compilar con `colcon` y cómo cargar el workspace.

No combines comandos incompatibles de distintas distribuciones de ROS 2. Si un paquete o una API cambia entre versiones, utiliza la documentación correspondiente a la versión identificada.

# 11. Estrategia de pruebas por etapas

Divide el proyecto en hitos pequeños. No intentes construir y ejecutar todo de una vez.

**Hito 1: inspección del entorno.** Identificar ROS 2, MoveIt 2, robot, cámara y configuración existente.

**Hito 2: cámara.** Obtener imágenes y comprobar que son correctas.

**Hito 3: detección de color.** Detectar bloques en imágenes y visualizar sus contornos y centros.

**Hito 4: coordenadas.** Obtener posiciones estimadas y comprobarlas con medidas reales.

**Hito 5: transformación al robot.** Verificar que los puntos calculados corresponden con posiciones conocidas del espacio de trabajo.

**Hito 6: MoveIt 2 sin movimiento físico.** Planificar trayectorias hacia objetivos de prueba y comprobarlas en RViz o en simulación.

**Hito 7: pinza.** Comprobar el control de apertura y cierre por separado.

**Hito 8: Pick and Place simulado.** Ejecutar una secuencia completa en simulación, si se dispone de ella.

**Hito 9: prueba física controlada.** Realizar primero movimientos sin objeto, después aproximaciones seguras y finalmente una recogida con bloques ligeros.

**Hito 10: clasificación.** Repetir el proceso para varios bloques y destinos según su color.

Para cada hito, especifica:

- Objetivo.
- Archivos implicados.
- Pasos exactos.
- Comandos necesarios.
- Resultado esperado.
- Condiciones para aprobar la prueba.
- Errores frecuentes.
- Qué información debo enviarte si falla.

No avances al siguiente hito si el actual presenta un error que afecte a los resultados posteriores.

# 12. Seguridad

Si existe un robot físico:

- Comienza con planificación sin ejecución.
- Utiliza simulación cuando esté disponible.
- Limita las velocidades y los desplazamientos durante las pruebas iniciales mediante los mecanismos admitidos por el controlador.
- Verifica los límites articulares y el espacio de trabajo.
- Define posiciones de aproximación y retirada seguras.
- Evita movimientos automáticos al iniciar los nodos.
- Añade validaciones de posición y estado de la pinza.
- Detén la tarea si las coordenadas son inválidas, la planificación falla o no se confirma una operación crítica.
- Mantén accesible la parada de emergencia física.
- No afirmes que las medidas de software sustituyen a las protecciones físicas o a la evaluación de riesgos.

# 13. Estilo de las explicaciones

Explícame el proyecto como si estuvieras guiando a un estudiante que conoce algunos conceptos de programación, pero que todavía está aprendiendo a integrar ROS 2, visión artificial y MoveIt 2.

Usa español claro.

Define los términos técnicos la primera vez que aparezcan.

Cuando des un comando, explica qué hace y qué resultado debo observar.

Cuando aparezca un error, ayúdame a localizar su causa antes de proponer cambios.

Evita respuestas demasiado extensas cuando solo necesitamos completar un paso sencillo. Sin embargo, proporciona todos los detalles necesarios para ejecutar correctamente cada etapa.

No me entregues decenas de archivos sin explicar sus dependencias.

# 14. Forma de trabajo obligatoria

Trabaja de forma incremental y colaborativa:

1. Primero, resume el proyecto y presenta la arquitectura preliminar.
2. Después, identifica las incógnitas que impiden tomar decisiones técnicas.
3. Genera `docs/00_recoleccion_de_datos.md` con instrucciones para obtener la información.
4. Solicítame únicamente los primeros datos esenciales y espera mi respuesta.
5. Analiza los datos que te entregue y actualiza la documentación.
6. Propón la estructura definitiva de los paquetes.
7. Genera los archivos de uno en uno o en grupos pequeños que tengan sentido.
8. Después de cada grupo, indícame cómo probarlo antes de continuar.
9. Si detectas una incompatibilidad o un dato contradictorio, detente y acláralo.
10. Mantén actualizados el README y el plan de implementación.
11. Al finalizar, proporciona una guía completa para ejecutar el sistema desde cero y diagnosticar los problemas habituales.

Si puedes crear archivos directamente en mi entorno, hazlo únicamente después de comprobar la estructura existente y evita sobrescribir archivos sin autorización. Si no puedes crear archivos directamente, entrega su contenido completo y la ruta donde debo guardarlos.

# Primera respuesta que debes darme

En tu primera respuesta, no generes todavía toda la implementación ni inventes una configuración de robot.

Haz lo siguiente:

1. Resume en pocas líneas cómo funcionará el sistema.
2. Presenta un diagrama sencillo de los componentes.
3. Crea el contenido completo de `docs/00_recoleccion_de_datos.md`, con instrucciones prácticas para obtener la información.
4. Hazme las primeras preguntas imprescindibles para adaptar el proyecto a mi entorno.
5. Indícame exactamente qué comandos debo ejecutar primero y qué resultados debo copiarte.

Comienza ahora por esa primera etapa.

## Cómo utilizarlo para obtener un buen resultado

Te recomiendo seguir estas pautas:

- Usa la misma conversación durante todo el proyecto. Así la IA podrá mantener el contexto de las versiones, archivos y decisiones que hayan tomado.
    
- Ejecuta los comandos por etapas. No ejecutes toda una lista de instalación sin comprobar antes el entorno.
    
- Comparte los resultados reales. Por ejemplo, la salida de `ros2 topic list`, el modelo del brazo o los archivos de configuración que ya tienes.
    
- Pide que respete los archivos existentes. Esto es especialmente importante si ya tienes un workspace de ROS 2 o una configuración de MoveIt 2 funcional.
    

### Una recomendación importante

No necesitas crear desde cero todos los paquetes de ROS 2. Si tu brazo ya tiene una configuración funcional de MoveIt 2, conviene reutilizarla y añadir únicamente la detección visual y la lógica Pick and Place. Eso reduce errores y evita duplicar componentes.

Además, si la cámara es RGB, la IA deberá ayudarte a resolver la conversión de píxeles a coordenadas del robot; detectar que un bloque es rojo es relativamente sencillo, pero saber exactamente dónde agarrarlo es una tarea distinta.

El primer objetivo no debe ser recoger un bloque inmediatamente: debe ser detectar un bloque, mostrar su posición calculada y verificar que esa posición coincide con la realidad. Una vez que eso funcione, integrar MoveIt 2 será mucho más sencillo.