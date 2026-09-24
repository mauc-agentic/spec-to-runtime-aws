# Cierre de los huecos A4 de UC-004, UC-005 y UC-006

Estado: **desplegado y verificado con la prueba de humo (13/13) el 2026-09-24**. Los tres eran flujos alternos que la auditoría (`cobertura-ucs.md`) marcó como no implementados.

## UC-004 A4: datos personales en la pregunta

- **Dónde:** en la API (`common/privacy.py`, llamado desde `submit_question`), antes de guardar y de encolar. Así la pregunta nunca se almacena con el dato original y el modelo tampoco lo ve.
- **Qué:** correos y teléfonos, con los mismos marcadores que el guardrail (`{EMAIL}`, `{PHONE}`). Un teléfono es una secuencia de 9 a 15 dígitos con separadores: así no se enmascaran fechas (`2026-09-26`) ni años.
- **Aviso:** la respuesta de la API lleva `masked` y la pregunta enmascarada; la solicitud guarda `notices: ["personal_data_masked"]`. La web reemplaza el texto de la burbuja y muestra «Oculté datos personales de tu pregunta antes de enviarla», y el aviso reaparece en el historial.
- **Cuota:** la consulta sigue en el paso 5 del flujo, así que cuenta como uso. Una consulta rechazada por límite también se guarda enmascarada.
- **Por qué no `ApplyGuardrail`:** habría añadido latencia, costo y permisos a la API, y su respuesta no distingue bien un dato enmascarado de una pregunta bloqueada. La expresión regular es determinista y gratis. Contra: solo cubre los tipos que el guardrail ya anonimiza.

## UC-005 A4: memoria no disponible

- **Dónde:** `build_agent` en `agent/factory.py`. Strands lee la memoria al crear el agente; si falla, se reconstruye sin memoria y se marca `memory_degraded`.
- **Aviso:** el agente emite un evento `notice`, el orquestador lo guarda en `notices` y la web muestra «No pude recordar lo anterior: respondo solo con tu pregunta actual».
- **Límite conocido:** si la memoria falla después (al guardar el turno), la consulta sigue terminando en error. No se ha provocado un fallo real de AgentCore Memory; solo hay tests con la memoria simulada.

## UC-006 A4: mostrar más conversaciones

- `GET /sessions?offset=N` devuelve 20 conversaciones desde `N`, con `has_more`; un `offset` no válido cuenta como 0. La web añade el botón «Mostrar más» al final de la lista.
- **Límite:** la API lee las últimas 200 consultas del usuario y las agrupa; más allá de eso no hay páginas.

## Aprendizajes

- **Los avisos son un solo mecanismo.** Los tres casos (dato enmascarado, memoria caída y, a futuro, otros) usan la lista `notices` de la solicitud y un diccionario de textos en la web (`web/errors.js`), sin un campo por aviso.
- **Cada cambio de comportamiento del agente exige imagen nueva:** commit, `scripts/deploy_agent.sh` y `terraform apply` (que también sube la web y actualiza las Lambdas).
- **Verificado en un navegador real el 2026-09-24** (cuenta de prueba con 22 conversaciones sembradas): el aviso «Oculté datos personales…» aparece sobre la respuesta y la burbuja muestra `{EMAIL}`; el historial pasa de 20 a 23 conversaciones con «Mostrar más», que desaparece al final. Sigue sin probarse el aviso de memoria caída.

## Derivas cerradas después (2026-09-24)

- **UC-004 A1 (sesión vencida):** la web guarda la pregunta con la cuenta a la que pertenece (`state.pending`) y la devuelve al cuadro al volver a entrar con esa misma cuenta; con otra cuenta no se restaura, y salir a propósito la descarta. Probado con un 401 simulado en la página: la sesión vencida real no se probó.
- **Cinco derivas resueltas en la spec** (UC-001 A3/BR-005 y A7/BR-004, UC-002 A1, UC-007 BR-002 y BR-008), más el paso 7 de UC-001 y una precondición de UC-004 que suponían lo contrario. El detalle está en `cobertura-ucs.md`.
- **Aprendizaje:** una afirmación de la auditoría ("el informe ya lo dice") resultó falsa al revisar el código. Antes de ajustar una spec al comportamiento actual, hay que comprobar que ese comportamiento existe.
- **Aprendizaje sobre las pruebas en navegador:** el asistente no puede escribir contraseñas, así que el login lo hace la persona en la pestaña que controla Claude (la sesión es por pestaña). Se sembraron datos directamente en DynamoDB para no gastar modelo y se borraron al terminar.
