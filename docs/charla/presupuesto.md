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

## Corte automático al 90 % (NFR-014)

`infra/budget_action.tf`. Al llegar al 90 % del presupuesto (45 USD), AWS Budgets adjunta a los roles del agente, del orquestador y de las herramientas (Lambda `tools`) la política `spec-to-runtime-budget-cutoff`, que **niega** invocar modelos, guardrails, la Knowledge Base y el Runtime. El resto de permisos (DynamoDB, logs) se mantiene: así el sistema puede registrar el fallo y devolver la cuota. La acción es automática y avisa por correo.

**Es la red de seguridad de último recurso, no una protección en tiempo real.** Facturación tiene un retraso de 8 a 24 horas: el gasto de una mala tarde puede tardar en verse. La protección en tiempo real son las cuotas de la API (25 preguntas por participante y día, 3.000 en total, 10 consultas simultáneas).

### Cómo se comprobó

- **Simulador de IAM con los recursos reales:** modelo, guardrail, Knowledge Base e invocar el Runtime pasan de `allowed` a `explicitDeny`; DynamoDB sigue `allowed`. El rol que asume Budgets solo puede adjuntar **esa** política a **esos dos** roles (no a otros, ni `AdministratorAccess`, ni crear usuarios).
- **Corte simulado de verdad** (`scripts/test_budget_cutoff.py`, con una pregunta real por la API):

| Paso | Resultado |
|---|---|
| Antes del corte | `Completed` en 9,6 s, cuota usada 1 |
| Con el corte activo | `Failed` en **0,8 s**, `AccessDeniedException`, la cuota se devuelve (sigue en 1) |
| Segundo intento | igual: falla rápido y sin gastar |
| Tras retirar el corte | `Completed` en 5,8 s, cuota 2 |

La web ya no dice "inténtalo de nuevo" cuando el fallo es el corte: dice que **la demo está en pausa por el límite de gasto** y avisa al ponente (`web/errors.js`, con tests).

### Operación

```bash
# ¿Está armada o disparada la acción? (STANDBY = armada; EXECUTION_SUCCESS = ya cortó)
aws budgets describe-budget-actions-for-budget --account-id <cuenta> --budget-name spec-to-runtime-50usd \
  --query 'Actions[].[Status,ActionThreshold.ActionThresholdValue]'

# Levantar el corte tras revisar el gasto (una vez por rol)
for rol in spec-to-runtime-agent-runtime spec-to-runtime-orchestrator; do
  aws iam detach-role-policy --role-name $rol --policy-arn $(terraform -chdir=infra output -raw budget_cutoff_policy_arn)
done
```

Si la acción disparó, además de quitar la política hay que reiniciar la acción en la consola de Budgets (o `terraform apply -replace=aws_budgets_budget_action.cutoff`) para que vuelva a `STANDBY`.

### Aprendizajes / dolores

- **El presupuesto estaba ciego:** filtraba por la etiqueta de costo `project`, que aún no existe en Facturación (la lista de etiquetas seguía vacía), así que marcaba 0 USD y la acción **nunca se habría disparado**. Ahora el presupuesto cubre toda la cuenta (`budget_filter_by_tag = false`), lo que hoy es seguro porque la cuenta no tiene otros proyectos gastando (~0 USD este mes). Cuando la etiqueta exista se puede acotar.
- **Quitar el bloque `cost_filter` del código no lo quita en AWS:** el proveedor lo trata como opcional y calculado, y `terraform plan` no detectó ningún cambio. Hubo que reemplazar el presupuesto (`-replace`). Regla: tras editar un recurso hay que comprobar el resultado **en AWS**, no solo que el plan salga limpio.
- **`main` estaba por detrás de lo desplegado** cuando fui a construir esto: el #18 se mergeó antes de que subiera mis últimos commits y el plan de Terraform proponía revertir el Runtime y la web. Por eso salió el PR #19 aparte. Antes de aplicar hay que leer el plan.
- **La primera simulación de IAM engañaba:** con recurso `*` el "antes" salía `implicitDeny` porque los permisos del rol están limitados a recursos concretos. Hay que simular con los recursos reales.
- **En zsh `$ACC:role` interpreta `:r` como modificador** y rompe el ARN: escribir `${ACC}:role`, o usar Python.
