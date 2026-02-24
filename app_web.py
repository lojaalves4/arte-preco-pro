# app_web.py  (APAGA TUDO E COLA ISSO)

from flask import Flask, request, jsonify, send_from_directory, make_response
from datetime import datetime
import io

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Licença (se o seu core já existe, ele vai usar)
try:
    from core.license_core import validar_chave
except Exception:
    validar_chave = None

app = Flask(__name__, static_folder="static")


# -----------------------------
# Helpers
# -----------------------------
def brl(valor: float) -> str:
    # Formata simples PT-BR
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def calcular_preco_simples(custo_material, horas, valor_hora, despesas, margem):
    custo_base = float(custo_material) + (float(horas) * float(valor_hora)) + float(despesas)
    preco_final = custo_base * (1.0 + (float(margem) / 100.0))
    return custo_base, preco_final


def gerar_pdf_orcamento(dados: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    # Cabeçalho
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 60, "Orçamento - Arte Preço Pro")

    c.setFont("Helvetica", 10)
    c.drawString(40, h - 80, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # Dados do cliente
    y = h - 120
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Dados do Cliente")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Nome: {dados.get('cliente_nome','')}")
    y -= 16
    c.drawString(40, y, f"Contato: {dados.get('cliente_contato','')}")
    y -= 16
    c.drawString(40, y, f"Endereço: {dados.get('cliente_endereco','')}")
    y -= 24

    # Dados do orçamento
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Detalhes do Serviço")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Produto/Serviço: {dados.get('produto','')}")
    y -= 16
    c.drawString(40, y, f"Custo do material: {brl(float(dados.get('custo_material',0) or 0))}")
    y -= 16
    c.drawString(40, y, f"Horas trabalhadas: {dados.get('horas',0)}")
    y -= 16
    c.drawString(40, y, f"Valor da hora: {brl(float(dados.get('valor_hora',0) or 0))}")
    y -= 16
    c.drawString(40, y, f"Despesas extras: {brl(float(dados.get('despesas',0) or 0))}")
    y -= 16
    c.drawString(40, y, f"Margem de lucro: {dados.get('margem',0)}%")
    y -= 22

    # Totais
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, f"Custo Base: {dados.get('custo_base_fmt','')}")
    y -= 22
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, f"Preço Final: {dados.get('preco_final_fmt','')}")
    y -= 22

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Validade: {dados.get('validade',0)} dia(s)")

    # Rodapé
    c.setFont("Helvetica", 9)
    c.drawString(40, 30, "Gerado pelo Arte Preço Pro")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()


# -----------------------------
# Static (PWA)
# -----------------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    # garante que /static/manifest.json e /static/sw.js sejam servidos como arquivo mesmo
    return send_from_directory("static", filename)


@app.get("/")
def home():
    html = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Arte Preço Pro</title>

  <!-- PWA -->
  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4A6B3E">
  <link rel="icon" href="/static/icon-192.png">

  <style>
    body{font-family:Arial, sans-serif; background:#dce6d5; margin:0; padding:0;}
    .wrap{max-width:520px; margin:28px auto; padding:0 14px;}
    .card{background:#e8efe3; border-radius:16px; padding:18px; box-shadow:0 2px 10px rgba(0,0,0,.08);}
    h1{margin:0 0 12px; font-size:40px;}
    label{display:block; margin:10px 0 6px; font-weight:700;}
    input{width:100%; padding:14px; border-radius:12px; border:1px solid #c6d4be; font-size:18px; background:#fff;}
    .row{display:flex; gap:10px;}
    .row>div{flex:1;}
    button{width:100%; padding:16px; border-radius:12px; border:none; background:#4A6B3E; color:#fff; font-size:20px; font-weight:700; margin-top:14px;}
    .btn2{background:#5f7d51;}
    .muted{opacity:.8; font-size:13px;}
    .ok{background:#fff; border-radius:12px; padding:12px; margin-top:14px;}
    .hide{display:none;}
    .smallbtns{display:flex; gap:10px; margin-top:12px;}
    .smallbtns button{margin-top:0;}
    .gray{background:#6b6b6b;}
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Arte Preço Pro</h1>

    <!-- BLOCO ATIVAÇÃO -->
    <div id="boxAtivacao">
      <label>Ativação</label>
      <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
      <input id="chave" placeholder="Cole sua chave AP-...">
      <button onclick="ativar()">Ativar</button>
      <div id="msgAtivacao" class="ok hide"></div>
    </div>

    <!-- BLOCO APP -->
    <div id="boxApp" class="hide">

      <div class="ok">
        ✅ <b id="status"></b>
      </div>

      <label>Cliente (nome)</label>
      <input id="cliente_nome" placeholder="Ex: João da Silva">

      <label>Contato</label>
      <input id="cliente_contato" placeholder="Ex: (24) 99999-9999 / WhatsApp / Email">

      <label>Endereço</label>
      <input id="cliente_endereco" placeholder="Ex: Rua..., Bairro..., Cidade/UF">

      <label>Produto</label>
      <input id="produto" value="Logo">

      <label>Custo do Material (R$)</label>
      <input id="custo_material" value="10" inputmode="decimal">

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" value="4" inputmode="decimal">
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" value="30" inputmode="decimal">
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="despesas" value="2" inputmode="decimal">

      <label>Margem de Lucro (%)</label>
      <input id="margem" value="80" inputmode="decimal">

      <label>Validade (dias)</label>
      <input id="validade" value="7" inputmode="numeric">

      <button onclick="calcular()">Calcular</button>

      <div id="resultado" class="ok hide"></div>

      <div class="smallbtns">
        <button class="gray" onclick="sair()">Sair</button>
        <button class="btn2" onclick="revalidar()">Revalidar chave</button>
      </div>
    </div>

  </div>
</div>

<script>
  // PWA Service Worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
  }

  function show(el){el.classList.remove('hide');}
  function hide(el){el.classList.add('hide');}

  function getToken(){ return localStorage.getItem('AP_TOKEN') || ''; }
  function setToken(t){ localStorage.setItem('AP_TOKEN', t); }

  async function ativar(){
    const chave = document.getElementById('chave').value.trim();
    const msg = document.getElementById('msgAtivacao');
    hide(msg);

    if(!chave.startsWith('AP-')){
      msg.innerText = 'Chave inválida (precisa começar com AP-)';
      show(msg); return;
    }

    const r = await fetch('/api/ativar', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({chave})
    });

    const j = await r.json().catch(()=>({ok:false, msg:'Erro'}));
    msg.innerText = j.msg || 'Erro';
    show(msg);

    if(j.ok){
      setToken(chave);
      abrirApp(j.cliente || 'Ativado');
    }
  }

  function abrirApp(status){
    document.getElementById('status').innerText = 'Ativado para ' + status;
    hide(document.getElementById('boxAtivacao'));
    show(document.getElementById('boxApp'));
  }

  function sair(){
    // só sai da tela do app (não apaga licença)
    hide(document.getElementById('resultado'));
    window.scrollTo(0,0);
  }

  async function revalidar(){
    const chave = getToken();
    if(!chave){ location.reload(); return; }
    const r = await fetch('/api/ativar', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({chave})
    });
    const j = await r.json().catch(()=>({ok:false, msg:'Erro'}));
    if(j.ok) abrirApp(j.cliente || 'Ativado');
    else {
      localStorage.removeItem('AP_TOKEN');
      location.reload();
    }
  }

  function num(v){
    v = (v||'').toString().replace(',', '.');
    const x = parseFloat(v);
    return isNaN(x) ? 0 : x;
  }

  async function calcular(){
    const payload = {
      token: getToken(),
      cliente_nome: document.getElementById('cliente_nome').value.trim(),
      cliente_contato: document.getElementById('cliente_contato').value.trim(),
      cliente_endereco: document.getElementById('cliente_endereco').value.trim(),
      produto: document.getElementById('produto').value.trim(),
      custo_material: num(document.getElementById('custo_material').value),
      horas: num(document.getElementById('horas').value),
      valor_hora: num(document.getElementById('valor_hora').value),
      despesas: num(document.getElementById('despesas').value),
      margem: num(document.getElementById('margem').value),
      validade: parseInt(document.getElementById('validade').value || '0', 10) || 0
    };

    const r = await fetch('/api/calcular', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });

    const j = await r.json().catch(()=>({ok:false, msg:'Erro'}));
    const box = document.getElementById('resultado');

    if(!j.ok){
      box.innerHTML = '❌ ' + (j.msg || 'Erro ao calcular');
      show(box); return;
    }

    box.innerHTML = `
      <div><b>Cliente:</b> ${j.cliente_nome || '-'} </div>
      <div><b>Produto:</b> ${j.produto}</div>
      <div><b>Custo Base:</b> ${j.custo_base_fmt}</div>
      <div style="font-size:30px; font-weight:800; margin-top:6px;">
        Preço Final: ${j.preco_final_fmt}
      </div>
      <div>Validade: ${j.validade} dia(s)</div>
      <div style="margin-top:10px;">
        <a href="/api/pdf?token=${encodeURIComponent(payload.token)}&key=${encodeURIComponent(j.key_pdf)}"
           style="display:inline-block; padding:12px 14px; background:#4A6B3E; color:#fff; border-radius:10px; text-decoration:none; font-weight:700;">
           Baixar PDF
        </a>
      </div>
    `;
    show(box);
  }

  // Auto-login
  window.addEventListener('load', () => {
    const token = getToken();
    if(token){
      revalidar();
    }
  });
</script>
</body>
</html>
"""
    resp = make_response(html)
    # Ajuda PWA / evitar caches chatos de HTML
    resp.headers["Cache-Control"] = "no-store"
    return resp


# -----------------------------
# API
# -----------------------------
@app.post("/api/ativar")
def api_ativar():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    if not chave.startswith("AP-"):
        return jsonify(ok=False, msg="Chave inválida."), 400

    if validar_chave is None:
        # fallback (caso core não esteja disponível)
        return jsonify(ok=True, msg="Ativado (modo fallback).", cliente="ARTE_PECO_PRO")

    ok, msg = validar_chave(chave)
    if ok:
        # msg costuma vir tipo: "Ativado para ARTE_PECO_PRO"
        cliente = "ARTE_PECO_PRO"
        if "para" in msg:
            try:
                cliente = msg.split("para", 1)[1].strip()
            except Exception:
                pass
        return jsonify(ok=True, msg=msg, cliente=cliente)

    return jsonify(ok=False, msg=msg), 400


# Guardar PDFs temporários em memória simples (suficiente pro seu caso)
PDF_CACHE = {}  # key -> dict(dados, expiração não implementada)


@app.post("/api/calcular")
def api_calcular():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    # Validar token/licença
    if validar_chave is not None:
        ok, msg = validar_chave(token)
        if not ok:
            return jsonify(ok=False, msg="Chave inválida/expirada. Revalide."), 401

    produto = (data.get("produto") or "").strip() or "Serviço"
    custo_material = float(data.get("custo_material") or 0)
    horas = float(data.get("horas") or 0)
    valor_hora = float(data.get("valor_hora") or 0)
    despesas = float(data.get("despesas") or 0)
    margem = float(data.get("margem") or 0)
    validade = int(data.get("validade") or 0)

    cliente_nome = (data.get("cliente_nome") or "").strip()
    cliente_contato = (data.get("cliente_contato") or "").strip()
    cliente_endereco = (data.get("cliente_endereco") or "").strip()

    custo_base, preco_final = calcular_preco_simples(
        custo_material, horas, valor_hora, despesas, margem
    )

    custo_base_fmt = brl(custo_base)
    preco_final_fmt = brl(preco_final)

    # chave para baixar pdf
    key_pdf = f"{datetime.now().timestamp()}-{abs(hash(produto))}"

    PDF_CACHE[key_pdf] = {
        "cliente_nome": cliente_nome,
        "cliente_contato": cliente_contato,
        "cliente_endereco": cliente_endereco,
        "produto": produto,
        "custo_material": custo_material,
        "horas": horas,
        "valor_hora": valor_hora,
        "despesas": despesas,
        "margem": margem,
        "validade": validade,
        "custo_base_fmt": custo_base_fmt,
        "preco_final_fmt": preco_final_fmt,
    }

    return jsonify(
        ok=True,
        cliente_nome=cliente_nome,
        produto=produto,
        custo_base_fmt=custo_base_fmt,
        preco_final_fmt=preco_final_fmt,
        validade=validade,
        key_pdf=key_pdf,
    )


@app.get("/api/pdf")
def api_pdf():
    token = (request.args.get("token") or "").strip()
    key = (request.args.get("key") or "").strip()

    if validar_chave is not None:
        ok, _msg = validar_chave(token)
        if not ok:
            return "Chave inválida/expirada.", 401

    dados = PDF_CACHE.get(key)
    if not dados:
        return "PDF não encontrado (gere novamente).", 404

    pdf_bytes = gerar_pdf_orcamento(dados)
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "attachment; filename=orcamento_arte_preco_pro.pdf"
    return resp


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
