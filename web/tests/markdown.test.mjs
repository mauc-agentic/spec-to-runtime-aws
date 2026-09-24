import assert from "node:assert/strict";
import { test } from "node:test";
import { escapeHtml, renderMarkdown } from "../markdown.js";

// Etiquetas que el renderizador puede producir; cualquier otra sería una fuga.
const ALLOWED = /^(p|br|strong|em|code|pre|a|ul|ol|li|h[3-6]|hr|blockquote)$/;

// La única etiqueta con atributos es el enlace, y solo con este formato exacto.
const SAFE_ANCHOR = /^<a href="https?:\/\/[^"\s<>]*" target="_blank" rel="noopener noreferrer">$/;

function assertOnlyAllowedTags(html) {
  for (const [, name] of html.matchAll(/<\/?([a-zA-Z][\w-]*)/g)) {
    assert.match(name, ALLOWED, `etiqueta no permitida <${name}> en: ${html}`);
  }
  for (const [tag] of html.matchAll(/<a\b[^>]*>/g)) {
    assert.match(tag, SAFE_ANCHOR, `enlace no seguro ${tag} en: ${html}`);
  }
  // Ninguna otra etiqueta puede llevar atributos: sin atributos no hay manejadores de eventos.
  for (const [tag] of html.matchAll(/<(?!a\b)[a-zA-Z][^>]*>/g)) {
    assert.match(tag, /^<[a-z0-9]+>$/, `etiqueta con atributos ${tag} en: ${html}`);
  }
}

test("escapa el HTML antes de todo", () => {
  assert.equal(escapeHtml(`<b>"a"&'b'</b>`), "&lt;b&gt;&quot;a&quot;&amp;&#39;b&#39;&lt;/b&gt;");
});

test("los vectores de XSS no producen etiquetas ni atributos activos", () => {
  const attacks = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "[clic](javascript:alert(1))",
    "[clic](JaVaScRiPt:alert(1))",
    "[clic](data:text/html,<script>alert(1)</script>)",
    '**<svg onload="alert(1)">**',
    '"><script>alert(1)</script>',
    "![img](https://x/y.png)<iframe src=//evil>",
    "`<script>alert(1)</script>`",
    "```\n<script>alert(1)</script>\n```",
    "> <img src=x onerror=alert(1)>",
    "- <a href=javascript:alert(1)>x</a>",
    '[a](https://ok.com" onmouseover="alert(1))',
  ];
  for (const attack of attacks) {
    const html = renderMarkdown(attack);
    assertOnlyAllowedTags(html);
    assert.doesNotMatch(html, /<script|<iframe|<svg|<img/i, attack);
    assert.doesNotMatch(html, /href="javascript:/i, attack);
  }
});

test("un enlace https válido se abre en otra pestaña sin dar acceso a la ventana", () => {
  const html = renderMarkdown("[visión](https://github.com/o/r/blob/main/docs/vision.md)");
  assert.equal(
    html,
    '<p><a href="https://github.com/o/r/blob/main/docs/vision.md" target="_blank" rel="noopener noreferrer">visión</a></p>',
  );
});

test("los enlaces que no son http(s) quedan como texto", () => {
  const html = renderMarkdown("[a](javascript:alert(1)) y [b](ftp://x)");
  assert.doesNotMatch(html, /<a /);
});

test("títulos, listas, negrita, cursiva, código y citas", () => {
  assert.equal(renderMarkdown("## Título"), "<h4>Título</h4>");
  assert.equal(renderMarkdown("- uno\n- dos"), "<ul><li>uno</li><li>dos</li></ul>");
  assert.equal(renderMarkdown("1. uno\n2. dos"), "<ol><li>uno</li><li>dos</li></ol>");
  assert.equal(renderMarkdown("**fuerte** y *suave* y `x`"), "<p><strong>fuerte</strong> y <em>suave</em> y <code>x</code></p>");
  assert.equal(renderMarkdown("> cita"), "<blockquote>cita</blockquote>");
  assert.equal(renderMarkdown("---"), "<hr>");
});

test("un bloque de código conserva el texto pero nunca se interpreta", () => {
  const html = renderMarkdown("```\n**no negrita** <b>x</b>\n```");
  assert.equal(html, "<pre><code>**no negrita** &lt;b&gt;x&lt;/b&gt;</code></pre>");
});

test("las fuentes que agrega el orquestador se ven como lista de enlaces", () => {
  const html = renderMarkdown("---\n**Fuentes**\n- [docs/vision.md](https://x/docs/vision.md)");
  assert.match(html, /<hr><p><strong>Fuentes<\/strong><\/p><ul><li><a href="https:\/\/x\/docs\/vision.md"/);
});

test("texto vacío o nulo no rompe", () => {
  assert.equal(renderMarkdown(""), "");
  assert.equal(renderMarkdown(null), "");
});
