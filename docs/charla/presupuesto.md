# Presupuesto: 50 USD para 50 participantes

Límite duro de **50 USD** para todo el proyecto (desarrollo, pruebas, ensayos y la charla). Aforo esperado: 50 participantes. Fecha del análisis: 2026-09-23. Región `us-east-1`.

## Tarifas usadas

Verificadas con la API de precios de AWS (`aws pricing get-products`):

| Servicio | Tarifa |
|---|---|
| Nova 2 Lite, entrada | 0,33 USD por millón de tokens (derivado de los precios `priority` y `batch`) |
| Nova 2 Lite, salida | 2,75 USD por millón de tokens (ídem) |
| AgentCore Runtime | 0,1276 USD por vCPU-hora y 0,0169 USD por GB-hora (solo consumo activo) |
| AgentCore Gateway | 0,000005 USD por invocación |
| AgentCore Memory, corto plazo | 0,00025 USD por evento |

**No verificadas** (la API de precios no las expone; tarifas publicadas de memoria, revisar antes de la charla): Bedrock Guardrails, 0,15 USD por 1.000 unidades de texto (filtros de contenido y temas) y 0,10 USD (PII); Titan Text Embeddings v2, 0,02 USD por millón de tokens; S3 Vectors, del orden de centavos para un corpus de `docs/`; API Gateway HTTP, 1 USD por millón de requests.

## Costo por consulta (RAG síncrona)

Supuestos conservadores: 2 llamadas al modelo con 4.000 tokens de entrada cada una, 700 tokens de salida, 12 s de runtime activo con 1 vCPU y 2 GB, 4 unidades de guardrails.

| Concepto | USD por consulta |
|---|---|
| Modelo (Nova 2 Lite) | 0,0046 |
| Guardrails | 0,0016 |
| AgentCore Runtime | 0,0005 |
| Gateway, Memory, API Gateway y otros | 0,0005 |
| **Total** | **0,0072** |

Se planifica con **0,010 USD por consulta** para cubrir lo que no está modelado (logs, reintentos).

## Escenarios

| Escenario | Consultas | USD |
|---|---|---|
| La charla: 50 personas x 15 preguntas | 750 | 7,5 |
| Plan base: desarrollo, pruebas, ensayos y charla | 1.500 | 15 |
| **Tope de diseño** (cuota global) | **3.000** | **30** |
| Límite si se agotara todo el presupuesto | 5.000 | 50 |

Los costos fijos (Secrets Manager, CloudWatch, S3 y state) suman centavos por día. El tope de diseño deja **20 USD de reserva** para errores del modelo de costos.

## Controles (requisitos NFR-012 a NFR-014)

1. **Cuotas en runtime:** 25 consultas por usuario y por día, tope global de 3.000, 800 tokens de salida máximos y 3 llamadas a herramientas por consulta. Superado el límite, la API responde con error sin invocar al modelo. El mecanismo (contador por usuario) se decide en la spec de UC-003.
2. **Registro abierto:** con un repo público, el registro de usuarios debe estar controlado (usuarios creados por el presentador o código de evento); un token público sin control es el mayor riesgo de gasto.
3. **AWS Budgets** de 50 USD con alertas al 50 %, 80 % y 100 %, y una acción al 90 % que deniega la invocación de modelos al rol del agente. Budgets tiene retraso de horas, por eso **no sustituye** a las cuotas.
4. **Destruir tras cada sesión** con `terraform destroy`. AgentCore no cobra en reposo, pero el resto sí acumula.

## Lo que se evita a propósito

NAT Gateway, OpenSearch Serverless (costo mínimo mensual alto), throughput aprovisionado de Bedrock, claves KMS propias, VPC endpoints, memoria de largo plazo de AgentCore, Evaluations, Code Interpreter y Browser. El Lambda va fuera de VPC.

## Aprendizajes / dolores

- Los precios de Bedrock en la API de precios aparecen por modalidad (`priority`, `batch`, `flex`); el precio estándar hay que derivarlo. Guardrails, Titan y S3 Vectors no salieron: hay que confirmarlos en la consola de precios antes de la charla.
- El costo dominante por consulta es el modelo y no la infraestructura; por eso la cuota por usuario y el tope de tokens pesan más que optimizar el runtime.
