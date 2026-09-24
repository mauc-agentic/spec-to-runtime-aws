# Checklist para cerrar pendientes antes de la charla (2026-09-26)

Actualizado el 2026-09-24. `[x]` hecho y verificado; `[ ]` pendiente. **Quién**: yo = el asistente puede hacerlo; tú = requiere a la persona (contraseñas, dispositivos físicos, decisiones o merges).

## Hecho

- [x] FR-012: Gateway con target Lambda y target de servidor MCP de AWS (#23, #27).
- [x] TC-001 escrito, en `Draft` (#24).
- [x] Huecos A4 de UC-004, UC-005 y UC-006 (#25); avisos y «Mostrar más» vistos en un navegador real.
- [x] Las 6 derivas resueltas (#26).
- [x] Prueba de humo reintenta una vez la búsqueda en la documentación de AWS (#28).
- [x] `POST /admin/sync` con cambios probado por la API (13,2 s, 11 nuevos y 28 modificados).
- [x] Falla de ingesta de los `scripts/*.py` (shebang) arreglada: 0 fallidos y los 4 `INDEXED`.
- [x] Las fuentes de la documentación de AWS salen siempre al final de la respuesta del Ponente (antes dependían de que el modelo las citara); prueba de humo 15/15 sin necesitar el reintento.
- [x] Ensayo del 2026-09-24 con `main` ya mergeado (#29): `smoke_test.py` 15/15, sin reintentos; todas las respuestas entre 3 y 8 s con el contenedor caliente (NFR-011 pide 10 s o menos). Knowledge Base sincronizada con `main` (2 nuevos, 11 modificados, 98 escaneados, 0 fallidos).
- [x] Datos de ensayo vaciados con `reset_event_data.py --yes` y verificados con la simulación: 0 preguntas, 0 contadores de cuota y 0 eventos de memoria (había 486 de 32 actores de prueba).
- [x] `main` validado tras los merges: tests, lint, Terraform sin desvío, checkov, validador de UC y CI en verde.

## Antes de la charla

- [x] Calidad de las respuestas (decisión opción 1, 2026-09-24): `tests/` y `scripts/` ya no se indexan. «¿Qué es AIUP?» y «¿Cuánto cuesta la demo?» responden bien y la pregunta de instalación ya no inventa «Python 3.8». Detalle en `pruebas-navegador.md`.
- [x] Pregunta de instalación (2026-09-24): tras el README no bastó; con las bitácoras fuera del índice y `docs/faq.md`, 3 de 3 respuestas por la API traen `uv sync`, `uv run pytest` y Python 3.14. Los cinco botones de ejemplo responden bien.
- [x] Tras mergear el FAQ (#35), la KB se sincronizó desde `main` (`docs/faq.md` indexado, 0 bitácoras, `tests/` ni `scripts/`) y las cinco preguntas de ejemplo, repetidas por la API real, respondieron bien.

- [ ] **Tú:** pulsar «Sincronizar documentos» en la web como Ponente y ver que muestra el estado sin error (la prueba de `POST` fue por la API, no por el botón).
- [ ] **Tú:** probar la web en un celular físico (formato de las respuestas, teclado, historial).
- [ ] **Tú:** probar la web con un lector de pantalla.
- [ ] **Tú:** confirmar los umbrales `Needs review` de NFR-004 y NFR-011 (o pedir que se midan de nuevo).
- [x] Cuenta del Ponente creada el 2026-09-24 con la API de Cognito (sin enviar correo): estado `CONFIRMED`, en el grupo `Ponente` y, con un login por API, el token trae `cognito:groups = ['Ponente']`. La contraseña es aleatoria y se entregó por un archivo temporal de la sesión; cámbiala cuando quieras con `aws cognito-idp admin-set-user-password --user-pool-id <pool> --username <correo> --password '<nueva>' --permanent`. **Si el entorno se destruye, la cuenta desaparece con él** y hay que recrearla.
- [ ] **Tú: probar el login del Ponente en la web** y ver el panel «Herramientas del ponente» (el asistente no escribe contraseñas en el navegador).
- [ ] **Tú, al empezar la charla: abrir el registro.** Está **cerrado** (`registration_open: false`). Comandos en «Operación durante el evento» de `infraestructura-base.md`; ciérralo al terminar. El código del evento se lee del secreto y no se escribe en ningún documento.
- [ ] **5 minutos antes de la charla (tú o yo):** `PYTHONPATH=src uv run python scripts/warmup.py`. Calienta el contenedor (en frío la primera pregunta tarda ~15 s), borra sus cuentas temporales y vacía los datos de ensayo, y **no toca el registro** (a diferencia de `smoke_test.py`, que lo cierra). Solo vacía si no hay preguntas reales guardadas. Verificado el 2026-09-24: 24 s calentando y hasta ~2 minutos con el vaciado; con una pregunta real simulada avisa y no borra nada.
- [ ] **Tú:** decidir si el entorno se destruye esta noche (y se reconstruye para el ensayo) o se deja hasta después de la charla; ver `agentcore-gateway.md` para el orden de reconstrucción.
- [ ] **Después de la charla (yo, si lo pides):** `terraform destroy` y comprobar que no queda ningún recurso de la demo (NFR-014).

## Para poder pasar UC a `Tested`

- [ ] **Tú:** revisar TC-001 (`Draft` → `Reviewed` / `Approved`).
- [ ] **Tú:** decidir sobre UC-008 (búsqueda en la documentación de AWS) o enmendar UC-004 BR-003.
- [x] Pruebas de navegador en vivo de UC-002 y UC-004 BR-009 (2026-09-24): ver `pruebas-navegador.md`. Encontraron y corrigieron un defecto de numeración de listas.
- [x] UC-001 A2 (contraseña incorrecta) verificado en un navegador real el 2026-09-24: mensaje genérico, igual para cuenta existente e inexistente. UC-001 A6 exige crear cuentas y no se hizo.
- [ ] **Automatizar** esas pruebas de navegador (Playwright, con el API y Cognito simulados); hoy la web solo tiene tests de sus módulos puros.
- [ ] **Yo:** automatizar TC-001 (depende de lo anterior y de que el login pueda hacerse sin que yo escriba contraseñas; ver el aprendizaje en `huecos-a4.md`).
- [ ] **Yo:** test de UC-005 A3/BR-001 (ventana de 10 interacciones; hoy es solo configuración).
- [ ] **Tú o yo:** provocar un fallo real de AgentCore Memory para UC-005 A4 (hoy solo con la memoria simulada).
- [ ] **Yo:** reproducir el proyecto desde un clon limpio y medir el tiempo (FR-001, FR-004 y NFR-004).
- [ ] **Tú:** `/coverage-check` no está disponible en la sesión del asistente; correrlo en tu entorno o dar por buena la auditoría manual.

## Riesgos conocidos, sin verificar

- [ ] Vencimiento real del token (el 401 se simuló).
- [ ] Cuántos intentos fallidos y cuánto dura el bloqueo real de Cognito (UC-001 A3 no promete cifras).
- [ ] Contenido malicioso en los fragmentos del servidor MCP de AWS (inyección de prompt); hoy solo hay mitigaciones de diseño.
- [ ] Causa completa de la falla intermitente de la búsqueda en la documentación de AWS: se arregló la parte de las URL sin citar y se mantiene el reintento, pero no se confirmó si hubo otras causas (los spans de aquella ejecución no aparecieron).

## Opcional

- [ ] Políticas Cedar por herramienta en el Gateway (defensa en profundidad).
- [ ] Cerrar FR-008 y NFR-001 a NFR-003, que siguen `Parcial`.

## Notas del ensayo (2026-09-24)

- **Presupuesto:** AWS Budgets marca 0,00 USD gastados y una previsión de 0,02 USD, pero Billing tarda de 8 a 24 horas en reflejar el gasto, así que no es una lectura fiable de lo gastado hoy. La protección real son las cuotas de la API y el corte automático al 90 %.
- **Estado:** `terraform plan` sobre `main`: «No changes». CI de `main` en curso cuando se miró.
- **Entorno:** sigue desplegado y gastando (NFR-014 pide destruirlo al terminar). Reconstruirlo antes de la charla lleva unos minutos, con el orden documentado en `agentcore-gateway.md`.

## Plan de cierre tras la charla (acordado el 2026-09-24)

Orden acordado: primero la prueba de reconstrucción desde cero, después destruir.

1. **Capturar datos reales antes de destruir (yo, en modo lectura):** el top de preguntas y la actividad (anónimos), la latencia real (p50 y p95, para confirmar NFR-011), tokens y estimación de costo. La tabla de preguntas, los logs y las trazas se pierden al destruir.
2. **Prueba de reconstrucción (NFR-004, FR-004):** con `docs/charla/reconstruccion.md` en la mano, destruir, crear todo desde un clon limpio siguiendo solo ese documento, medir el tiempo total y por fase contra los 30 minutos, y volver a destruir. Anotar todo paso manual que el documento no recoja.
3. **Mejoras que la prueba debe decidir** (se aplican durante la reconstrucción, no antes, para no dejar el entorno de la charla con cambios pendientes): quitar la fase 1 con `-target` haciendo que la política del orquestador no dependa del ARN del Runtime, y declarar en Terraform el grupo de logs del Runtime, que hoy `destroy` deja atrás (ya hay uno huérfano del entorno anterior).
4. **Comprobar que no queda nada (NFR-014):** el barrido por etiqueta debe dar 0 y no debe quedar ningún grupo de logs `/aws/bedrock-agentcore/runtimes/...`. Decidir si se conserva el bucket del estado (`prevent_destroy`; guarda el estado, con valores sensibles).
5. **Gasto real:** Billing tarda de 8 a 24 horas en reflejarlo; mirar 1 o 2 días después y comparar el costo por consulta con los 0,010 USD estimados (NFR-012). El historial de costos sobrevive al `destroy`.
6. **Cierre en AIUP y en el repositorio:** estados de los UC y TC-001, requisitos `Parcial` y `Needs review`, pendientes sin hacer convertidos en issues, retrospectiva en `docs/charla/`, ramas mergeadas, archivos temporales y un tag del estado de la charla.
