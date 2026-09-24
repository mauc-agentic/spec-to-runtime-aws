# UC-003 Sincronización del repositorio: resultados reales

Implementado en `src/spec_to_runtime/sync/` y `infra/sync.tf` (Lambda `spec-to-runtime-sync`). El caso de uso sigue en `Draft` hasta que el autor lo apruebe. Probado con GitHub y AWS reales el 2026-09-24.

## Qué hace

Lista la rama `main` en GitHub, aplica las reglas de UC-003 (BR-001 y BR-003), compara la versión (sha de git guardado como metadato del objeto) con lo ya cargado en S3, sube lo nuevo o cambiado, borra lo eliminado y lanza la ingesta de la Knowledge Base. `{"action": "status"}` devuelve el progreso. El rol Ponente se exigirá en la API (A1); hasta entonces se invoca con `aws lambda invoke`.

```bash
aws lambda invoke --function-name spec-to-runtime-sync --payload '{}' --cli-binary-format raw-in-base64-out out.json && cat out.json
aws lambda invoke --function-name spec-to-runtime-sync --payload '{"action":"status"}' --cli-binary-format raw-in-base64-out out.json && cat out.json
```

## Resultados

| Prueba | Resultado |
|---|---|
| Primera sincronización | 59 archivos en `main`; 52 cargados, 7 omitidos (candados de dependencias y archivos sin texto útil); 0 fallos |
| Ingesta de la Knowledge Base | `COMPLETE`, 50 documentos indexados, 0 fallidos, unos 2,5 minutos |
| Segunda sincronización con la ingesta en curso (A2) | `AlreadyRunning`, sin lanzar otra |
| Recuperación por tipo de archivo | Markdown, PlantUML, Terraform, Python, TOML, JSON y YAML se recuperan con puntuaciones de 0,71 a 0,87 |

## Calibración de la relevancia mínima

La puntuación de Titan **no discrimina bien**: preguntas sin relación con el repo (capital de Francia, receta de arepas, fútbol) puntúan **0,60 a 0,64**; las relacionadas, incluso coloquiales, **0,69 a 0,87**. El valor provisional de 0,3 nunca habría activado "sin fuente". Se fijó **`MIN_RELEVANCE = 0,66`**. El margen es estrecho (0,02 a 0,03): conviene revisarlo si cambia el corpus.

## Calidad de las respuestas con el corpus real

- Fuera de tema: "sin fuente" sin llamar al modelo (0 tokens), como pide UC-004 A5.
- **El modelo rellenaba lo que las fuentes no dicen.** A "¿por qué Terraform y no CDK?" (el repo solo dice que se descartó CDK) respondió con "razones estratégicas" inventadas. Se corrigió con una regla explícita en el prompt ("no infieras, no supongas"); ahora responde que el repositorio no detalla las razones. Hay un test que fija la regla en los tres perfiles.
- Con más fragmentos (6 en lugar de 4) aparecen más documentos correctos (por ejemplo UC-001 al preguntar por el registro), a costa de unos 1.000 tokens más de entrada.

## Problemas conocidos

- **El código añadía ruido a las preguntas de negocio (resuelto en parte el 2026-09-24):** indexar `tests/` y `scripts/` desplazaba a `docs/vision.md` y `CLAUDE.md` de los 6 fragmentos que recibe el agente: «¿Qué es AIUP?» respondía que era una aplicación. Desde el 2026-09-24 esas dos carpetas **no se indexan** (`NOISE_DIRS` en `sync/rules.py`; UC-003 BR-001 actualizado; la sincronización quitó 16 archivos y la KB quedó con 0 fallidos). `src/`, `infra/` y `web/` siguen indexados: pueden seguir colándose fragmentos de código en preguntas coloquiales.
- **Probable explicación de los 2 objetos que faltaban (sin confirmar):** en aquel momento había scripts con shebang, que Bedrock rechaza (ver el aprendizaje del 2026-09-24 más abajo). Lo original sigue así:
- **Faltan 2 objetos por explicar:** se subieron 52 y la ingesta contó 50, sin marcar ninguno como omitido ni fallido. Los siete tipos de archivo son recuperables, así que no afecta a lo probado; queda por identificar cuáles son.
- **No hay registro propio de cada sincronización:** UC-003 BR-008 se cumple con el historial de trabajos de ingesta de Bedrock (documentos examinados y fallidos, inicio y fin), sin tabla adicional.

## Aprendizajes / dolores

- `python3` del sistema (Homebrew 3.14) no tiene boto3: para scripts sueltos, `uv run python`.
- El zip de Lambda incluía `__pycache__`, cuyo contenido depende de la máquina y cambiaría el hash entre tu Mac y el CI: se excluyó explícitamente.
- **Bedrock rechaza los `.py` que empiezan con shebang (2026-09-24).** Cada ingesta terminaba `COMPLETE` pero con 4 documentos fallidos («formato no soportado»): los cuatro `scripts/*.py`, todos con `#!/usr/bin/env python3`. Se confirmó con dos archivos de prueba, con y sin shebang: solo el primero falló. La sincronización ahora sube los `.py` sin esa primera línea (`prepare_body` en `sync/sync.py`; el original en GitHub no cambia). Como un archivo sin cambios no se vuelve a subir, los 4 ya cargados se migraron borrando su copia del bucket y sincronizando de nuevo: 0 fallidos y los 4 `INDEXED`.
- **Que la ingesta diga `COMPLETE` no significa que todo se indexó.** Mirar siempre `documents_failed` y `failureReasons` del trabajo (`aws bedrock-agent get-ingestion-job`). El error solo se vio al probar `POST /admin/sync` con cambios y leer las estadísticas.
- **Cifras de la prueba de `POST /admin/sync` con cambios:** 130 archivos examinados, 11 nuevos, 28 modificados, 0 eliminados y 65 sin cambios; respuesta en 13,2 s; ingesta de unos 2,5 minutos.
- En zsh, `GID` es una variable especial: asignarla falla con «failed to change group ID» (ya anotado en `agentcore-gateway.md`).
- **Medir la recuperación con `retrieve` ahorra pruebas a ciegas (2026-09-24).** Consultar la Knowledge Base directamente (puntuación y ruta de cada fragmento) mostró por qué fallaban las respuestas, y confirmó la mejora tras quitar `tests/` y `scripts/`: para «¿Qué es AIUP?», `docs/vision.md` pasó del puesto 6 a ocupar 2 de los 6 fragmentos junto con `CLAUDE.md`. Ver `pruebas-navegador.md`.
- **La KB se sincroniza desde `main` en GitHub:** un cambio de contenido solo se ve tras mergearlo. Sincronizar desde una rama local devuelve `NoChanges`.
