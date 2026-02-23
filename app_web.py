import os
from flask import Flask, send_from_directory, render_template_string, jsonify, request

app = Flask(__name__)

# ========= PWA: ROTAS NA RAIZ =========
@app.get("/sw.js")
def pwa_sw_root():
    # entrega o service worker da pasta static, mas em /sw.js
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.get("/manifest.webmanifest")
def pwa_manifest_root():
    # se seu manifest está como static/manifest.json, vamos entregar como webmanifest
    # prioridade: manifest.webmanifest -> manifest.json
    if os.path.exists(os.path.join("static", "manifest.webmanifest")):
        return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# ========= TELA DO APP =========
HTML = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Arte Preço Pro</title>

  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#4d6b3a">

  <style>
    body{font-family:Arial;background:#dfe8d6;margin:0}
    .wrap{max-width:720px;margin:0 auto;padding:18px}
    .card{background:#e9f0e0;border-radius:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
    h1{margin:0 0 12px}
    label{display:block;font-weight:700;margin:10px 0 6px}
    input{width:100%;padding:12px;border-radius:10px;border:1px solid #c6d3bb;font-size:16px}
    .row{display:flex;gap:10px}
    .row>div{flex:1}
    button{width:100%;padding:14px;border:0;border-radius:12px;background:#4d6b3a;color:#fff;font-size:18px;font-weight:700;margin-top:14px}
    .ok{background:#fff;border-radius:12px;padding:12px;margin-top:12px;border:1px solid #c6d3bb}
    .small{font-size:13px;opacity:.8}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Arte Preço Pro</h1>
      <div class="small">Se aparecer "Instalar app", o PWA está OK.</div>

      <label>Produto</label>
      <input id="produto" placeholder="Ex: Logo"/>

      <label>Custo do Material (R$)</label>
      <input id="custo_material" inputmode="decimal" placeholder="Ex: 10"/>

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" inputmode="decimal" placeholder="Ex: 4"/>
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" inputmode="decimal" placeholder="Ex: 30"/>
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="extras" inputmode="decimal" placeholder="Ex: 2"/>

      <label>Margem de Lucro (%)</label>
      <input id="margem" inputmode="decimal" placeholder="Ex: 80"/>

      <label>Validade (dias)</label>
      <input id="validade" inputmode="numeric" placeholder="Ex: 7"/>

      <button onclick="calcular()">Calcular</button>

      <div id="saida" class="ok" style="display:none;"></div>
    </div>
  </div>

<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      } catch (e) {}
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

    if(!data.ok){
      saida.innerHTML = 'Erro: ' + (data.msg || 'falha');
      return;
    }

    saida.innerHTML = `
      <div><b>Produto:</b> ${data.produto}</div>
      <div><b>Custo Base:</b> R$ ${data.custo_base.toFixed(2).replace('.',',')}</div>
      <div style="font-size:28px;font-weight:800;margin-top:8px;">Preço Final: R$ ${data.preco_final.toFixed(2).replace('.',',')}</div>
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
        preco_final = custo_base * (1 + margem/100.0)

        return jsonify({
            "ok": True,
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "validade": validade
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
