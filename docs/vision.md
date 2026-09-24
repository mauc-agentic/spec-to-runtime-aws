# Vision: spec-to-runtime-aws

> Borrador inicial derivado del contexto del repo y de la charla. Los puntos marcados **(por confirmar)** deben ser validados por el autor antes de pasar a `Reviewed`.

## Mission

Mostrar, con un ejemplo real y reproducible, cómo llevar una especificación hasta un sistema corriendo en AWS usando AIUP (AI Unified Process): visión, requisitos, modelo de entidades, casos de uso y casos de prueba son la fuente de verdad, y el código, las pruebas y el despliegue se derivan y se mantienen alineados con ellos. El repositorio sirve como material de una charla: documenta el paso a paso, los temas de interés, las buenas prácticas y los dolores vividos, y aloja las demos.

## Target users

- **Asistentes a la charla (desarrolladores y arquitectos):** quieren ver un flujo spec-driven de punta a punta y poder repetirlo en sus propios proyectos.
- **Presentador (autor):** necesita un repositorio ordenado, con demos que funcionen y documentación al día para mostrar en vivo.
- **Lectores posteriores del repo:** llegan sin haber asistido y necesitan entender los pasos y las decisiones leyendo solo `docs/`.

## Goals

- Cada demo se puede reproducir desde cero siguiendo únicamente la documentación del repo, y su infraestructura se levanta y destruye con IaC **(por confirmar: número de demos)**.
- Todo caso de uso o caso de prueba implementado tiene su especificación en `docs/` con estado actualizado y cobertura verificada (`/coverage-check` sin gaps ni drift).
- Los aprendizajes (pasos, buenas prácticas, dolores) quedan registrados en `docs/charla/` en el momento en que ocurren.

## Scope

### In scope

- Documentación AIUP completa: visión, requisitos, modelo de entidades, diagrama y especificaciones de casos de uso, casos de prueba.
- Una aplicación de demostración implementada a partir de esas especificaciones: un agente en Python con Strands Agents, ejecutado en Amazon Bedrock AgentCore **(por confirmar: dominio de la aplicación)**.
- Infraestructura en AWS definida 100 % como código (IaC): API Gateway, Lambda, AgentCore, CloudWatch, SQS y Secrets Manager **(por confirmar: herramienta de IaC, p. ej. CDK o Terraform)**.
- Uso del servidor MCP de AWS para integrar herramientas de los servicios con el agente.
- Registro de buenas prácticas y problemas encontrados durante el proceso.
- Flujo de trabajo por ramas: cada spec, UC o TC nuevo en su rama, con merge a `main` solo tras pruebas y certificación.

### Out of scope

- Ser una plataforma o producto de uso productivo.
- Cubrir servicios de AWS distintos de los listados en Constraints, o stacks distintos de Python + Strands.
- Material de la charla en otros formatos (diapositivas, video) dentro de este repo.

## Constraints

- La metodología es AIUP; `aiup-core` genera la documentación. El plugin `aiup-vaadin-jooq` no aplica porque el stack no es Vaadin/jOOQ.
- Stack: Python + Strands Agents. Se eligió porque es el framework de agentes de AWS, integra con más facilidad las herramientas de los servicios AWS y ofrece un servidor MCP.
- Servicios AWS: API Gateway, Lambda, Bedrock AgentCore, CloudWatch, SQS y Secrets Manager, todos aprovisionados por IaC.
- Nada se mergea a `main` sin pruebas en verde y cobertura del spec certificada.
- Fecha de la charla: **2026-09-26**. Condiciona el alcance.

## Success measures

- Un tercero puede clonar el repo y reproducir una demo siguiendo solo `docs/`.
- El 100 % de los UC en estado `Implemented` o superior tienen cobertura verificada sin drift entre spec, código y tests.
- Las demos se ejecutan en vivo durante la charla sin intervención manual fuera de lo documentado.
