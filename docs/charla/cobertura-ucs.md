# Cobertura de los casos de uso (auditoría del 2026-09-24)

Auditoría a mano de cada UC contra el código, los tests y las verificaciones reales (`/coverage-check` no está disponible en esta sesión). Método: por cada flujo alterno (A) y regla de negocio (BR) se busca evidencia: un **test** que la ejercite, una **verificación real** con AWS (prueba de humo, prueba en el navegador o medición), o el **código** que la implementa. Sin ninguna de las tres es un **hueco**; si el código hace algo distinto de lo que dice la spec es una **deriva**.

## Aprobación y estados

El autor aprobó los siete UC el 2026-09-24. **Se implementaron antes de aprobarse:** el flujo de trabajo del repo exige `Approved` antes de implementar y aquí se hizo al revés, por el plazo de la charla. Queda constancia para no repetirlo. Los siete pasan a **`Implemented`**; ninguno pasa a `Tested` porque todos tienen al menos un hueco o una deriva sin cerrar (NFR-002 exige 0 huecos y 0 deriva).

| UC | Estado | Resumen |
|---|---|---|
| UC-001 Autenticarse | Implemented | Cubierto; spec ajustada a Cognito el 2026-09-24 (bloqueo y contraseña) |
| UC-002 Elegir perfil | Implemented | Cubierto; spec ajustada (General por defecto) y sin tests de la web |
| UC-003 Sincronizar documentos | Implemented | El mejor cubierto; el `POST` con cambios se probó el 2026-09-24 (a mano, por la API y sin navegador) |
| UC-004 Consultar al agente | Implemented | Muy cubierto; A4 y la deriva de A1 cerradas el 2026-09-24 |
| UC-005 Continuar conversación | Implemented | Cubierto; A4 cerrado el 2026-09-24 (con un límite: ver abajo) |
| UC-006 Consultar historial | Implemented | Cubierto; A4 cerrado el 2026-09-24 |
| UC-007 Top 10 de preguntas | Implemented | Muy cubierto; derivas cerradas el 2026-09-24 |

## Detalle: qué falta en cada UC

### UC-001 Autenticarse
- **Cubierto:** flujo principal, A1, A4, A5, A8, BR-001, BR-002, BR-003, BR-007 (5 tests de la Lambda y la prueba en el navegador con registro real y sesión de Ponente); BR-006 y BR-008 por configuración de Cognito.
- **Deriva resuelta, A3 y BR-005:** la spec pasa a "bloqueo temporal decidido por Cognito, sin cifras". No se ha comprobado aquí cuántos intentos ni cuánto dura el bloqueo real; la spec no promete ninguna cifra.
- **Deriva resuelta, A7 y BR-004:** la spec pide ahora 8 caracteres, una minúscula y un número, que es la política real de Cognito.
- **Sin test:** A2 y A6 (los mensajes de error de `web/cognito.js`); se comprobaron a mano.

### UC-002 Elegir perfil de respuesta
- **Cubierto:** flujo principal, A2, A3, A4, BR-001, BR-002, BR-003, BR-004, BR-005 (2 tests del agente y de la API, y la prueba en el navegador).
- **Deriva resuelta, A1:** la spec pasa a "General preseleccionado y cambiable en cualquier momento" (también el paso 7 de UC-001 y la precondición de UC-004).
- **Sin test:** que "las conversaciones nuevas arrancan con el último perfil" (usa `localStorage`); no hay tests de la interfaz.

### UC-003 Sincronizar documentos del repositorio
- **Cubierto:** todo, con 13 tests y una sincronización real (59 archivos, 52 cargados, 0 fallos; A2 comprobado en vivo).
- **Hueco cerrado el 2026-09-24:** `POST /admin/sync` con cambios reales (11 nuevos y 28 modificados) respondió 200 en 13,2 s, dentro del corte de 30 s de la API, y la ingesta terminó `COMPLETE`. Se llamó por la API con un Ponente temporal, no desde el botón de la web. La prueba destapó un fallo que la sincronización arrastraba: 4 documentos fallidos en cada ingesta por el shebang de los `scripts/*.py`; arreglado (ver `uc-003-sincronizacion.md`).
- **Nota:** BR-008 se cumple con el historial de trabajos de ingesta de Bedrock, no con tabla propia.

### UC-004 Consultar al agente sobre el repositorio
- **Cubierto:** flujo principal, A2, A3, A5, A6, A7, A8, BR-001, BR-002, BR-003, BR-004, BR-005, BR-006, BR-007, BR-008 y BR-010 (33 tests, verificación con Nova 2 Lite y la Knowledge Base reales, trazas y cuotas).
- **Cubierto, A4 (datos personales en la pregunta):** la API enmascara correos y teléfonos (`{EMAIL}`, `{PHONE}`) antes de guardar y de encolar, cuenta la consulta y avisa en la web, que además muestra la pregunta ya enmascarada (tests de `common/privacy.py` y de la API, y la prueba de humo). Alcance: solo correos y teléfonos, los tipos que el guardrail ya anonimiza; otros datos personales (nombres, direcciones) no se detectan. Ver `docs/charla/huecos-a4.md`.
- **Deriva resuelta, A1 (sesión vencida):** al vencer la sesión al enviar, la pregunta escrita vuelve al cuadro cuando se entra con la misma cuenta (nunca con otra). Comprobado en un navegador real con un 401 simulado; el vencimiento real del token no se ha probado.
- **Sin test:** BR-009 (formato legible en celular): se comprobó a mano, no hay test de la interfaz.

### UC-005 Continuar una conversación
- **Cubierto:** flujo principal, A1, A2, BR-002, BR-003, BR-004, BR-005 (2 tests, memoria real comprobada con dos turnos y eventos guardados en AgentCore).
- **Cubierto, A4 (memoria no disponible):** si la memoria falla **al crear el agente** (que es cuando Strands la lee), el agente responde solo con la pregunta actual y la web lo avisa. **Límite:** si la memoria falla después, al guardar el turno, la consulta sigue terminando en error (A7 de UC-004). Cubierto con tests; no se ha provocado un fallo real de AgentCore Memory.
- **Sin test:** A3 y BR-001 (ventana de 10 interacciones): es configuración (`window_size=20`) sin test.
- **Nota:** la memoria de la plataforma conserva 7 días; el límite de 24 h (BR-002) lo aplica la API.

### UC-006 Consultar historial de conversaciones
- **Cubierto:** flujo principal, A1, A2, A3, BR-001, BR-002, BR-003, BR-004 y BR-005 (3 tests y la prueba en el navegador).
- **Cubierto, A4:** la API pagina con `?offset=` de 20 en 20 y la web ofrece "Mostrar más" (tests de la API y de la prueba de humo; la web solo se ha comprobado que se sirve, sin prueba en navegador). **Límite:** la API lee las últimas 200 consultas del usuario, así que más allá de ellas no hay páginas (con 25 preguntas por día alcanza para 8 días).

### UC-007 Consultar top 10 de preguntas
- **Cubierto:** flujo principal, A1 a A8, BR-001, BR-003 a BR-007, BR-009, BR-010 y BR-011 (20 tests, verificación con 30 preguntas de 7 temas: 7, 5, 5, 4, 4, 3, 2 exactos).
- **Deriva resuelta, BR-002:** la spec pasa a "como máximo las 1.000 preguntas más recientes" y el informe lo dice explícitamente cuando se llega al tope (test). Antes solo mostraba el total analizado, sin decir que había recorte.
- **Deriva resuelta, BR-008:** la spec pasa a 20 s típico y 60 s como límite general. En la práctica tarda 4 a 7 s con todo caliente.

## Requisitos: estado real

| Requisito | Estado | Nota |
|---|---|---|
| FR-002, FR-003, FR-010, FR-011, FR-013 a FR-016, FR-018 a FR-023 | Implementado | Ver los UC |
| FR-017 (herramientas solo para el Ponente) | Implementado | El rol sale del token; los participantes no reciben las herramientas |
| FR-012 (herramientas por AgentCore Gateway) | Implementado | Dos targets: Lambda (las tres herramientas del Ponente) y el servidor MCP público de conocimiento de AWS (búsqueda en su documentación). Verificado con la prueba de humo y con el span de la llamada; ver `docs/charla/agentcore-gateway.md` |
| FR-001, FR-004 | Parcial | TC-001 escrito (`Draft`, sin automatizar); falta una reproducción desde un clon limpio |
| FR-005 a FR-007, FR-009 | Implementado | `docs/charla/` y el flujo por ramas y PR |
| FR-008 (trazabilidad spec-código) | Parcial | Esta auditoría es la primera; falta cerrar los huecos |
| NFR-005, NFR-006, NFR-007, NFR-008, NFR-009, NFR-010, NFR-012, NFR-013, NFR-014 | Implementado | Medidos o probados; ver `docs/charla/` |
| NFR-011 (latencia) | Cumple con el contenedor caliente | La primera pregunta tras un despliegue tarda ~15 s |
| NFR-001 a NFR-003 | Parcial | Se cumplieron con excepciones (el #18 se mergeó antes de sus últimos commits) |
| NFR-004 (reproducibilidad en 30 min) | Sin verificar | Nadie ha reproducido desde un clon limpio |

## Pendiente, por prioridad para la charla (2026-09-26)

1. ~~AgentCore Gateway (FR-012)~~ Hecho el 2026-09-24 con los dos targets (Lambda y servidor MCP de AWS).
2. ~~**TC-001**~~ Escrito en `docs/test_cases/TC-001-conversacion-y-analisis-del-ponente.md` (`Draft`, falta la revisión del autor). Sigue sin automatizarse: la web no tiene pruebas de navegador.
3. ~~Cerrar los huecos de UC-004 A4, UC-005 A4 y UC-006 A4~~ Cerrados el 2026-09-24 (`docs/charla/huecos-a4.md`); los avisos de enmascarado y "Mostrar más" se vieron en un navegador real; falta solo la prueba de memoria caída de verdad.
4. ~~Decidir las derivas~~ Resueltas el 2026-09-24: UC-004 A1 en código; UC-001, UC-002, UC-004 y UC-007 en la spec (UC-007 BR-002 en ambos).
5. ~~Probar el `POST /admin/sync` con cambios~~ Hecho por la API el 2026-09-24; queda pulsar el botón en la web.
6. Probar la web en un **celular físico** y con lector de pantalla.
7. Ensayo con `scripts/smoke_test.py` unos minutos antes, y vaciar datos con `scripts/reset_event_data.py --yes`.
