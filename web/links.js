// Enlace a la sesión de una conversación en la consola de CloudWatch (solo lo ve el Ponente).
// El id de sesión es el mismo que el agente etiqueta como `session.id` en sus trazas, así que la
// página de la sesión reúne todas las preguntas de esa conversación y sus trazas.

/** @param {string} region @param {string} sessionId formato del servidor: sess- y 32 hex */
export function sessionUrl(region, sessionId) {
  if (!/^sess-[0-9a-f]{32}$/.test(sessionId)) return null; // nunca se arma un enlace con datos raros
  return `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}#gen-ai-observability/agent-core/session/${sessionId}`;
}
