# Cobertura de los casos de uso (auditoría del 2026-09-24)

Auditoría a mano de cada UC contra el código, los tests y las verificaciones reales (`/coverage-check` no está disponible en esta sesión). Método: por cada flujo alterno (A) y regla de negocio (BR) se busca evidencia: un **test** que la ejercite, una **verificación real** con AWS (prueba de humo, prueba en el navegador o medición), o el **código** que la implementa. Sin ninguna de las tres es un **hueco**; si el código hace algo distinto de lo que dice la spec es una **deriva**.

## Aprobación y estados

El autor aprobó los siete UC el 2026-09-24. **Se implementaron antes de aprobarse:** el flujo de trabajo del repo exige `Approved` antes de implementar y aquí se hizo al revés, por el plazo de la charla. Queda constancia para no repetirlo. Los siete pasan a **`Implemented`**; ninguno pasa a `Tested` porque todos tienen al menos un hueco o una deriva sin cerrar (NFR-002 exige 0 huecos y 0 deriva).

| UC | Estado | Resumen |
|---|---|---|
| UC-001 Autenticarse | Implemented | Cubierto; derivas por comportamiento propio de Cognito |
| UC-002 Elegir perfil | Implemented | Cubierto; deriva en A1 y sin tests de la web |
| UC-003 Sincronizar documentos | Implemented | El mejor cubierto; falta probar el `POST` con cambios desde la web |
| UC-004 Consultar al agente | Implemented | Muy cubierto; **A4 sin implementar** y deriva en A1 |
| UC-005 Continuar conversación | Implemented | Cubierto; A4 sin implementar |
| UC-006 Consultar historial | Implemented | Cubierto; A4 sin implementar en la web |
| UC-007 Top 10 de preguntas | Implemented | Muy cubierto; dos derivas documentadas |

## Detalle: qué falta en cada UC

### UC-001 Autenticarse
- **Cubierto:** flujo principal, A1, A4, A5, A8, BR-001, BR-002, BR-003, BR-007 (5 tests de la Lambda y la prueba en el navegador con registro real y sesión de Ponente); BR-006 y BR-008 por configuración de Cognito.
- **Deriva, A3 y BR-005:** la spec dice "5 intentos fallidos = bloqueo de 15 minutos"; Cognito aplica su propio bloqueo progresivo. Decidir: aceptarlo y ajustar la spec, o dejarlo.
- **Deriva menor, A7 y BR-004:** la spec pide "letras y números"; la política de Cognito exige al menos una minúscula y un número.
- **Sin test:** A2 y A6 (los mensajes de error de `web/cognito.js`); se comprobaron a mano.

### UC-002 Elegir perfil de respuesta
- **Cubierto:** flujo principal, A2, A3, A4, BR-001, BR-002, BR-003, BR-004, BR-005 (2 tests del agente y de la API, y la prueba en el navegador).
- **Deriva, A1:** la spec dice que el sistema pide elegir perfil antes de la primera pregunta; la web arranca con **General** ya marcado y no pregunta.
- **Sin test:** que "las conversaciones nuevas arrancan con el último perfil" (usa `localStorage`); no hay tests de la interfaz.

### UC-003 Sincronizar documentos del repositorio
- **Cubierto:** todo, con 13 tests y una sincronización real (59 archivos, 52 cargados, 0 fallos; A2 comprobado en vivo).
- **Hueco:** el `POST /admin/sync` desde la web **con cambios** no se ha ejecutado de punta a punta (solo el estado y la llamada sin cambios). La API corta a los 30 s y una sincronización con muchos cambios podría acercarse.
- **Nota:** BR-008 se cumple con el historial de trabajos de ingesta de Bedrock, no con tabla propia.

### UC-004 Consultar al agente sobre el repositorio
- **Cubierto:** flujo principal, A2, A3, A5, A6, A7, A8, BR-001, BR-002, BR-003, BR-004, BR-005, BR-006, BR-007, BR-008 y BR-010 (33 tests, verificación con Nova 2 Lite y la Knowledge Base reales, trazas y cuotas).
- **Hueco, A4 (datos personales en la pregunta):** **no implementado.** La spec dice que el sistema enmascara el dato personal de la pregunta e informa al participante. Hoy la pregunta se guarda tal cual; el guardrail solo enmascara al modelo, y el informe del Ponente enmascara al mostrarse. El participante no recibe ningún aviso.
- **Deriva, A1 (sesión vencida):** la spec dice que se conserva la pregunta escrita; la web cierra la sesión y la pregunta se pierde.
- **Sin test:** BR-009 (formato legible en celular): se comprobó a mano, no hay test de la interfaz.

### UC-005 Continuar una conversación
- **Cubierto:** flujo principal, A1, A2, BR-002, BR-003, BR-004, BR-005 (2 tests, memoria real comprobada con dos turnos y eventos guardados en AgentCore).
- **Hueco, A4 (memoria no disponible):** **no implementado.** Si la memoria falla, la consulta termina en error (A7 de UC-004) en vez de responder solo con la pregunta actual y avisarlo.
- **Sin test:** A3 y BR-001 (ventana de 10 interacciones): es configuración (`window_size=20`) sin test.
- **Nota:** la memoria de la plataforma conserva 7 días; el límite de 24 h (BR-002) lo aplica la API.

### UC-006 Consultar historial de conversaciones
- **Cubierto:** flujo principal, A1, A2, A3, BR-001, BR-002, BR-003, BR-004 y BR-005 (3 tests y la prueba en el navegador).
- **Hueco, A4:** la API devuelve `has_more` pero la web **no ofrece "mostrar más"**: con más de 20 conversaciones las antiguas son inalcanzables.

### UC-007 Consultar top 10 de preguntas
- **Cubierto:** flujo principal, A1 a A8, BR-001, BR-003 a BR-007, BR-009, BR-010 y BR-011 (20 tests, verificación con 30 preguntas de 7 temas: 7, 5, 5, 4, 4, 3, 2 exactos).
- **Deriva, BR-002:** la spec dice "todas las preguntas almacenadas"; el análisis cubre las **1.000 más recientes** y lo informa. Alcanza para el aforo (unas 750).
- **Deriva, BR-008:** la spec dice 20 s para el informe y 90 s como fallo; el sistema aplica el tiempo límite general de **60 s**. En la práctica tarda 4 a 7 s.

## Requisitos: estado real

| Requisito | Estado | Nota |
|---|---|---|
| FR-002, FR-003, FR-010, FR-011, FR-013 a FR-016, FR-018 a FR-023 | Implementado | Ver los UC |
| FR-017 (herramientas solo para el Ponente) | Implementado | El rol sale del token; los participantes no reciben las herramientas |
| **FR-012 (herramientas por AgentCore Gateway)** | **Parcial** | Las herramientas del Ponente son **locales**, no están detrás de Gateway. Es el requisito de prioridad alta más grande sin cumplir |
| FR-001, FR-004 | Parcial | Falta el caso de prueba TC-001 y una reproducción desde un clon limpio |
| FR-005 a FR-007, FR-009 | Implementado | `docs/charla/` y el flujo por ramas y PR |
| FR-008 (trazabilidad spec-código) | Parcial | Esta auditoría es la primera; falta cerrar los huecos |
| NFR-005, NFR-006, NFR-007, NFR-008, NFR-009, NFR-010, NFR-012, NFR-013, NFR-014 | Implementado | Medidos o probados; ver `docs/charla/` |
| NFR-011 (latencia) | Cumple con el contenedor caliente | La primera pregunta tras un despliegue tarda ~15 s |
| NFR-001 a NFR-003 | Parcial | Se cumplieron con excepciones (el #18 se mergeó antes de sus últimos commits) |
| NFR-004 (reproducibilidad en 30 min) | Sin verificar | Nadie ha reproducido desde un clon limpio |

## Pendiente, por prioridad para la charla (2026-09-26)

1. **AgentCore Gateway (FR-012):** decidir si se implementa o se enmienda el requisito.
2. **TC-001:** el caso de prueba de punta a punta que encadena UC-001, UC-004, UC-005, UC-006 y UC-007.
3. Cerrar los **huecos de UC-004 A4, UC-005 A4 y UC-006 A4**, o dejarlos como alcance declarado.
4. Decidir las **derivas** (UC-001 A3/BR-005, UC-002 A1, UC-004 A1, UC-007 BR-002/BR-008): cambiar el código o ajustar la spec.
5. Probar el **`POST /admin/sync` con cambios** desde la web.
6. Probar la web en un **celular físico** y con lector de pantalla.
7. Ensayo con `scripts/smoke_test.py` unos minutos antes, y vaciar datos con `scripts/reset_event_data.py --yes`.
