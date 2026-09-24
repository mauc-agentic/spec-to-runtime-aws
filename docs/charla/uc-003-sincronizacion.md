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

- **El código añade ruido a las preguntas de negocio:** indexar `src/` y `tests/` hace que preguntas coloquiales devuelvan fragmentos de código. Se mitigó pidiendo preferir `docs/`, pero la búsqueda es solo semántica (S3 Vectors no ofrece búsqueda híbrida). Si molesta en la demo, se puede excluir `tests/` en `rules.py`.
- **Faltan 2 objetos por explicar:** se subieron 52 y la ingesta contó 50, sin marcar ninguno como omitido ni fallido. Los siete tipos de archivo son recuperables, así que no afecta a lo probado; queda por identificar cuáles son.
- **No hay registro propio de cada sincronización:** UC-003 BR-008 se cumple con el historial de trabajos de ingesta de Bedrock (documentos examinados y fallidos, inicio y fin), sin tabla adicional.

## Aprendizajes / dolores

- `python3` del sistema (Homebrew 3.14) no tiene boto3: para scripts sueltos, `uv run python`.
- El zip de Lambda incluía `__pycache__`, cuyo contenido depende de la máquina y cambiaría el hash entre tu Mac y el CI: se excluyó explícitamente.
