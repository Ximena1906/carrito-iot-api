"""Swagger UI personalizado (tema rosa) con encabezado propio e indicadores en vivo.

Sustituye la página /docs por defecto de FastAPI. El contenido OpenAPI no cambia:
solo el diseño. Los indicadores consultan /health y /health/db cada 30 s.
"""
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

SWAGGER_JS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
SWAGGER_CSS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='16' fill='%23d63384'/%3E"
    "%3Crect x='12' y='24' width='40' height='16' rx='6' fill='white'/%3E"
    "%3Cpath d='M20 24l6-8h12l6 8' fill='none' stroke='white' stroke-width='4' stroke-linejoin='round'/%3E"
    "%3Ccircle cx='22' cy='44' r='6' fill='%23ffd1e3' stroke='white' stroke-width='3'/%3E"
    "%3Ccircle cx='42' cy='44' r='6' fill='%23ffd1e3' stroke='white' stroke-width='3'/%3E"
    "%3C/svg%3E"
)

ESTILOS = """
<style>
  :root{
    --rosa:#d63384; --rosa-osc:#a61e63; --rosa-suave:#fde7f0; --rosa-borde:#f6bcd6;
    --lila:#7c3aed; --lila-suave:#f3edff; --texto:#3b1a2c; --gris:#6b5763;
  }
  body{margin:0;background:#fff7fb;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--texto)}
  .swagger-ui .topbar{display:none}
  .swagger-ui .information-container .info .title,
  .swagger-ui .information-container .info .link{display:none}

  /* ---------- Encabezado ---------- */
  .hero{background:linear-gradient(135deg,#d63384 0%,#e85d9c 55%,#f48fb8 100%);color:#fff;
        padding:28px 20px 70px}
  .hero-in{max-width:1460px;margin:0 auto;display:flex;flex-wrap:wrap;gap:20px;align-items:center;
           justify-content:space-between}
  .marca{display:flex;gap:16px;align-items:center}
  .logo{width:60px;height:60px;border-radius:18px;background:rgba(255,255,255,.18);display:grid;
        place-items:center;box-shadow:inset 0 0 0 2px rgba(255,255,255,.35)}
  .hero h1{margin:0;font-size:30px;line-height:1.1;font-weight:800;letter-spacing:-.5px}
  .hero p{margin:6px 0 0;opacity:.92;font-size:15px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
  .chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:999px;
        padding:4px 12px;font-size:12px;font-weight:600}
  .estado{display:flex;gap:10px;flex-wrap:wrap}
  .pill{background:#fff;color:var(--texto);border-radius:14px;padding:10px 14px;min-width:150px;
        box-shadow:0 6px 18px rgba(120,20,70,.18)}
  .pill small{display:block;font-size:11px;color:var(--gris);text-transform:uppercase;letter-spacing:.6px}
  .pill b{display:flex;align-items:center;gap:7px;font-size:14px;margin-top:3px}
  .dot{width:10px;height:10px;border-radius:50%;background:#c9b6c0}
  .ok .dot{background:#16a34a;box-shadow:0 0 0 4px #dcfce7}
  .mal .dot{background:#dc2626;box-shadow:0 0 0 4px #fee2e2}
  .esp .dot{background:#f59e0b;box-shadow:0 0 0 4px #fef3c7}

  /* ---------- Tarjetas de guía ---------- */
  .guia{max-width:1460px;margin:-48px auto 0;padding:0 20px;display:grid;gap:14px;
        grid-template-columns:repeat(auto-fit,minmax(230px,1fr));position:relative}
  .card{background:#fff;border:1px solid var(--rosa-borde);border-radius:16px;padding:16px 18px;
        box-shadow:0 8px 24px rgba(214,51,132,.10)}
  .card h3{margin:0 0 6px;font-size:14px;color:var(--rosa-osc)}
  .card p{margin:0;font-size:13px;color:var(--gris);line-height:1.5}
  .card code{background:var(--rosa-suave);color:var(--rosa-osc);padding:1px 6px;border-radius:6px;font-size:12px}

  /* ---------- Swagger ---------- */
  .swagger-ui .wrapper{max-width:1460px}
  .swagger-ui .information-container{display:none}
  .swagger-ui .scheme-container{background:transparent;box-shadow:none;padding:18px 0 4px}
  .swagger-ui .btn.authorize{border-color:var(--rosa);color:var(--rosa);border-radius:10px;font-weight:700}
  .swagger-ui .btn.authorize svg{fill:var(--rosa)}
  .swagger-ui .btn.execute{background:var(--rosa);border-color:var(--rosa);border-radius:10px}
  .swagger-ui .btn{border-radius:10px}
  .swagger-ui .filter-container .operation-filter-input{border:1px solid var(--rosa-borde);border-radius:12px;
        padding:10px 14px}
  .swagger-ui .opblock-tag{border-bottom:2px solid var(--rosa-borde);color:var(--texto);font-weight:800}
  .swagger-ui .opblock-tag small{color:var(--gris)}
  .swagger-ui .opblock{border-radius:12px;box-shadow:none;margin-bottom:10px}
  .swagger-ui .opblock .opblock-summary-method{border-radius:8px;min-width:76px;font-weight:800}
  .swagger-ui .opblock.opblock-post{background:var(--rosa-suave);border-color:var(--rosa)}
  .swagger-ui .opblock.opblock-post .opblock-summary-method{background:var(--rosa)}
  .swagger-ui .opblock.opblock-post .opblock-summary{border-color:var(--rosa)}
  .swagger-ui .opblock.opblock-get{background:var(--lila-suave);border-color:var(--lila)}
  .swagger-ui .opblock.opblock-get .opblock-summary-method{background:var(--lila)}
  .swagger-ui .opblock.opblock-get .opblock-summary{border-color:var(--lila)}
  .swagger-ui .opblock-summary-description{color:var(--gris);font-weight:600}
  .swagger-ui section.models{border-color:var(--rosa-borde);border-radius:14px}
  .swagger-ui .opblock .opblock-section-header{background:rgba(255,255,255,.7)}
  .swagger-ui .response-col_status{font-weight:800;color:var(--rosa-osc)}
  .swagger-ui .unlocked svg, .swagger-ui .locked svg{fill:var(--rosa)}
  .swagger-ui .btn.authorize svg, .swagger-ui .authorization__btn svg{fill:var(--rosa)!important;color:var(--rosa)!important}
  .swagger-ui .renderedMarkdown code, .swagger-ui .markdown code{color:var(--rosa-osc)!important;
        background:var(--rosa-suave)!important;border-radius:6px;padding:1px 6px}
  .swagger-ui .opblock-section-header .tab-header .tab-item.active h4 span:after{background:var(--rosa)!important}
  .swagger-ui .opblock-tag:hover{background:rgba(214,51,132,.04)}
  .swagger-ui .dialog-ux .modal-ux{border-radius:16px;border:1px solid var(--rosa-borde)}
  .swagger-ui .dialog-ux .modal-ux-header h3{color:var(--rosa-osc)}
  footer.pie{text-align:center;color:var(--gris);font-size:12px;padding:26px 0 34px}
  @media (max-width:640px){ .hero h1{font-size:24px} .pill{min-width:0;flex:1} }
</style>
"""

ENCABEZADO = """
<header class="hero">
  <div class="hero-in">
    <div>
      <div class="marca">
        <div class="logo">
          <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden="true">
            <rect x="8" y="26" width="48" height="18" rx="7" fill="#fff"/>
            <path d="M18 26l7-10h14l7 10" fill="none" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>
            <circle cx="20" cy="47" r="7" fill="#ffd1e3" stroke="#fff" stroke-width="3"/>
            <circle cx="44" cy="47" r="7" fill="#ffd1e3" stroke="#fff" stroke-width="3"/>
          </svg>
        </div>
        <div>
          <h1>Carrito IoT API</h1>
          <p>Control remoto del carrito con garra · ESP32 + 2× 74HC595</p>
        </div>
      </div>
      <div class="chips">
        <span class="chip">FastAPI · v__VERSION__</span><span class="chip">Amazon RDS · MySQL</span>
        <span class="chip">21 Stored Procedures</span><span class="chip">WebSocket en tiempo real</span>
      </div>
    </div>
    <div class="estado" aria-live="polite">
      <div class="pill esp" id="ind-api"><small>Servidor API</small><b><span class="dot"></span><span>Comprobando…</span></b></div>
      <div class="pill esp" id="ind-db"><small>Amazon RDS</small><b><span class="dot"></span><span>Comprobando…</span></b></div>
    </div>
  </div>
</header>
<section class="guia">
  <div class="card"><h3>1 · Autentícate</h3>
    <p>Pulsa <b>Authorize</b> e ingresa con el usuario <code>operador</code> (movimientos y DEMO) o el administrador.</p></div>
  <div class="card"><h3>2 · Mueve el carrito</h3>
    <p><code>POST /vehiculos/1/movimientos</code> con <code>{"comando":"AVANZAR"}</code>. Se guarda en estado e historial.</p></div>
  <div class="card"><h3>3 · Ejecuta una DEMO</h3>
    <p><code>POST /vehiculos/1/demos/1/iniciar</code>. Los pasos se transmiten por WebSocket y no van al historial.</p></div>
  <div class="card"><h3>4 · Escucha en tiempo real</h3>
    <p>Conéctate a <code id="ws-url">ws://…/ws/vehiculos/1</code> para recibir cada evento del vehículo.</p></div>
</section>
"""

SCRIPT = """
<footer class="pie">Carrito IoT · Implementación de soluciones IoT</footer>
<script>
  (function(){
    var wsProto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    var el = document.getElementById('ws-url');
    if (el) el.textContent = wsProto + location.host + '/ws/vehiculos/1';
    function pintar(id, clase, texto){
      var n = document.getElementById(id); if(!n) return;
      n.className = 'pill ' + clase; n.querySelector('b span:last-child').textContent = texto;
    }
    async function revisar(url, id){
      var c = new AbortController(); var t = setTimeout(function(){ c.abort(); }, 8000);
      try{
        var r = await fetch(url, {signal:c.signal, cache:'no-store'});
        var d = await r.json().catch(function(){ return {}; });
        if (r.ok && d.estado === 'disponible'){
          pintar(id, 'ok', 'Disponible' + (d.latencia_ms !== undefined ? ' · ' + Math.round(d.latencia_ms) + ' ms' : ''));
        } else { pintar(id, 'mal', 'No disponible'); }
      } catch(e){ pintar(id, 'mal', 'No disponible'); }
      finally{ clearTimeout(t); }
    }
    function ciclo(){ revisar('health', 'ind-api'); revisar('health/db', 'ind-db'); }
    ciclo(); setInterval(ciclo, 30000);
  })();
</script>
"""


def registrar_documentacion(app: FastAPI, version: str, js_url: str = SWAGGER_JS, css_url: str = SWAGGER_CSS) -> None:
    @app.get("/docs", include_in_schema=False)
    def swagger_personalizado() -> HTMLResponse:
        base = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} · Documentación",
            swagger_js_url=js_url,
            swagger_css_url=css_url,
            swagger_favicon_url=FAVICON,
            swagger_ui_parameters={
                "docExpansion": "none",
                "filter": True,
                "persistAuthorization": True,
                "displayRequestDuration": True,
                "defaultModelsExpandDepth": -1,
                "tryItOutEnabled": True,
            },
        ).body.decode("utf-8")
        html = base.replace("</head>", ESTILOS + "</head>", 1)
        html = html.replace("<body>", "<body>" + ENCABEZADO.replace("__VERSION__", version), 1)
        html = html.replace("</body>", SCRIPT + "</body>", 1)
        return HTMLResponse(html)
