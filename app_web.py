from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
import os

app = Flask(__name__)

# =========================================================
# Helpers (licença e preço)
# =========================================================

def validar_chave_wrapper(chave: str, device_id: str):
    """
    Compatível com versões diferentes do license_core.validar_chave:
    - validar_chave(chave, device_id)
    - validar_chave(chave)
    """
    try:
        from core.license_core import validar_chave  # type: ignore
    except Exception:
        return False, "Sistema de licença não encontrado (core.license_core)."

    try:
        return validar_chave(chave, device_id)
    except TypeError:
        try:
            return validar_chave(chave)
        except Exception as e:
            return False, f"Erro ao validar chave: {e}"
    except Exception as e:
        return False, f"Erro ao validar chave: {e}"


def calcular_preco_local(custo_material: float, horas: float, valor_hora: float, despesas_extras: float, margem_percent: float):
    custo_base = float(custo_material) + (float(horas) * float(valor_hora)) + float(despesas_extras)
    margem = float(margem_percent) / 100.0
    preco_final = custo_base * (1.0 + margem)
    return custo_base, preco_final


def brl(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


# =========================================================
# UI (HTML)
# =========================================================

HTML = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Arte Preço Pro</title>

  <!-- PWA -->
  <meta name="theme-color" content="#4d6b3a">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/static/icon-192.png">

  <style>
    :root{
      --bg:#dfe8d6;
      --card:#e7efe0;
      --btn:#4d6b3a;
      --btn2:#2f3b2b;
      --txt:#101510;
      --muted:#3b4a36;
      --stroke:#b7c7ad;
      --white:#ffffff;
    }
    body{
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background: var(--bg);
      color: var(--txt);
    }
    .wrap{
      max-width: 520px;
      margin: 0 auto;
      padding: 18px 14px 26px;
    }
    h1{
      font-size: 40px;
      margin: 12px 0 10px;
      letter-spacing: -1px;
    }
    .card{
      background: var(--card);
      border: 1px solid var(--stroke);
      border-radius: 14px;
      padding: 14px;
      box-shadow: 0 1px 0 rgba(0,0,0,.03);
    }
    label{
      font-weight: 700;
      display:block;
      margin: 10px 0 6px;
      font-size: 18px;
    }
    input{
      width: 100%;
      box-sizing: border-box;
      padding: 12px 12px;
      border-radius: 10px;
      border: 1px solid var(--stroke);
      background: var(--white);
      font-size: 18px;
      outline: none;
    }
    .row{
      display:flex;
      gap: 10px;
    }
    .row > div{ flex:1; }
    .btn{
      width:100%;
      margin-top: 14px;
      padding: 14px 16px;
      border-radius: 12px;
      border: none;
      background: var(--btn);
      color: white;
      font-size: 20px;
      font-weight: 800;
      cursor:pointer;
    }
    .btn:active{ transform: translateY(1px); }
    .btn2{
      width:100%;
      margin-top: 10px;
      padding: 12px 16px;
      border-radius: 12px;
      border: none;
      background: var(--btn2);
      color: white;
      font-size: 18px;
      font-weight: 800;
      cursor:pointer;
    }
    .msg{
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--stroke);
      background: #ffffff;
      font-weight: 700;
    }
    .ok{ color: #1b5e20; }
    .bad{ color: #b71c1c; }
    .muted{ color: var(--muted); font-weight: 600; }
    .big{
      font-size: 38px;
      font-weight: 900;
      margin: 8px 0 6px;
    }
    .result{
      margin-top: 14px;
      padding: 14px;
      border-radius: 12px;
      background: #fff;
      border: 1px solid var(--stroke);
    }
    .actions{
      display:flex;
      gap:10px;
      margin-top: 10px;
    }
    .actions button{ flex:1; }
    .hide{ display:none; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Arte Preço Pro</h1>

    <!-- TELA ATIVAÇÃO -->
    <div id="card_ativacao" class="card">
      <h2 style="margin:0 0 6px;">Ativação do Arte Preço Pro</h2>
      <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>

      <label for="chave">Chave</label>
      <input id="chave" placeholder="Cole sua chave AP-..." autocomplete="off">

      <button class="btn" id="btn_ativar">Ativar</button>

      <div id="msg_ativacao" class="msg hide"></div>
    </div>

    <!-- TELA APP -->
    <div id="card_app" class="card hide">
      <div id="status" class="msg ok">✅ Ativado</div>

      <label>Cliente</label>
      <input id="cliente" placeholder="Nome do cliente">

      <label>Contato</label>
      <input id="contato" placeholder="WhatsApp / Telefone / E-mail">

      <label>Endereço</label>
      <input id="endereco" placeholder="Rua, número, bairro, cidade - UF">

      <hr style="border:none;border-top:1px solid var(--stroke); margin:14px 0;">

      <label>Produto</label>
      <input id="produto" placeholder="Ex: Logo">

      <label>Custo do Material (R$)</label>
      <input id="custo_material" inputmode="decimal" placeholder="Ex: 10">

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" inputmode="decimal" placeholder="Ex: 4">
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" inputmode="decimal" placeholder="Ex: 30">
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="despesas_extras" inputmode="decimal" placeholder="Ex: 2">

      <label>Margem de Lucro (%)</label>
      <input id="margem" inputmode="decimal" placeholder="Ex: 80">

      <label>Validade (dias)</label>
      <input id="validade" inputmode="numeric" value="7">

      <button class="btn" id="btn_calcular">Calcular</button>

      <div id="out" class="result hide"></div>

      <div class="actions">
        <button class="btn2" id="btn_revalidar">Revalidar chave</button>
        <button class="btn2" id="btn_sair">Sair</button>
      </div>
    </div>

  </div>

<script>
  // PWA: registrar service worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(()=>{});
    });
  }

  function getDeviceId(){
    let id = localStorage.getItem("ap_device_id");
    if(!id){
      id = "dev_" + Math.random().toString(16).slice(2) + "_" + Date.now();
      localStorage.setItem("ap_device_id", id);
    }
    return id;
  }

  function saveKey(k){ localStorage.setItem("ap_key", k); }
  function getKey(){ return localStorage.getItem("ap_key") || ""; }
  function clearKey(){ localStorage.removeItem("ap_key"); }

  function show(el){ el.classList.remove("hide"); }
  function hide(el){ el.classList.add("hide"); }

  const cardAtiv = document.getElementById("card_ativacao");
  const cardApp  = document.getElementById("card_app");
  const msgAtiv  = document.getElementById("msg_ativacao");
  const statusEl = document.getElementById("status");
  const chaveInp = document.getElementById("chave");

  async function apiAtivar(chave){
    const device_id = getDeviceId();
    const r = await fetch("/api/ativar", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ chave, device_id })
    });
    return await r.json();
  }

  function entrarNoApp(textoStatus){
    statusEl.textContent = textoStatus || "✅ Ativado";
    hide(cardAtiv);
    show(cardApp);
  }

  function voltarParaAtivacao(msg){
    show(cardAtiv);
    hide(cardApp);
    if(msg){
      msgAtiv.textContent = msg;
      msgAtiv.className = "msg bad";
      show(msgAtiv);
    } else {
      hide(msgAtiv);
    }
  }

  window.addEventListener("load", async ()=>{
    const k = getKey();
    if(k){
      try{
        const j = await apiAtivar(k);
        if(j.ok){
          entrarNoApp("✅ " + (j.msg || "Ativado"));
          return;
        }else{
          clearKey();
          voltarParaAtivacao("Chave inválida. Cole novamente.");
          return;
        }
      }catch(e){
        voltarParaAtivacao("Falha ao conectar. Tente novamente.");
      }
    }
  });

  document.getElementById("btn_ativar").addEventListener("click", async ()=>{
    const k = (chaveInp.value || "").trim();
    if(!k){
      msgAtiv.textContent = "Cole a chave.";
      msgAtiv.className = "msg bad";
      show(msgAtiv);
      return;
    }
    try{
      const j = await apiAtivar(k);
      if(j.ok){
        saveKey(k);
        msgAtiv.textContent = "✅ " + (j.msg || "Ativado");
        msgAtiv.className = "msg ok";
        show(msgAtiv);
        entrarNoApp("✅ " + (j.msg || "Ativado"));
      }else{
        msgAtiv.textContent = j.msg || "Chave inválida.";
        msgAtiv.className = "msg bad";
        show(msgAtiv);
      }
    }catch(e){
      msgAtiv.textContent = "Erro ao ativar. Tente novamente.";
      msgAtiv.className = "msg bad";
      show(msgAtiv);
    }
  });

  document.getElementById("btn_revalidar").addEventListener("click", async ()=>{
    const k = getKey();
    if(!k){
      voltarParaAtivacao("Cole a chave novamente.");
      return;
    }
    try{
      const j = await apiAtivar(k);
      if(j.ok){
        statusEl.textContent = "✅ " + (j.msg || "Ativado");
        alert("Chave OK ✅");
      }else{
        clearKey();
        voltarParaAtivacao("Chave inválida. Cole novamente.");
      }
    }catch(e){
      alert("Falha ao revalidar. Tente novamente.");
    }
  });

  document.getElementById("btn_sair").addEventListener("click", ()=>{
    // Só volta pra tela de ativação. NÃO APAGA A CHAVE.
    voltarParaAtivacao("");
  });

  function n(v){
    if(v === null || v === undefined) return 0;
    const s = String(v).replace(".", "").replace(",", ".");
    const x = parseFloat(s);
    return isNaN(x) ? 0 : x;
  }

  async function apiCalcular(payload){
    const r = await fetch("/api/calcular", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });
    return await r.json();
  }

  document.getElementById("btn_calcular").addEventListener("click", async ()=>{
    const k = getKey();
    if(!k){
      voltarParaAtivacao("Cole a chave para continuar.");
      return;
    }

    const cliente  = (document.getElementById("cliente").value || "").trim();
    const contato  = (document.getElementById("contato").value || "").trim();
    const endereco = (document.getElementById("endereco").value || "").trim();

    const d = {
      chave: k,
      device_id: getDeviceId(),
      cliente,
      contato,
      endereco,
      produto: (document.getElementById("produto").value || "").trim(),
      custo_material: n(document.getElementById("custo_material").value),
      horas: n(document.getElementById("horas").value),
      valor_hora: n(document.getElementById("valor_hora").value),
      despesas_extras: n(document.getElementById("despesas_extras").value),
      margem: n(document.getElementById("margem").value),
      validade_dias: parseInt(document.getElementById("validade").value || "7", 10) || 7
    };

    try{
      const j = await apiCalcular(d);
      if(!j.ok){
        if(j.code === "LICENSE"){
          clearKey();
          voltarParaAtivacao(j.msg || "Chave inválida.");
          return;
        }
        alert(j.msg || "Erro ao calcular.");
        return;
      }

      const out = document.getElementById("out");
      out.innerHTML = `
        <div><b>Cliente:</b> ${j.cliente || "-"}</div>
        <div><b>Contato:</b> ${j.contato || "-"}</div>
        <div><b>Endereço:</b> ${j.endereco || "-"}</div>
        <hr style="border:none;border-top:1px solid #eee; margin:10px 0;">
        <div><b>Produto:</b> ${j.produto || "-"}</div>
        <div><b>Custo Base:</b> ${j.custo_base_fmt || "-"}</div>
        <div class="big">Preço Final: ${j.preco_final_fmt || "-"}</div>
        <div class="muted">Validade: ${j.validade_dias || 7} dia(s)</div>
        <button class="btn" id="btn_pdf">Gerar PDF</button>
      `;
      show(out);

      document.getElementById("btn_pdf").addEventListener("click", ()=>{
        const url = new URL(window.location.origin + "/pdf");
        url.searchParams.set("cliente", j.cliente || "");
        url.searchParams.set("contato", j.contato || "");
        url.searchParams.set("endereco", j.endereco || "");
        url.searchParams.set("produto", j.produto || "");
        url.searchParams.set("custo_base", j.custo_base_fmt || "");
        url.searchParams.set("preco_final", j.preco_final_fmt || "");
        url.searchParams.set("validade_dias", String(j.validade_dias || 7));
        window.open(url.toString(), "_blank");
      });

    }catch(e){
      alert("Erro ao calcular. Tente novamente.");
    }
  });
</script>
</body>
</html>
"""


# =========================================================
# Routes
# =========================================================

@app.get("/")
def home():
    return render_template_string(HTML)


@app.get("/manifest.webmanifest")
def manifest():
    # PWA manifest
    m = """
{
  "name": "Arte Preço Pro",
  "short_name": "ArtePreço",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#dfe8d6",
  "theme_color": "#4d6b3a",
  "icons": [
    { "src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
""".strip()
    return Response(m, mimetype="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    # Service worker tem que ficar na raiz pra controlar o site todo
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.post("/api/ativar")
def api_ativar():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()
    device_id = (data.get("device_id") or "").strip() or "device_unknown"

    if not chave:
        return jsonify(ok=False, msg="Cole a chave.", code="VALIDATION")

    ok, msg = validar_chave_wrapper(chave, device_id)
    return jsonify(ok=bool(ok), msg=str(msg))


@app.post("/api/calcular")
def api_calcular():
    data = request.get_json(silent=True) or {}

    chave = (data.get("chave") or "").strip()
    device_id = (data.get("device_id") or "").strip() or "device_unknown"

    ok, msg = validar_chave_wrapper(chave, device_id)
    if not ok:
        return jsonify(ok=False, msg=str(msg), code="LICENSE")

    cliente = (data.get("cliente") or "").strip()
    contato = (data.get("contato") or "").strip()
    endereco = (data.get("endereco") or "").strip()

    produto = (data.get("produto") or "").strip()
    custo_material = float(data.get("custo_material") or 0)
    horas = float(data.get("horas") or 0)
    valor_hora = float(data.get("valor_hora") or 0)
    despesas_extras = float(data.get("despesas_extras") or 0)
    margem = float(data.get("margem") or 0)
    validade_dias = int(data.get("validade_dias") or 7)

    custo_base, preco_final = calcular_preco_local(
        custo_material=custo_material,
        horas=horas,
        valor_hora=valor_hora,
        despesas_extras=despesas_extras,
        margem_percent=margem
    )

    return jsonify(
        ok=True,
        cliente=cliente,
        contato=contato,
        endereco=endereco,
        produto=produto,
        custo_base=custo_base,
        custo_base_fmt=brl(custo_base),
        preco_final=preco_final,
        preco_final_fmt=brl(preco_final),
        validade_dias=validade_dias
    )


@app.get("/pdf")
def pdf_view():
    cliente = request.args.get("cliente", "")
    contato = request.args.get("contato", "")
    endereco = request.args.get("endereco", "")
    produto = request.args.get("produto", "")
    custo_base = request.args.get("custo_base", "")
    preco_final = request.args.get("preco_final", "")
    validade_dias = request.args.get("validade_dias", "7")

    html = f"""
    <!doctype html>
    <html lang="pt-br">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Orçamento - Arte Preço Pro</title>
      <style>
        body{{font-family:Arial, sans-serif; padding:24px;}}
        .box{{border:1px solid #ddd; border-radius:12px; padding:18px; max-width:560px;}}
        h1{{margin:0 0 12px;}}
        .big{{font-size:34px; font-weight:900; margin:10px 0;}}
        .muted{{color:#555;}}
        .line{{border:none;border-top:1px solid #eee;margin:12px 0;}}
        @media print {{ .noprint {{ display:none; }} }}
      </style>
    </head>
    <body>
      <div class="box">
        <h1>ORÇAMENTO</h1>

        <div><b>Cliente:</b> {cliente or "-"}</div>
        <div><b>Contato:</b> {contato or "-"}</div>
        <div><b>Endereço:</b> {endereco or "-"}</div>

        <hr class="line">

        <div><b>Produto:</b> {produto or "-"}</div>
        <div><b>Custo Base:</b> {custo_base or "-"}</div>
        <div class="big">Preço Final: {preco_final or "-"}</div>
        <div class="muted">Validade: {validade_dias} dia(s)</div>

        <div class="muted" style="margin-top:16px;">Gerado pelo Arte Preço Pro</div>
      </div>

      <div class="noprint" style="margin-top:16px;">
        <button onclick="window.print()">Imprimir / Salvar em PDF</button>
      </div>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
