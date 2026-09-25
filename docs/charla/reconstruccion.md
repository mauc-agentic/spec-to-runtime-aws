# Reconstruir el entorno desde cero

Procedimiento para crear (o volver a crear) toda la infraestructura desde un clon limpio del repositorio, y para destruirla al terminar. Cubre FR-004 (reproducción de la demo) y NFR-004 (reproducible en 30 minutos o menos).

**Estado de la verificación:** desde un clon limpio, con solo los archivos `.example`, `terraform init` y `plan` se verificaron (2026-09-24, «No changes» sobre el entorno existente). La reconstrucción completa (destruir, crear y medir el tiempo) **aún no se ha probado**; ver el final.

## Requisitos

- Python 3.14 y [`uv`](https://docs.astral.sh/uv/).
- Terraform 1.10 o superior.
- Docker en ejecución (la imagen del agente es `linux/arm64`).
- AWS CLI con credenciales de una cuenta en `us-east-1`.
- Node.js, solo para los tests de la web.

## 1. Una sola vez por cuenta: el bucket del estado

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply
```

Crea el bucket `spec-to-runtime-tfstate-<account-id>` (con versionado, cifrado y sin acceso público). Tiene `prevent_destroy`: `terraform destroy` del entorno no lo toca. Si el bucket ya existe en la cuenta, se omite este paso.

## 2. Dos archivos locales (no van a git)

```bash
cp infra/backend.hcl.example infra/backend.hcl              # sustituye <account-id> por el de tu cuenta
cp infra/terraform.tfvars.example infra/terraform.tfvars    # pon el correo de las alertas de presupuesto
terraform -chdir=infra init -backend-config=backend.hcl
```

## 3. Despliegue en tres fases

El agente corre en un contenedor y el Runtime no se puede crear hasta que la imagen existe en ECR. Por eso no basta un solo `apply`:

```bash
# Fase 1: solo el repositorio de imágenes (ECR)
terraform -chdir=infra apply -var agent_image_tag="" -target=aws_ecr_repository.agent

# Fase 2: construye y sube la imagen (usa el hash del commit como etiqueta; exige el árbol limpio)
scripts/deploy_agent.sh

# Fase 3: todo lo demás, incluido el Runtime con esa imagen
terraform -chdir=infra apply
```

Sin la fase 1, un `apply` completo con la etiqueta vacía falla porque la política del orquestador (`infra/api.tf`) necesita el ARN del Runtime, que aún no existe (comprobado); y con una etiqueta real, el Runtime no puede crearse mientras la imagen no esté en ECR (esperado, no probado). Tras la fase 2, `infra/agent_image.auto.tfvars` queda modificado con la etiqueta nueva; en un entorno propio conviene hacer commit.

## 4. Después de desplegar

1. **Sincronizar la Knowledge Base** con el repositorio (se ejecuta sobre `main` en GitHub, no sobre lo local):
   ```bash
   aws lambda invoke --function-name spec-to-runtime-sync --payload '{}' \
     --cli-binary-format raw-in-base64-out --cli-read-timeout 300 out.json
   aws lambda invoke --function-name spec-to-runtime-sync --payload '{"action":"status"}' \
     --cli-binary-format raw-in-base64-out out.json && cat out.json   # esperar COMPLETE con 0 fallidos
   ```
2. **Crear la cuenta del Ponente.** No existe ningún registro que otorgue ese rol. Sin correo de invitación y sin dejar la contraseña en el historial del shell:
   ```bash
   POOL=$(terraform -chdir=infra output -raw user_pool_id)
   EMAIL="ponente@ejemplo.com"; read -rs PW    # escribe la contraseña y pulsa Enter
   aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$EMAIL" --message-action SUPPRESS \
     --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true
   aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$EMAIL" --password "$PW" --permanent
   aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username "$EMAIL" --group-name Ponente
   ```
3. **Registro de participantes:** nace cerrado. El código del evento es **nuevo en cada entorno** (se genera al crearlo). Para abrirlo, conservando el código:
   ```bash
   CODE=$(aws secretsmanager get-secret-value --secret-id spec-to-runtime/event --query SecretString --output text \
     | python3 -c "import json,sys; print(json.load(sys.stdin)['event_code'])")
   aws secretsmanager put-secret-value --secret-id spec-to-runtime/event \
     --secret-string "{\"event_code\":\"$CODE\",\"registration_open\":true}"
   ```
   Para cerrarlo, la misma orden con `false`.
4. **Comprobar y calentar:**
   ```bash
   terraform -chdir=infra output web_url                   # la dirección pública cambia en cada entorno
   PYTHONPATH=src uv run python scripts/warmup.py          # calienta y no toca el registro
   PYTHONPATH=src uv run python scripts/smoke_test.py      # 15 comprobaciones (cierra el registro al terminar)
   ```

## 5. Destruir y comprobar que no queda nada

```bash
terraform -chdir=infra destroy
```

Destruye unos 100 recursos: los buckets, el repositorio de imágenes y el secreto se borran sin ventana de espera. Después:

- **Barrido por etiqueta:** debe devolver 0.
  ```bash
  aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=spec-to-runtime-aws \
    --query 'length(ResourceTagMappingList)'
  ```
- **Logs que crea AgentCore y Terraform no gestiona:** AgentCore Runtime crea un grupo de logs `/aws/bedrock-agentcore/runtimes/...` sin caducidad que `destroy` deja atrás. Bórralo a mano:
  ```bash
  aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore/runtimes/spec_to_runtime \
    --query 'logGroups[].logGroupName' --output text
  aws logs delete-log-group --log-group-name <nombre>
  ```
- **Bucket del estado:** sigue existiendo (paso 1). Guarda el estado, que incluye valores sensibles como el código del evento. Solo se borra si no se va a reconstruir: hay que quitar `prevent_destroy` de `infra/bootstrap`, vaciar todas las versiones del bucket y ejecutar `destroy` en esa carpeta.

## Lo que cambia al reconstruir

- La dirección de la web y del API, los identificadores de Cognito, de la Knowledge Base y del Runtime son nuevos.
- El código del evento es nuevo, y la cuenta del Ponente, las preguntas, las cuotas y la memoria del agente **no se conservan**.
- La Knowledge Base se vuelve a llenar desde GitHub con la sincronización.

## Pendiente de medir en la prueba de reconstrucción

La prueba real (destruir, reconstruir desde un clon limpio siguiendo solo este documento, medir el tiempo y volver a destruir) se hace después de la charla. Debe:

- Medir el tiempo total contra los 30 minutos de NFR-004, y cuánto tarda cada fase.
- Anotar cualquier paso manual que este documento no recoja.
- Decidir si se elimina la fase 1 (`-target`) haciendo que la política del orquestador no dependa del ARN del Runtime, y si el grupo de logs del Runtime pasa a Terraform para que `destroy` no lo deje atrás.
