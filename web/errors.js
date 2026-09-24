// Qué decirle al participante cuando una respuesta falla, según el motivo que guardó el servidor.

export const PAUSED_MESSAGE =
  "La demo está en pausa: se alcanzó el límite de gasto de la charla. Avisa al ponente.";
const TIMEOUT_MESSAGE = "La respuesta tardó demasiado. Inténtalo de nuevo.";
const GENERIC_MESSAGE =
  "No se pudo completar la respuesta. Esta pregunta no se descontó de tu límite: inténtalo de nuevo.";

/** @returns {{ text: string, retry: boolean }} `retry` indica si tiene sentido ofrecer "Intentar de nuevo". */
export function describeFailure(data) {
  switch (data?.error_code) {
    // El corte automático de presupuesto (NFR-014) niega la invocación de modelos: reintentar no sirve.
    case "AccessDeniedException":
      return { text: PAUSED_MESSAGE, retry: false };
    case "timeout":
      return { text: TIMEOUT_MESSAGE, retry: true };
    default:
      return { text: GENERIC_MESSAGE, retry: true };
  }
}

// Avisos que el servidor adjunta a una consulta que sí se respondió (UC-004 A4 y UC-005 A4).
export const NOTICES = {
  personal_data_masked: "Oculté datos personales de tu pregunta antes de enviarla.",
  memory_unavailable: "No pude recordar lo anterior: respondo solo con tu pregunta actual.",
};

/** @returns {string[]} los textos de los avisos conocidos, sin repetir; ignora los que no conoce. */
export function noticeTexts(codes) {
  return [...new Set(codes ?? [])].map((code) => NOTICES[code]).filter(Boolean);
}
