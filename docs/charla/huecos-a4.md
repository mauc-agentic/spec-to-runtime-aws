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
- **Lo que no se verificó:** la web solo se comprobó que se sirve con el JS nuevo. Los avisos y «Mostrar más» no se han visto en un navegador.
