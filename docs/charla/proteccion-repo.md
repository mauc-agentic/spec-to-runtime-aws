# Protección del repo (repo público)

El repo es público y solo el dueño (`@mauc-agentic`) puede mergear a `main`. Todo cambio entra por PR.

## Ruleset `protect-main` (GitHub)

- Sin push directo a `main`, sin borrado ni force-push, historial lineal.
- Todo por PR, solo **squash merge**, 1 aprobación, aprobaciones descartadas si hay commits nuevos, conversaciones resueltas y revisión de code owner (`.github/CODEOWNERS`).
- **Commits firmados** obligatorios (`required_signatures`). Los squash merges desde la web los firma GitHub (`web-flow`), por eso un PR con commits viejos sin firmar sí puede mergearse.
- **Bypass del dueño solo vía PR** (rol admin, modo `pull_request`): el dueño puede mergear sus propios PRs sin segunda aprobación, pero nunca hacer push directo. Sin este bypass, un repo con un solo admin no podría mergear nada.
- Los checks de CI (`python`, `terraform`) se exigen en el ruleset una vez que hayan corrido en un PR.

## Ajustes del repo y seguridad

- Ramas borradas al mergear; wiki y projects desactivados; merge commit y rebase desactivados.
- Secret scanning con push protection, patrones extra y validity checks; alertas y actualizaciones de seguridad de Dependabot; reporte privado de vulnerabilidades (`SECURITY.md`).
- Actions: token por defecto de solo lectura, no puede aprobar PRs, y los PRs de forks de contribuyentes externos requieren aprobación para correr.
- Dependabot (`.github/dependabot.yml`) para `uv`, Terraform y GitHub Actions; las actions van fijadas por SHA.

## Firma de commits con SSH

La misma llave ed25519 firma y autentica. Se sube dos veces a GitHub: como llave de autenticación y como *signing key* (`gh ssh-key add <pub> --type signing`). Git: `gpg.format ssh`, `user.signingkey`, `commit.gpgsign true`. El correo del commit debe estar verificado en la cuenta para que salga *Verified*.

## Aprendizajes / dolores

- Un PR apilado sobre otra rama se fusiona en esa rama, no en `main`, si el PR base ya se mergeó: hubo que abrir un PR extra (#3) para llevarlo a `main`. Cambiar la base del PR apilado a `main` antes de mergear el primero.
- `checkov` lee `#checkov:skip` solo **dentro** del bloque del recurso.
- `pytest` sale con código 5 cuando no hay tests; el CI lo tolera hasta el primer UC implementado.
- Un token con todos los permisos sirve para configurar rulesets y ajustes, pero conviene revocarlo al terminar.
