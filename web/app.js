import { ApiError, createApi } from "./api.js";
import * as cognito from "./cognito.js";
import { renderMarkdown } from "./markdown.js";

const $ = (selector, root = document) => root.querySelector(selector);
const TIMEZONE = "America/Bogota";
const POLL_MS = 800;
const POLL_TIMEOUT_MS = 100_000;
const FINAL = new Set(["Completed", "Blocked", "Failed", "Rejected"]);
const PHASES = {
  Queued: "En cola",
  Processing: "Preparando la respuesta",
  Searching: "Buscando en el repositorio",
  Writing: "Redactando",
};
const SUGGESTIONS = [
  "¿Qué es AIUP?",
  "¿Cuánto cuesta la demo?",
  "¿Cómo protege el agente sus respuestas?",
  "¿Qué diferencia hay entre los perfiles?",
];
const TOP_PROMPT = "¿Cuáles fueron las preguntas más frecuentes? Dame el top 10";

// El almacenamiento del navegador puede no estar disponible (modo privado): la app funciona igual.
const safe = (storage) => ({
  get: (key) => { try { return storage.getItem(key); } catch { return null; } },
  set: (key, value) => { try { storage.setItem(key, value); } catch { /* sin almacenamiento */ } },
  del: (key) => { try { storage.removeItem(key); } catch { /* sin almacenamiento */ } },
});
const session = safe(window.sessionStorage);
const prefs = safe(window.localStorage);

const state = { token: null, isSpeaker: false, sessionId: null, busy: false, mode: "login" };
const api = createApi(() => state.token, () => logout("Tu sesión terminó. Entra de nuevo."));
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, 6000);
}

/* Acceso ---------------------------------------------------------------- */

function setMode(mode) {
  state.mode = mode;
  const signup = mode === "signup";
  $("#tab-login").setAttribute("aria-selected", String(!signup));
  $("#tab-signup").setAttribute("aria-selected", String(signup));
  $("#code-field").hidden = !signup;
  $("#password-hint").hidden = !signup;
  $("#password").autocomplete = signup ? "new-password" : "current-password";
  $("#auth-submit").textContent = signup ? "Crear cuenta" : "Entrar";
  $("#auth-error").hidden = true;
}

function authError(message) {
  const node = $("#auth-error");
  node.textContent = message;
  node.hidden = false;
}

async function submitAuth(event) {
  event.preventDefault();
  const email = $("#email").value.trim();
  const password = $("#password").value;
  const eventCode = $("#event-code").value.trim();
  const signup = state.mode === "signup";
  if (!email || !password) return authError("Escribe tu correo y tu contraseña.");
  if (signup && !/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(password)) {
    return authError("La contraseña necesita al menos 8 caracteres, con letras y números.");
  }
  if (signup && !eventCode) return authError("Escribe el código del evento que comparte el ponente.");

  const button = $("#auth-submit");
  button.disabled = true;
  $("#auth-error").hidden = true;
  try {
    if (signup) await cognito.signUp(email, password, eventCode);
    enterChat(await cognito.signIn(email, password));
  } catch (error) {
    authError(error.message);
  } finally {
    button.disabled = false;
  }
}

function enterChat(token) {
  state.token = token;
  state.isSpeaker = cognito.groupsOf(token).includes("Ponente");
  session.set("token", token);
  $("#password").value = "";
  $("#view-auth").hidden = true;
  $("#view-chat").hidden = false;
  $("#speaker").hidden = !state.isSpeaker;
  const saved = prefs.get("profile");
  const radio = saved && $(`input[name="profile"][value="${saved}"]`);
  if (radio) radio.checked = true;
  resetConversation();
  $("#prompt").focus();
}

function logout(message) {
  state.token = null;
  state.sessionId = null;
  session.del("token");
  $("#history").hidden = true;
  $("#view-chat").hidden = true;
  $("#view-auth").hidden = false;
  if (message) toast(message);
}

/* Conversación ---------------------------------------------------------- */

const currentProfile = () => $('input[name="profile"]:checked').value;

function scrollToEnd(force = false) {
  const box = $("#scroller");
  if (force || box.scrollHeight - box.scrollTop - box.clientHeight < 140) box.scrollTop = box.scrollHeight;
}

function setBusy(busy) {
  state.busy = busy;
  $("#send").disabled = busy;
}

function resetConversation() {
  state.sessionId = null;
  $("#log").replaceChildren();
  $("#empty").hidden = false;
}

function addUser(text) {
  $("#empty").hidden = true;
  const item = document.createElement("li");
  item.className = "msg user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text; // texto del usuario: nunca como HTML
  item.append(bubble);
  $("#log").append(item);
  scrollToEnd(true);
}

function addAgent() {
  $("#empty").hidden = true;
  const item = document.createElement("li");
  item.className = "msg agent";
  const avatar = document.createElement("img");
  avatar.className = "avatar";
  avatar.src = "aws-ug-valle-del-cauca.png";
  avatar.alt = "";
  avatar.width = 26;
  avatar.height = 30;
  item.append(avatar);
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const status = document.createElement("div");
  status.className = "status";
  status.innerHTML = '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="label"></span>';
  const body = document.createElement("div");
  body.className = "md";
  bubble.append(status, body);
  item.append(bubble);
  $("#log").append(item);
  scrollToEnd(true);
  return { bubble, status, label: $(".label", status), body, text: "" };
}

function setPhase(message, phase) {
  message.status.hidden = false;
  message.label.textContent = PHASES[phase] ?? phase;
}

function setText(message, text) {
  if (text === message.text) return;
  message.text = text;
  message.body.innerHTML = renderMarkdown(text); // renderMarkdown escapa todo el HTML
  scrollToEnd();
}

function paint(message, data) {
  if (data.text) setText(message, data.text);
  if (FINAL.has(data.status)) {
    message.status.hidden = true;
    if (data.status === "Blocked") message.bubble.classList.add("notice");
  } else {
    setPhase(message, data.phase);
  }
}

function fail(message, text, retry) {
  message.status.hidden = true;
  message.bubble.classList.add("failed");
  setText(message, text);
  if (retry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost retry";
    button.textContent = "Intentar de nuevo";
    button.addEventListener("click", () => {
      button.remove();
      message.bubble.classList.remove("failed");
      retry();
    });
    message.bubble.append(button);
  }
}

function resetTime(iso) {
  const when = new Intl.DateTimeFormat("es-CO", {
    weekday: "long", hour: "numeric", minute: "2-digit", hour12: true, timeZone: TIMEZONE,
  }).format(new Date(iso));
  return when;
}

function explain(error) {
  if (error.status === 429 && error.code === "project_limit") {
    return "Se alcanzó el límite de preguntas de esta charla. Gracias por participar.";
  }
  if (error.status === 429) {
    return `Alcanzaste tu límite de preguntas de hoy. Podrás volver a preguntar el ${resetTime(error.body.resets_at)}.`;
  }
  if (error.code === "session_not_found") {
    state.sessionId = null;
    return "Esa conversación ya no existe. Envía la pregunta otra vez para empezar una nueva.";
  }
  if (error.status === 400) return error.message;
  if (error.code === "timeout") return "La respuesta está tardando demasiado. Inténtalo de nuevo.";
  return "No se pudo enviar la pregunta. Revisa tu conexión e inténtalo de nuevo.";
}

async function follow(message, requestId) {
  const started = Date.now();
  let failures = 0;
  while (Date.now() - started < POLL_TIMEOUT_MS) {
    await sleep(POLL_MS);
    let data;
    try {
      data = await api.request(requestId);
      failures = 0;
    } catch (error) {
      if (error.status === 401) return null;
      if (++failures >= 4) throw error;
      continue;
    }
    paint(message, data);
    if (FINAL.has(data.status)) return data;
  }
  throw new ApiError(0, { code: "timeout" });
}

async function ask(prompt, existing) {
  if (state.busy) return;
  setBusy(true);
  let message = existing;
  if (!message) {
    addUser(prompt);
    message = addAgent();
  }
  setPhase(message, "Queued");
  try {
    const sent = await api.ask(prompt, currentProfile(), state.sessionId);
    state.sessionId = sent.session_id;
    if (sent.context_expired) toast("Pasaron más de 24 horas desde tu última pregunta: empecé una conversación nueva.");
    const data = await follow(message, sent.request_id);
    if (data?.status === "Failed") {
      fail(message, "No se pudo completar la respuesta. Esta pregunta no se descontó de tu límite: inténtalo de nuevo.", () => ask(prompt, message));
    }
  } catch (error) {
    fail(message, explain(error), error.status === 429 ? null : () => ask(prompt, message));
  } finally {
    setBusy(false);
    $("#prompt").focus();
  }
}

/* Historial ------------------------------------------------------------- */

let historyOpener = null;

async function openHistory() {
  historyOpener = document.activeElement;
  $("#history").hidden = false;
  $("#history-close").focus();
  const list = $("#history-list");
  list.textContent = "Cargando…";
  try {
    const { sessions } = await api.sessions();
    list.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "history-empty";
      empty.textContent = "Todavía no tienes conversaciones. Haz tu primera pregunta.";
      list.append(empty);
      return;
    }
    const day = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: TIMEZONE });
    for (const item of sessions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session";
      const title = document.createElement("span");
      title.className = "s-title";
      title.textContent = item.first_question;
      const meta = document.createElement("span");
      meta.className = "s-meta";
      meta.textContent = `${item.questions} ${item.questions === 1 ? "pregunta" : "preguntas"}, ${day.format(new Date(item.last_activity_at))}`;
      button.append(title, meta);
      button.addEventListener("click", () => loadSession(item.session_id));
      list.append(button);
    }
  } catch {
    list.textContent = "No se pudo cargar el historial. Inténtalo de nuevo.";
  }
}

function closeHistory() {
  $("#history").hidden = true;
  historyOpener?.focus();
}

async function loadSession(sessionId) {
  closeHistory();
  try {
    const { items } = await api.session(sessionId);
    $("#log").replaceChildren();
    state.sessionId = sessionId;
    for (const item of items) {
      addUser(item.prompt);
      const message = addAgent();
      paint(message, item);
      if (!FINAL.has(item.status)) {
        // UC-006 A3: la respuesta sigue en curso; se muestra lo escrito hasta ahora y se completa sola.
        follow(message, item.request_id).catch(() => fail(message, "No se pudo completar esta respuesta.", null));
      } else if (item.status === "Failed") {
        fail(message, "Esta respuesta no se pudo completar.", null);
      }
    }
    scrollToEnd(true);
  } catch {
    toast("No se pudo abrir la conversación. Inténtalo de nuevo.");
  }
}

/* Herramientas del ponente ---------------------------------------------- */

const SYNC_STATUS = {
  COMPLETE: "Terminada", IN_PROGRESS: "En curso", STARTING: "Iniciando", FAILED: "Falló", NeverRun: "Nunca se ha ejecutado",
};

function formatSync(result) {
  switch (result.result) {
    case "Started": {
      const lines = [
        "**Sincronización iniciada**",
        `- ${result.new} documentos nuevos`,
        `- ${result.changed} modificados`,
        `- ${result.removed} eliminados`,
        `- ${result.skipped.length} archivos omitidos`,
      ];
      if (result.failed?.length) lines.push(`- **${result.failed.length} no se pudieron cargar:** ${result.failed.map((f) => f.path).join(", ")}`);
      lines.push("", "La ingesta tarda unos 2 minutos. Toca «Estado de la sincronización» para ver el avance.");
      return lines.join("\n");
    }
    case "NoChanges": return "Los documentos ya estaban al día. No hubo nada que sincronizar.";
    case "AlreadyRunning": return `Ya hay una sincronización en curso (${SYNC_STATUS[result.status] ?? result.status}). Espera a que termine.`;
    case "Failed": return "No se pudo leer el repositorio. El conocimiento del agente no cambió.";
    default: {
      const status = SYNC_STATUS[result.status] ?? result.status;
      if (result.status === "NeverRun") return `**Sincronización:** ${status}.`;
      return `**Última sincronización:** ${status}\n- ${result.documents_scanned} documentos revisados\n- ${result.documents_failed} con error`;
    }
  }
}

async function speakerAction(label, call) {
  if (state.busy) return;
  setBusy(true);
  addUser(label);
  const message = addAgent();
  setPhase(message, "Preparando la respuesta");
  try {
    const result = await call();
    message.status.hidden = true;
    setText(message, formatSync(result));
  } catch (error) {
    fail(message, error.status === 403 ? "Solo el ponente puede hacer esto." : "No se pudo completar. Inténtalo de nuevo.", null);
  } finally {
    setBusy(false);
  }
}

/* Arranque -------------------------------------------------------------- */

function autosize() {
  const box = $("#prompt");
  box.style.height = "auto";
  box.style.height = `${Math.min(box.scrollHeight, 144)}px`;
  const count = $("#count");
  count.textContent = `${box.value.length} de 500`;
  count.classList.toggle("near", box.value.length >= 450);
}

function send() {
  const box = $("#prompt");
  const text = box.value.trim();
  if (!text || state.busy) return;
  box.value = "";
  autosize();
  ask(text);
}

function init() {
  $("#tab-login").addEventListener("click", () => setMode("login"));
  $("#tab-signup").addEventListener("click", () => setMode("signup"));
  $("#auth-form").addEventListener("submit", submitAuth);
  $("#composer").addEventListener("submit", (event) => { event.preventDefault(); send(); });
  $("#prompt").addEventListener("input", autosize);
  $("#prompt").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); }
  });
  for (const radio of document.querySelectorAll('input[name="profile"]')) {
    radio.addEventListener("change", () => prefs.set("profile", currentProfile()));
  }
  $("#btn-history").addEventListener("click", openHistory);
  $("#history-close").addEventListener("click", closeHistory);
  $("#btn-new").addEventListener("click", resetConversation);
  $("#btn-logout").addEventListener("click", () => logout());
  $("#btn-top").addEventListener("click", () => { $("#prompt").value = TOP_PROMPT; send(); });
  $("#btn-sync").addEventListener("click", () => speakerAction("Sincronizar documentos", api.sync));
  $("#btn-sync-status").addEventListener("click", () => speakerAction("Estado de la sincronización", api.syncStatus));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#history").hidden) closeHistory();
  });

  const suggestions = $("#suggestions");
  for (const text of SUGGESTIONS) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = text;
    chip.addEventListener("click", () => { $("#prompt").value = text; send(); });
    suggestions.append(chip);
  }

  const saved = session.get("token");
  if (saved && !cognito.isExpired(saved)) enterChat(saved);
}

init();
