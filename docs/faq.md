# Preguntas frecuentes

Respuestas breves a las preguntas que más se hacen sobre este repositorio y la demo «Pregúntale al repo». Cada una remite al documento con el detalle.

## ¿Qué es AIUP?

AIUP (AI Unified Process, https://unifiedprocess.ai) es una **metodología de desarrollo** en la que la especificación es la fuente de verdad y el código se deriva de ella. El sistema se documenta con la visión, los requisitos, el modelo de entidades, el diagrama y las especificaciones de casos de uso, y los casos de prueba; el código, los tests y el despliegue se construyen a partir de esos documentos y se mantienen alineados con ellos.

En este repositorio se usa AIUP para llevar una especificación hasta un sistema corriendo en AWS. AIUP no es la aplicación: «Pregúntale al repo» es el ejemplo que se construye siguiendo la metodología. Ver `docs/vision.md` y `CLAUDE.md`.

## ¿Cuánto cuesta la demo?

- **Presupuesto duro:** 50 USD para todo el proyecto (desarrollo, pruebas, ensayos y la charla). La meta de planificación es 30 USD, con 20 USD de reserva.
- **Por consulta:** se estima en 0,0072 USD y se planifica con 0,010 USD.
- **La charla:** 50 personas con 15 preguntas cada una son 750 consultas, unos 7,5 USD.
- **Límites:** 25 consultas por participante y día, 100 para el Ponente y 3.000 en total. Hay alertas de presupuesto al 50 %, 80 % y 100 %, y un corte automático al 90 % (45 USD).

Ver `docs/charla/presupuesto.md`.

## ¿Cómo protege el agente sus respuestas?

- **Guardrails de Bedrock** revisan la pregunta y la respuesta: bloquean los intentos de manipular al agente y los temas fuera de alcance, ocultan correos y teléfonos y bloquean claves de AWS.
- **Datos personales:** la API oculta los correos y teléfonos de la pregunta antes de guardarla y avisa a la persona.
- **Solo desde el repositorio:** las respuestas salen de los documentos indexados, con un enlace a cada fuente; si no hay fuente, el agente lo dice y no inventa.
- **Acceso:** solo entra quien crea una cuenta con el código del evento. Cada persona ve únicamente sus conversaciones, y el análisis de preguntas es anónimo y exclusivo del Ponente.
- **Cuotas** por persona y un tope global.

Ver `docs/use_cases/UC-004-consultar-al-agente-sobre-el-repositorio.md`.

## ¿Qué diferencia hay entre los perfiles?

Hay tres perfiles, y la misma pregunta se responde según el elegido:

- **Básico:** explica paso a paso, define los términos técnicos y termina con una pregunta corta para comprobar que se entendió.
- **Técnico:** es detallado y directo, menciona los trade-offs y remite a las decisiones registradas en el repositorio.
- **General:** es corto y claro, sin jerga, con la idea principal primero.

El perfil se puede cambiar en cualquier momento y aplica desde la siguiente pregunta. General viene seleccionado por defecto. Ver `docs/use_cases/UC-002-elegir-perfil-de-respuesta.md`.

## ¿Cómo instalo las dependencias y corro los tests?

```bash
uv sync
uv run pytest
```

Se necesita Python 3.14 y `uv`. Los tests de la web se corren con `cd web && node --test`. Los demás comandos están en `README.md`.
