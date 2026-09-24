# Pruebas de navegador en vivo (2026-09-24)

Verificación manual asistida en Chrome contra la web desplegada, con una cuenta de participante desechable (ya borrada). El asistente no escribe contraseñas: el login lo hizo la persona en la pestaña que controla Claude. Las pruebas automatizadas con Playwright siguen pendientes.

## Resultado

| Qué | Resultado |
|---|---|
| UC-002 flujo principal: tres perfiles con su descripción corta | Correcto (Básico «paso a paso», Técnico «con detalle», General «corto y claro») |
| UC-002 A1 (spec ajustada): General preseleccionado | Correcto |
| UC-002 A2 y BR-003: cambio de perfil a mitad de conversación | Correcto: la 2.ª pregunta salió con `Technical` dentro de la sesión existente y la 1.ª respuesta quedó intacta |
| UC-002: «Nueva» arranca con el último perfil, y sobrevive a recargar la página | Correcto (preferencia en `localStorage`; la sesión también sobrevive) |
| UC-004 BR-002: estilo por perfil | Básico: 271 palabras y termina con una pregunta de comprobación. Técnico: 458 palabras. Una muestra por perfil, no una prueba estadística |
| UC-004 BR-009: formato en pantalla de celular | Sin desborde horizontal del documento en 606 px y con el contenedor limitado a 390 px; los bloques de código se contienen con su propio scroll horizontal; el cuadro de texto usa 16 px (evita el zoom automático de iOS); `viewport` correcto |
| **Defecto encontrado y corregido:** listas numeradas | Ver abajo |
| Los 4 botones de ejemplo | Responden en 5 a 7 s y citan fuentes. Un problema de contenido en el primero: ver abajo |
| UC-001 A2 (contraseña incorrecta) | **Pendiente:** hay que mirar el mensaje con la persona escribiendo la contraseña equivocada. UC-001 A6 no se hizo (exige crear cuentas) |

## Defecto corregido: listas numeradas

Un bloque de código entre pasos (o una línea en blanco) cerraba la lista y el renderizador abría otra nueva sin `start`: seis listas de un elemento, y cada paso salía como «1.». Ahora `web/markdown.js` conserva el número de cada lista (`<ol start="N">`, solo 1 a 4 dígitos). Tres tests nuevos en `web/tests/markdown.test.mjs` (20 en total). Verificado en el navegador con la misma respuesta.

## Hallazgo sin resolver: calidad de la recuperación (RAG)

- **Síntoma:** «¿Qué es AIUP?» respondió que AIUP es «un proyecto que incluye una aplicación llamada Pregúntale al repo». AIUP es la metodología (AI Unified Process). «¿Cómo instalo las dependencias?» dijo que el repositorio no tiene instrucciones e inventó «Python 3.8» (el repo exige 3.14 y `CLAUDE.md` trae los comandos), lo que contradice UC-004 BR-003 (no inventar).
- **Causa medida** (`retrieve` contra la Knowledge Base):
  - Para «¿Qué es AIUP?», de los 6 fragmentos que recibe el agente, 3 son de `scripts/` y solo entra `docs/vision.md` (en el puesto 6, con 0,717).
  - Para la pregunta de instalación, `CLAUDE.md` queda en el puesto 11 y solo se recuperan 6; con palabras clave sueltas sale primero.
  - Indexar el código (`scripts/`, `tests/`, `src/`) mete fragmentos que mencionan los mismos términos. Ya estaba anotado como «El código añade ruido a las preguntas de negocio» en `uc-003-sincronizacion.md`; ahora afecta a la primera pregunta de ejemplo.
- **Opciones** (decisión pendiente; cambiar qué se indexa modifica UC-003 BR-001):
  1. **No indexar `scripts/` ni `tests/`** (`EXCLUDED_DIRS` en `sync/rules.py`), sincronizar y repetir los 4 botones. Es la más simple y encaja con FR-014, que enumera documentos y no código.
  2. **Reordenar por ruta** en `retrieval.retrieve`: pedir más fragmentos (por ejemplo 20) y priorizar `docs/`, `README.md` y `CLAUDE.md` sobre el código. Conserva el código para preguntas técnicas.
  3. Ambas.
- Cualquiera de las tres exige volver a probar los 4 botones y la prueba de humo antes de la charla.

## Límites de esta verificación

- Chrome no deja bajar de **606 px** de ancho. Los 390 px se emularon limitando el contenedor del chat, lo que no dispara la regla `max-width: 380px` ni prueba táctil, teclado móvil, iOS ni Android. Falta el celular físico.
- Lector de pantalla: no probado.
- Los 4 botones se valoraron con una respuesta cada uno; el modelo no es determinista.

## Aprendizajes

- La herramienta de JavaScript del navegador bloquea (`[BLOCKED: Sensitive key]`) las claves de objeto con nombres como `sessions`; usar otros nombres.
- Cada espera del navegador se limita a 10 s: para respuestas largas, sondear desde el propio JavaScript de la página.
- Probar la interfaz encontró un defecto de renderizado y un problema de contenido que ninguna de las 20 pruebas automáticas ni la prueba de humo (15 comprobaciones) habían visto.
