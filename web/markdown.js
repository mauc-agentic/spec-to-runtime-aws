// Renderizador de Markdown mínimo y seguro para las respuestas del agente.
// El texto lo genera un modelo a partir de documentos, así que NUNCA se inserta como HTML:
// primero se escapa todo y solo después se aplican unas pocas marcas propias.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

// Solo enlaces http(s): javascript:, data: y similares nunca coinciden con este patrón.
const LINK = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g;

function inline(escaped) {
  return escaped
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>")
    .replace(LINK, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

export function renderMarkdown(source) {
  const lines = escapeHtml(source ?? "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let paragraph = [];
  let list = null; // { tag: "ul" | "ol", items: [] }
  let fence = null; // líneas del bloque de código

  const flushParagraph = () => {
    if (paragraph.length) html.push(`<p>${inline(paragraph.join("<br>"))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (list) html.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`);
    list = null;
  };

  for (const line of lines) {
    if (fence) {
      if (line.trim().startsWith("```")) {
        html.push(`<pre><code>${fence.join("\n")}</code></pre>`);
        fence = null;
      } else fence.push(line);
      continue;
    }
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      fence = [];
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    const quote = line.match(/^&gt;\s?(.*)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = Math.min(heading[1].length + 2, 6); // los # del modelo nunca compiten con el título
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      flushParagraph();
      flushList();
      html.push("<hr>");
    } else if (bullet || ordered) {
      flushParagraph();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tag !== tag) {
        flushList();
        list = { tag, items: [] };
      }
      list.items.push((bullet || ordered)[1]);
    } else if (quote) {
      flushParagraph();
      flushList();
      html.push(`<blockquote>${inline(quote[1])}</blockquote>`);
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  if (fence) html.push(`<pre><code>${fence.join("\n")}</code></pre>`);
  flushParagraph();
  flushList();
  return html.join("");
}
