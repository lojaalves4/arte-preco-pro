import os
from flask import Flask, request, render_template_string, jsonify, send_from_directory

app = Flask(__name__)

# ====== PWA: manifest + service worker + ícones ======
@app.get("/manifest.webmanifest")
def manifest():
    # Servindo o manifest como arquivo (se existir) OU como JSON gerado
    path = os.path.join("static", "manifest.webmanifest")
    if os.path.exists(path):
        return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")

    # fallback: gera um manifest padrão
    manifest_json = {
        "name": "Arte Preço Pro",
        "short_name": "ArtePreço",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#dfe8d6",
        "theme_color": "#4d6b3a",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return jsonify(manifest_json)

@app.get("/sw.js")
def sw():
    # sw.js fica em /static/sw.js
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# ====== Página principal ======
HTML = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Arte Preço Pro</title>

  <!-- PWA -->
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#4d6b3a">

  <style>
    body { font-family: Arial, sans-serif; background:#dfe8d6; margin:0; padding:0; }
    .wrap { max-width:720px; margin:0 auto; padding:18px; }
    .card { background:#e9f0e0; border-radius:12px; padding:16px; box-shadow:0 1px 4px rgba(0,0,0,.08); }
    h1 { margin:0 0 12px; }
    .row { display:flex; gap:10px; }
    .row > div { flex:1; }
    label { display:block; font-weight:700; margin:10px 0 6px; }
    input { width:100%; padding:12px; border-radius:10px; border:1px solid #c6d3bb; font-size:16px; }
    button { width:100%; padding:14px; border:0; border-radius:12px; background:#4d6b3a; color:#fff; font-size:18px; font-weight:700; margin-top:14px; }
    .small { font-size:13px; opacity:.8; }
    .ok { background:#fff; border-radius:12px; padding:12px; margin-top:12px; border:1px solid #c6d3bb; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Arte Preço Pro</h1>
      <div class="small">Se aparecer “Instalar app”, o PWA está OK.</div>

      <label>Produto</label>
      <input id="produto" placeholder="Ex: Logo" />

      <label>Custo do Material (R$)</label>
      <input id="custo_material" inputmode="decimal" placeholder="Ex: 10" />

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" inputmode="decimal" placeholder="Ex: 4" />
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" inputmode="decimal" placeholder="Ex: 30" />
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="extras" inputmode="decimal" placeholder="Ex: 2" />

      <label>Margem de Lucro (%)</label>
      <input id="margem" inputmode="decimal" placeholder="Ex: 80" />

      <label>Validade (dias)</label>
      <input id="validade" inputmode="numeric" placeholder="Ex: 7" />

      <button onclick="calcular()">Calcular</button>

      <div id="saida" class="ok" style="display:none;"></div>
    </div>
  </div>

<script>
  // registra service worker (PWA)
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        await navigator.serviceWorker.register('/sw.js', { scope: '/' });
        // console.log('SW ok');
      } catch (e) {
        // console.log('SW falhou', e);
      }
    });
  }

  function num(v){ return parseFloat(String(v).replace(',','.')) || 0; }

  async function calcular(){
    const payload = {
      produto: document.getElementById('produto').value || '',
      custo_material: num(document.getElementById('custo_material').value),
      horas: num(document.getElementById('horas').value),
      valor_hora: num(document.getElementById('valor_hora').value),
      extras: num(document.getElementById('extras').value),
      margem: num(document.getElementById('margem').value),
      validade: parseInt(document.getElementById('validade').value || '0', 10) || 0
    };

    const r = await fetch('/api/calcular', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });

    const data = await r.json();
    const saida = document.getElementById('saida');
    saida.style.display = 'block';

    if (!data.ok){
      saida.innerHTML = 'Erro: ' + (data.msg || 'falha');
      return;
    }

    saida.innerHTML = `
      <div><b>Produto:</b> ${data.produto}</div>
      <div><b>Custo Base:</b> R$ ${data.custo_base.toFixed(2).replace('.',',')}</div>
      <div style="font-size:28px; font-weight:800; margin-top:8px;">Preço Final: R$ ${data.preco_final.toFixed(2).replace('.',',')}</div>
      <div><b>Validade:</b> ${data.validade} dia(s)</div>
    `;
  }
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.post("/api/calcular")
def api_calcular():
    try:
        d = request.get_json(force=True) or {}
        produto = (d.get("produto") or "").strip()
        custo_material = float(d.get("custo_material") or 0)
        horas = float(d.get("horas") or 0)
        valor_hora = float(d.get("valor_hora") or 0)
        extras = float(d.get("extras") or 0)
        margem = float(d.get("margem") or 0)
        validade = int(d.get("validade") or 0)

        custo_base = custo_material + (horas * valor_hora) + extras
        preco_final = custo_base * (1 + (margem / 100.0))

        return jsonify({
            "ok": True,
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "validade": validade
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 400

# Para rodar local (não afeta Vercel)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
