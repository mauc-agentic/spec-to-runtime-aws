# La web

Código en `web/`, infraestructura en `infra/web.tf`. Estado: **publicada y probada en un navegador real el 2026-09-24**. Los UCs siguen en `Draft`.

Es una página estática sin framework ni paso de compilación (HTML, CSS y JavaScript con módulos): habla directamente con Cognito (registro e inicio de sesión) y con la API. Se sirve por CloudFront desde un bucket privado, con HTTPS y sin costo fijo. `terraform apply` sube los archivos y genera `config.js` con la URL de la API y el cliente de Cognito, así que no hay que recompilar nada.

## Identidad visual

Tomada del cartel del primer meetup de AWS User Group Valle del Cauca: degradado de ciruela (arriba a la izquierda) a azul noche y cobalto (abajo a la derecha), títulos y acentos en lila, tipografía limpia sin serifas con mucho contraste de peso, y como pieza central el logo de la comunidad, con su hexágono, la caña de azúcar y las notas. La imagen del logo es la oficial de la comunidad, la aporta el autor y no se ha modificado. El resto es diseño propio.

El logo oficial se usa también en el encabezado del chat y como avatar del agente (y como icono de la pestaña): el primer despliegue solo lo tenía en el acceso y el resto seguía con mi dibujo, que se retiró por completo.

Decisiones de diseño: un solo elemento memorable (el logo); nada de tarjetas idénticas, etiquetas en mayúsculas ni numeraciones decorativas; los botones dicen lo que hacen ("Entrar", "Enviar", "Intentar de nuevo"); en el acceso el formulario va a la izquierda y el logo a la derecha, como en el cartel, y en celular el logo pasa arriba.

## Pantallas

- **Acceso:** Entrar o Crear cuenta. Crear cuenta pide el código del evento (UC-001); los errores dicen qué pasó y cómo seguir sin revelar si un correo existe.
- **Chat:** selector de perfil (Básico, Técnico, General; se recuerda en el dispositivo), sugerencias de preguntas, estados "En cola, Preparando, Buscando, Redactando" y el texto que va apareciendo, fuentes como enlaces, contador de 500 caracteres y "Intentar de nuevo" cuando algo falla.
- **Historial:** lista de conversaciones y reapertura de cualquiera para seguir preguntando (UC-006). Si una respuesta sigue en curso, se muestra lo escrito y se completa sola (UC-006 A3).
- **Herramientas del ponente:** solo se muestran si el token trae el grupo Ponente: top 10 de preguntas, sincronizar documentos y estado de la sincronización. El servidor vuelve a comprobar el rol en cada llamada; ocultar los botones es solo comodidad.

## Seguridad

- **XSS:** las respuestas las genera un modelo a partir de documentos, así que nunca se insertan como HTML. `web/markdown.js` escapa todo primero y solo después aplica unas pocas marcas propias; los enlaces solo pueden ser `http(s)`. Hay 8 tests con vectores de ataque (`<script>`, `javascript:`, `onerror`, bloques de código, etc.) que corren en el CI, y comprobé que fallan si se quita el escape.
- **CSP estricta** desde CloudFront: solo scripts y estilos propios, y conexiones únicamente a Cognito y a la API. Más HSTS, `X-Frame-Options: DENY`, `nosniff` y `Referrer-Policy: no-referrer`.
- **Bucket privado:** el acceso directo devuelve 403; solo CloudFront lo lee.
- **CORS de la API acotado** a la dirección de la web (antes era `*`); un origen ajeno queda bloqueado.
- El token de sesión vive en `sessionStorage` (se borra al cerrar la pestaña) y dura 12 horas.

## Verificación con un navegador real

Con Chrome: registro desde la interfaz con el código del evento, inicio de sesión, pregunta con perfil Básico (estado "Redactando" y respuesta en Markdown con títulos, listas, código y fuentes enlazadas), historial, y vista del Ponente (herramientas y estado de la sincronización). Sin errores en la consola. La cuenta de prueba, sus preguntas y sus contadores se borraron y el código del evento se rotó.

## Defectos que encontré al mirarla

- **Faltaba la caña de azúcar en mi primer dibujo:** los degradados estaban en un SVG con `hidden` y Chrome no resuelve degradados de un SVG con `display: none`. Se resolvió cambiándolo a un SVG de tamaño cero. Después se sustituyó el dibujo por el logo oficial de la comunidad.
- El título de mi primer hexágono se salía del hueco porque abajo el hexágono se estrecha, y un signo "+" se solapaba con el texto.
- Un primer test de XSS tenía una aserción mal escrita que no comprobaba nada; se reescribió para exigir que el único atributo posible sea el de un enlace https exacto.

- **Un error de la primera versión que solo la prueba real del autor destapó:** el logo oficial estaba en el acceso, pero el encabezado y el avatar seguían con el dibujo. Al reemplazar un elemento hay que buscar todos sus usos (`grep`), no solo el que se ve primero.

## Aprendizajes / dolores

- El primer clic sobre un campo o botón en la automatización del navegador a veces solo enfoca el elemento: si no pasa nada, hay que repetirlo.
- Un borde superior sin transición corta el texto en seco bajo el selector de perfil; se difumina con `mask-image`.
- Node necesita `"type": "module"` en `web/package.json` para importar el `.js` como módulo en los tests.
- La CSP sin `unsafe-inline` prohíbe `style="..."` y `<script>` en línea, pero permite cambiar `element.style` desde JavaScript, que es lo único que usa el autoajuste del cuadro de texto.
- Sin caché en CloudFront (política `Managed-CachingDisabled`): el sitio pesa unos KB y así los cambios se ven al instante, sin invalidaciones.
- Las herramientas de automatización del navegador no listan los elementos fuera de la pantalla: para pulsar el botón "Entrar" hubo que localizarlo con una búsqueda.

## Pendiente

- Probar en un celular físico y con lector de pantalla (solo se probó con Chrome en ancho de celular).
- Una respuesta con citas numeradas del modelo (`[1]`) no las enlaza; las fuentes reales van en la lista al final.
- Sin mostrar la fecha del evento dinámicamente ni el nombre del ponente.
