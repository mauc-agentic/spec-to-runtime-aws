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
- [x] `main` validado tras los merges: tests, lint, Terraform sin desvío, checkov, validador de UC y CI en verde.

## Antes de la charla

- [ ] **Tú:** pulsar «Sincronizar documentos» en la web como Ponente y ver que muestra el estado sin error (la prueba de `POST` fue por la API, no por el botón).
- [ ] **Tú:** probar la web en un celular físico (formato de las respuestas, teclado, historial).
- [ ] **Tú:** probar la web con un lector de pantalla.
- [ ] **Tú:** confirmar los umbrales `Needs review` de NFR-004 y NFR-011 (o pedir que se midan de nuevo).
- [ ] **Yo, el día del ensayo:** `scripts/smoke_test.py` (15 comprobaciones) unos minutos antes, para calentar el contenedor (la primera pregunta tarda ~15 s en frío).
- [ ] **Yo, tras el ensayo:** `scripts/reset_event_data.py --yes` para arrancar limpio, sin `--users` si el Ponente ya existe.
- [ ] **Tú:** decidir si el entorno se destruye esta noche (y se reconstruye para el ensayo) o se deja hasta después de la charla; ver `agentcore-gateway.md` para el orden de reconstrucción.
- [ ] **Después de la charla (yo, si lo pides):** `terraform destroy` y comprobar que no queda ningún recurso de la demo (NFR-014).

## Para poder pasar UC a `Tested`

- [ ] **Tú:** revisar TC-001 (`Draft` → `Reviewed` / `Approved`).
- [ ] **Tú:** decidir sobre UC-008 (búsqueda en la documentación de AWS) o enmendar UC-004 BR-003.
- [ ] **Yo:** pruebas de navegador para UC-002 (perfil), UC-004 BR-009 (formato en celular) y UC-001 A2/A6 (mensajes de error). Hoy la web solo tiene tests de sus módulos puros.
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
