import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, make_response, redirect, url_for

# >>> IMPORTS DO SEU PROJETO
# Se existir core/license_core.py e core/pricing.py, vamos usar.
from core.license_core import validar_chave
from core.pricing import calcular_preco  # ajuste se o nome da função for diferente no seu pricing.py

app = Flask(__name__)

APP_NAME = "Arte Preço Pro"

# =========================================================
# Helpers
# =========================================================

def _get_device_id():
    """
    O device_id vem do navegador (localStorage) e é enviado por header/query.
    """
    # 1) Header
    device_id = request.headers.get("X-Device-Id", "").strip()
    if device_id:
        return device_id

    # 2) Query / form
    device_id = request.args.get("device_id", "").strip()
    if device_id:
        return device_id

    device_id = request.form.get("device_id", "").strip()
    if device_id:
        return device_id

    # 3) JSON
    try:
        body = request.get_json(silent=True) or {}
        device_id = str(body.get("device_id", "")).strip()
        if device_id:
            return device_id
    except Exception:
        pass

    return ""


def _json_ok(**data):
    return jsonify({"ok": True, **data})


def _json_err(msg, **data):
    return jsonify({"ok": False, "error": msg, **data})


# =========================================================
# PWA files
# =========================================================

@app.get("/manifest.webmanifest")
def manifest():
    manifest_data = {
        "name": APP_NAME,
        "short_name": "ArtePreço",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#DCE6D5",
        "theme_color": "#4E6B3E",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    resp = make_response(json.dumps(manifest_data, ensure_ascii=False))
    resp.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    return resp


@app.get("/service-worker.js")
def service_worker():
    """
    Service Worker simples: cache básico para PWA.
    """
    js = r"""
const CACHE_NAME = "arte-preco-pro-v1";
const URLS_TO_CACHE = [
  "/",
  "/app",
  "/manifest.webmanifest",
  "/static/icon-192.png",
  "/static/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(URLS_TO_CACHE))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : null)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((resp) => resp || fetch(event.request))
  );
});
"""
    resp = make_response(js)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return resp


# =========================================================
# Telas
# =========================================================

HTML_BASE = r"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{title}}</title>

  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#4E6B3E"/>

  <style>
    body { font-family: Arial, sans-serif; background:#DCE6D5; margin:0; padding:0; }
    .wrap { max-width: 820px; margin: 40px auto; padding: 0 16px; }
    .card { background:#EAF1E5; border:1px solid #c7d4bf; border-radius:14px; padding:18px; }
    h1 { margin:0 0 10px; }
    .muted { color:#445; opacity:.85; margin: 6px 0 14px; }
    label { display:block; font-weight:700; margin-top:12px; }
    input { width:100%; padding:12px; border-radius:10px; border:1px solid #b8c5b0; font-size:16px; background:#fff; box-sizing:border-box; }
    button { width:100%; margin-top:14px; padding:14px 12px; border:0; border-radius:12px; background:#4E6B3E; color:#fff; font-size:18px; font-weight:700; cursor:pointer; }
    .row { display:flex; gap:12px; }
    .row > div { flex:1; }
    .msg { margin-top:12px; padding:10px; border-radius:10px; background:#fff; border:1px solid #c7d4bf; }
    .ok { color:#1e6b1e; font-weight:700; }
    .err { color:#9a1c1c; font-weight:700; }
    .btn2 { background:#2d3d25; }
    .btn3 { background:#7a1f1f; }
    .big { font-size: 22px; font-weight: 900; margin-top: 10px; }
    .hide { display:none; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      {{body|safe}}
    </div>
  </div>

<script>
  // registra SW
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(()=>{});
  }

  // device_id persistente (fica no celular)
  function getDeviceId() {
    let id = localStorage.getItem("ap_device_id");
    if (!id) {
      id = "dev_" + Math.random().toString(16).slice(2) + "_" + Date.now();
      localStorage.setItem("ap_device_id", id);
    }
    return id;
  }

  function setKey(key) {
    localStorage.setItem("ap_key", key);
  }
  function getKey() {
    return localStorage.getItem("ap_key") || "";
  }
</script>

{{scripts|safe}}
</body>
</html>
"""


@app.get("/")
def home():
    body = r"""
      <h1>Ativação do Arte Preço Pro</h1>
      <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>

      <label>Chave</label>
      <input id="key" placeholder="Cole sua chave AP-..." autocomplete="off"/>

      <button onclick="ativar()">Ativar</button>

      <div id="msg" class="msg hide"></div>
    """

    scripts = r"""
<script>
  document.getElementById("key").value = getKey();

  function showMsg(ok, text) {
    const el = document.getElementById("msg");
    el.classList.remove("hide");
    el.innerHTML = ok
      ? '<span class="ok">✅ ' + text + '</span>'
      : '<span class="err">❌ ' + text + '</span>';
  }

  async function ativar() {
    const key = document.getElementById("key").value.trim();
    if (!key) return showMsg(false, "Cole uma chave primeiro.");

    const device_id = getDeviceId();

    try {
      const resp = await fetch("/api/ativar", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Device-Id": device_id },
        body: JSON.stringify({ chave: key, device_id })
      });
      const data = await resp.json();

      if (data.ok) {
        setKey(key);
        showMsg(true, data.message || "Ativado!");
        setTimeout(()=>{ window.location.href="/app"; }, 600);
      } else {
        showMsg(false, data.error || "Chave inválida.");
      }
    } catch (e) {
      showMsg(false, "Erro ao ativar. Tente novamente.");
    }
  }
</script>
"""
    return render_template_string(HTML_BASE, title=APP_NAME, body=body, scripts=scripts)


@app.get("/app")
def app_page():
    body = r"""
      <h1>Arte Preço Pro</h1>
      <div id="status" class="msg">Verificando ativação...</div>

      <div id="conteudo" class="hide">
        <div class="muted">Preencha os campos e clique em <b>Calcular</b>.</div>

        <label>Produto</label>
        <input id="produto" placeholder="Ex: Logo Barber Prime"/>

        <div class="row">
          <div>
            <label>Custo do Material (R$)</label>
            <input id="custo_material" inputmode="decimal" placeholder="0"/>
          </div>
          <div>
            <label>Horas Trabalhadas</label>
            <input id="horas" inputmode="decimal" placeholder="0"/>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Valor da Hora (R$)</label>
            <input id="valor_hora" inputmode="decimal" placeholder="0"/>
          </div>
          <div>
            <label>Despesas Extras (R$)</label>
            <input id="despesas" inputmode="decimal" placeholder="0"/>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Margem de Lucro (%)</label>
            <input id="margem" inputmode="decimal" placeholder="0"/>
          </div>
          <div>
            <label>Validade (dias)</label>
            <input id="validade" inputmode="numeric" value="7"/>
          </div>
        </div>

        <button onclick="calcular()">Calcular</button>

        <div id="resultado" class="msg hide"></div>

        <div class="row">
          <div><button class="btn2" onclick="atualizar()">Atualizar</button></div>
          <div><button class="btn3" onclick="sair()">Sair</button></div>
        </div>
      </div>
    """

    scripts = r"""
<script>
  function showStatus(ok, text) {
    const el = document.getElementById("status");
    el.innerHTML = ok
      ? '<span class="ok">✅ ' + text + '</span>'
      : '<span class="err">❌ ' + text + '</span>';
  }

  function showResultado(html) {
    const el = document.getElementById("resultado");
    el.classList.remove("hide");
    el.innerHTML = html;
  }

  function toNum(v) {
    if (!v) return 0;
    v = String(v).replace(/\./g, "").replace(",", "."); // aceita 1.234,56
    const n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  }

  async function checarAtivacao() {
    const key = getKey();
    const device_id = getDeviceId();
    if (!key) {
      window.location.href = "/";
      return;
    }

    try {
      const resp = await fetch("/api/status", {
        headers: { "X-Device-Id": device_id }
      });
      const data = await resp.json();

      if (data.ok) {
        showStatus(true, data.message || "Ativado.");
        document.getElementById("conteudo").classList.remove("hide");
      } else {
        showStatus(false, data.error || "Não ativado.");
        localStorage.removeItem("ap_key");
        setTimeout(()=>{ window.location.href="/"; }, 600);
      }
    } catch(e) {
      showStatus(false, "Falha ao validar. Recarregue a página.");
    }
  }

  async function calcular() {
    const device_id = getDeviceId();
    const key = getKey();

    const payload = {
      chave: key,
      device_id: device_id,
      produto: document.getElementById("produto").value.trim(),
      custo_material: toNum(document.getElementById("custo_material").value),
      horas: toNum(document.getElementById("horas").value),
      valor_hora: toNum(document.getElementById("valor_hora").value),
      despesas: toNum(document.getElementById("despesas").value),
      margem: toNum(document.getElementById("margem").value),
      validade: parseInt(document.getElementById("validade").value || "0", 10) || 0
    };

    try {
      const resp = await fetch("/api/calcular", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Device-Id": device_id },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (!data.ok) {
        showResultado('<span class="err">❌ ' + (data.error || 'Erro ao calcular') + '</span>');
        return;
      }

      const html = `
        <div><b>Produto:</b> ${data.produto}</div>
        <div class="big">Preço Final: ${data.preco_final_fmt}</div>
        <div><b>Validade:</b> ${data.validade} dia(s)</div>
      `;
      showResultado(html);

    } catch (e) {
      showResultado('<span class="err">❌ Erro ao calcular. Tente novamente.</span>');
    }
  }

  function sair() {
    // sai do app e volta para ativação
    localStorage.removeItem("ap_key");
    window.location.href = "/";
  }

  function atualizar() {
    window.location.reload();
  }

  checarAtivacao();
</script>
"""
    return render_template_string(HTML_BASE, title=APP_NAME, body=body, scripts=scripts)


# =========================================================
# API
# =========================================================

@app.post("/api/ativar")
def api_ativar():
    device_id = _get_device_id()
    body = request.get_json(silent=True) or {}
    chave = str(body.get("chave", "")).strip()

    if not chave:
        return _json_err("Cole a chave.")

    if not device_id:
        return _json_err("Device ID ausente. Recarregue a página e tente de novo.")

    ok, msg = validar_chave(chave, device_id)
    if ok:
        return _json_ok(message=msg or "Ativado.")
    return _json_err(msg or "Chave inválida.")


@app.get("/api/status")
def api_status():
    device_id = _get_device_id()
    # chave fica no navegador, então aqui só checamos se ele consegue chamar.
    # A tela /app chama esse endpoint e se der erro ele manda pra ativação.
    # Se quiser validar de verdade aqui, precisa mandar a chave também.
    return _json_ok(message="Conexão OK. Abra /app para usar.")


@app.post("/api/calcular")
def api_calcular():
    device_id = _get_device_id()
    body = request.get_json(silent=True) or {}

    chave = str(body.get("chave", "")).strip()
    if not chave:
        return _json_err("Você saiu do app. Ative novamente.")

    if not device_id:
        return _json_err("Device ID ausente. Recarregue e tente novamente.")

    ok, msg = validar_chave(chave, device_id)
    if not ok:
        return _json_err(msg or "Chave inválida. Ative novamente.")

    produto = str(body.get("produto", "")).strip() or "Sem nome"
    custo_material = float(body.get("custo_material", 0) or 0)
    horas = float(body.get("horas", 0) or 0)
    valor_hora = float(body.get("valor_hora", 0) or 0)
    despesas = float(body.get("despesas", 0) or 0)
    margem = float(body.get("margem", 0) or 0)
    validade = int(body.get("validade", 0) or 0)

    try:
        # A sua função de pricing deve retornar um número final.
        # Se sua função for diferente, me diga o conteúdo do core/pricing.py e eu ajusto.
        preco_final = calcular_preco(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas_extras=despesas,
            margem_lucro_percent=margem,
        )
    except TypeError:
        # fallback caso o pricing.py seja diferente
        try:
            preco_final = calcular_preco(custo_material, horas, valor_hora, despesas, margem)
        except Exception as e:
            return _json_err(f"Erro no cálculo: {e}")
    except Exception as e:
        return _json_err(f"Erro no cálculo: {e}")

    def brl(v):
        return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return _json_ok(
        produto=produto,
        preco_final=float(preco_final),
        preco_final_fmt=brl(float(preco_final)),
        validade=validade,
        message=msg
    )


# =========================================================
# Local run (só pra PC)
# =========================================================
if __name__ == "__main__":
    # No PC: http://127.0.0.1:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
