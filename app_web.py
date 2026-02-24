import os
import io
import json
from datetime import datetime

from flask import Flask, request, Response, send_file

# ============================================================
# Helpers
# ============================================================

def money_br(v):
    try:
        v = float(v)
    except Exception:
        v = 0.0
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def to_float(x):
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        x = str(x).strip().replace(".", "").replace(",", ".")
        return float(x) if x else 0.0
    except Exception:
        return 0.0

def to_int(x):
    try:
        return int(float(str(x).strip().replace(",", ".")))
    except Exception:
        return 0

def calc_preco_robusto(**kw):
    """
    Aceita chaves diferentes e evita erro de keyword inesperada.
    Retorna (custo_base, preco_final)
    """
    custo_material = to_float(kw.get("custo_material", kw.get("material", 0)))
    horas = to_float(kw.get("horas", kw.get("horas_trabalhadas", 0)))
    valor_hora = to_float(kw.get("valor_hora", kw.get("hora", 0)))
    despesas = to_float(kw.get("despesas", kw.get("despesas_extras", 0)))
    margem_pct = to_float(kw.get("margem_pct", kw.get("margem", 0)))

    custo_base = custo_material + (horas * valor_hora) + despesas
    preco_final = custo_base * (1.0 + (margem_pct / 100.0))
    return round(custo_base, 2), round(preco_final, 2)

def validar_licenca(key: str):
    """
    Validação via core.license_core se existir.
    Se não existir (ou der erro), faz fallback mínimo.
    """
    key = (key or "").strip()
    if not key:
        return (False, "Chave vazia.")

    # tenta usar o seu core.license_core
    try:
        from core.license_core import validar_chave  # seu projeto já tem isso
        # Alguns projetos mudam assinatura. A sua agora está aceitando 1 argumento.
        ok, msg = validar_chave(key)
        return (bool(ok), str(msg))
    except Exception:
        # fallback: aceita formato AP-...
        if key.startswith("AP-") and len(key) > 20:
            return (True, "Ativado.")
        return (False, "Chave inválida.")

# ============================================================
# App
# ============================================================

app = Flask(__name__)

HTML_INDEX = r"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Arte Preço Pro</title>

  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4E633E">
  <link rel="icon" href="/static/icon-192.png">

  <style>
    :root {
      --bg: #DCE5D5;
      --card: #E9F0E5;
      --btn: #4E633E;
      --btn2: #3f5233;
      --txt: #1a1a1a;
      --muted: #58635a;
      --line: rgba(0,0,0,.12);
      --white: #fff;
    }
    body { margin:0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--txt); }
    .wrap { max-width: 720px; margin: 0 auto; padding: 18px; }
    .card { background: var(--card); border-radius: 16px; padding: 16px; box-shadow: 0 2px 10px rgba(0,0,0,.06); border: 1px solid var(--line); }
    h1 { margin: 8px 0 14px; font-size: 34px; }
    h2 { margin: 14px 0 10px; font-size: 18px; }
    label { display:block; font-weight: 700; margin: 10px 0 6px; }
    input { width: 100%; box-sizing: border-box; padding: 14px; border-radius: 10px; border: 1px solid var(--line); font-size: 16px; background: var(--white); }
    .row { display:flex; gap: 10px; }
    .row > div { flex: 1; }
    .btn { width:100%; background: var(--btn); color: white; font-weight: 700; border:0; padding: 16px; border-radius: 12px; font-size: 18px; cursor:pointer; }
    .btn:active { transform: scale(.99); }
    .btn2 { background: #6b6b6b; }
    .btn3 { background: var(--btn2); }
    .msg { margin-top: 10px; padding: 12px; border-radius: 10px; border: 1px solid var(--line); background: rgba(255,255,255,.6); }
    .ok { border-color: rgba(0,128,0,.25); }
    .err { border-color: rgba(220,0,0,.25); }
    .small { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .big { font-size: 36px; font-weight: 800; margin-top: 8px; }
    .kbd { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; padding: 2px 6px; background: rgba(0,0,0,.08); border-radius: 6px; }
  </style>
</head>

<body>
  <div class="wrap">
    <div class="card" id="cardAuth" style="display:none;">
      <h1>Arte Preço Pro</h1>
      <h2>Ativação</h2>
      <div class="small">Cole a chave <span class="kbd">AP-...</span> (uma vez). O app lembra automaticamente.</div>
      <label>Chave</label>
      <input id="inpKey" placeholder="Cole sua chave AP-..." />
      <div style="height:12px"></div>
      <button class="btn" onclick="ativar()">Ativar</button>
      <div id="authMsg" class="msg" style="display:none;"></div>
    </div>

    <div class="card" id="cardApp" style="display:none;">
      <h1>Arte Preço Pro</h1>
      <div id="statusBox" class="msg ok" style="display:none;"></div>

      <h2>Dados da Empresa</h2>
      <label>Nome</label>
      <input id="emp_nome" placeholder="Ex: PJ Studio Design" />
      <div class="row">
        <div>
          <label>Telefone</label>
          <input id="emp_tel" placeholder="Ex: (24) 98119-6037" />
        </div>
        <div>
          <label>E-mail</label>
          <input id="emp_email" placeholder="Ex: loj...@gmail.com" />
        </div>
      </div>
      <label>Endereço</label>
      <input id="emp_end" placeholder="Ex: Rua ..., 505" />

      <h2>Dados do Cliente</h2>
      <label>Nome</label>
      <input id="cli_nome" placeholder="Ex: Nome do Cliente" />
      <div class="row">
        <div>
          <label>Telefone</label>
          <input id="cli_tel" placeholder="Ex: (22) 9...." />
        </div>
        <div>
          <label>E-mail</label>
          <input id="cli_email" placeholder="Ex: cliente@email.com" />
        </div>
      </div>
      <label>Endereço</label>
      <input id="cli_end" placeholder="Ex: Rua ..., nº ..." />

      <h2>Orçamento</h2>
      <label>Produto/Serviço</label>
      <input id="produto" placeholder="Ex: Logo" />

      <label>Custo do Material (R$)</label>
      <input id="custo_material" placeholder="Ex: 10" inputmode="decimal" />

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" placeholder="Ex: 4" inputmode="decimal" />
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" placeholder="Ex: 30" inputmode="decimal" />
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="despesas" placeholder="Ex: 2" inputmode="decimal" />

      <label>Margem de Lucro (%)</label>
      <input id="margem" placeholder="Ex: 80" inputmode="decimal" />

      <label>Validade (dias)</label>
      <input id="validade" placeholder="Ex: 7" inputmode="numeric" />

      <div style="height:14px"></div>
      <button class="btn" onclick="calcular()">Calcular</button>

      <div id="resBox" class="msg" style="display:none; margin-top:14px;"></div>

      <div style="height:10px"></div>
      <button class="btn btn3" onclick="gerarPDF()">Gerar PDF</button>

      <div style="height:10px"></div>
      <div class="row">
        <div><button class="btn btn2" onclick="sair()">Sair</button></div>
        <div><button class="btn btn3" onclick="revalidar()">Revalidar chave</button></div>
      </div>

      <div class="small" style="margin-top:10px;">
        Se aparecer 500 ou travar, geralmente é cache antigo. Faça: Chrome → Configurações → Privacidade → Limpar dados → e abra de novo.
      </div>
    </div>
  </div>

<script>
  const LS_KEY = "artepreco_key";
  const LS_EMP = "artepreco_empresa";
  const LS_CLI = "artepreco_cliente";

  function setMsg(id, text, cls) {
    const el = document.getElementById(id);
    el.style.display = "block";
    el.className = "msg " + (cls || "");
    el.innerText = text;
  }

  function showAuth() {
    document.getElementById("cardAuth").style.display = "block";
    document.getElementById("cardApp").style.display = "none";
  }

  function showApp(okText) {
    document.getElementById("cardAuth").style.display = "none";
    document.getElementById("cardApp").style.display = "block";
    if (okText) {
      const sb = document.getElementById("statusBox");
      sb.style.display = "block";
      sb.className = "msg ok";
      sb.innerText = "✅ " + okText;
    }
  }

  function getKey() {
    return (localStorage.getItem(LS_KEY) || "").trim();
  }

  function saveEmpresaCliente() {
    const empresa = {
      nome: document.getElementById("emp_nome").value || "",
      tel: document.getElementById("emp_tel").value || "",
      email: document.getElementById("emp_email").value || "",
      end: document.getElementById("emp_end").value || ""
    };
    const cliente = {
      nome: document.getElementById("cli_nome").value || "",
      tel: document.getElementById("cli_tel").value || "",
      email: document.getElementById("cli_email").value || "",
      end: document.getElementById("cli_end").value || ""
    };
    localStorage.setItem(LS_EMP, JSON.stringify(empresa));
    localStorage.setItem(LS_CLI, JSON.stringify(cliente));
    return {empresa, cliente};
  }

  function loadEmpresaCliente() {
    try {
      const emp = JSON.parse(localStorage.getItem(LS_EMP) || "{}");
      const cli = JSON.parse(localStorage.getItem(LS_CLI) || "{}");
      document.getElementById("emp_nome").value = emp.nome || "";
      document.getElementById("emp_tel").value = emp.tel || "";
      document.getElementById("emp_email").value = emp.email || "";
      document.getElementById("emp_end").value = emp.end || "";
      document.getElementById("cli_nome").value = cli.nome || "";
      document.getElementById("cli_tel").value = cli.tel || "";
      document.getElementById("cli_email").value = cli.email || "";
      document.getElementById("cli_end").value = cli.end || "";
    } catch(e) {}
  }

  async function ativar() {
    const key = (document.getElementById("inpKey").value || "").trim();
    if (!key) { setMsg("authMsg", "Cole a chave.", "err"); return; }

    const r = await fetch("/api/activate", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({key})
    });

    const txt = await r.text();
    if (r.ok) {
      localStorage.setItem(LS_KEY, key);
      loadEmpresaCliente();
      showApp(txt);
    } else {
      setMsg("authMsg", txt, "err");
    }
  }

  async function revalidar() {
    const key = getKey();
    if (!key) { showAuth(); return; }
    const r = await fetch("/api/activate", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({key})
    });
    const txt = await r.text();
    if (r.ok) {
      showApp(txt);
    } else {
      localStorage.removeItem(LS_KEY);
      showAuth();
      setMsg("authMsg", txt, "err");
    }
  }

  function sair() {
    // mantém empresa/cliente salvos, mas remove a chave
    localStorage.removeItem(LS_KEY);
    document.getElementById("inpKey").value = "";
    document.getElementById("resBox").style.display = "none";
    showAuth();
  }

  function collectCalc() {
    const produto = document.getElementById("produto").value || "";
    const custo_material = document.getElementById("custo_material").value || "";
    const horas = document.getElementById("horas").value || "";
    const valor_hora = document.getElementById("valor_hora").value || "";
    const despesas = document.getElementById("despesas").value || "";
    const margem = document.getElementById("margem").value || "";
    const validade = document.getElementById("validade").value || "";

    return {
      produto,
      custo_material,
      horas,
      valor_hora,
      despesas,
      margem,
      validade
    };
  }

  async function calcular() {
    const key = getKey();
    if (!key) { showAuth(); return; }

    const dados = collectCalc();
    const {empresa, cliente} = saveEmpresaCliente();

    const payload = {
      key,
      empresa,
      cliente,
      ...dados
    };

    const r = await fetch("/api/calc", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });

    const txt = await r.text();
    if (!r.ok) {
      setMsg("resBox", txt, "err");
      return;
    }

    const data = JSON.parse(txt);
    const html = [
      `Produto: ${data.produto}`,
      `Custo Base: ${data.custo_base_fmt}`,
      `<div class="big">Preço Final: ${data.preco_final_fmt}</div>`,
      `Validade: ${data.validade} dia(s)`
    ].join("<br>");

    const el = document.getElementById("resBox");
    el.style.display = "block";
    el.className = "msg ok";
    el.innerHTML = html;
  }

  async function gerarPDF() {
    const key = getKey();
    if (!key) { showAuth(); return; }

    const dados = collectCalc();
    const {empresa, cliente} = saveEmpresaCliente();

    const payload = {
      key,
      empresa,
      cliente,
      ...dados
    };

    const r = await fetch("/api/pdf", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });

    if (!r.ok) {
      const txt = await r.text();
      alert(txt);
      return;
    }

    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    window.location.href = url;
  }

  // boot
  (async function(){
    if ("serviceWorker" in navigator) {
      try { await navigator.serviceWorker.register("/static/sw.js"); } catch(e) {}
    }

    const key = getKey();
    if (!key) {
      showAuth();
      return;
    }
    loadEmpresaCliente();
    await revalidar();
  })();
</script>
</body>
</html>
"""

# ============================================================
# Routes
# ============================================================

@app.get("/")
def index():
    return Response(HTML_INDEX, mimetype="text/html")

@app.get("/health")
def health():
    return Response("ok", mimetype="text/plain")

@app.post("/api/activate")
def api_activate():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()
    ok, msg = validar_licenca(key)
    if ok:
        return Response(msg, mimetype="text/plain")
    return Response(msg, status=403, mimetype="text/plain")

@app.post("/api/calc")
def api_calc():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()
    ok, msg = validar_licenca(key)
    if not ok:
        return Response(msg, status=403, mimetype="text/plain")

    try:
        produto = (payload.get("produto") or "").strip() or "Serviço"
        custo_material = to_float(payload.get("custo_material"))
        horas = to_float(payload.get("horas"))
        valor_hora = to_float(payload.get("valor_hora"))
        despesas = to_float(payload.get("despesas"))
        margem = to_float(payload.get("margem"))
        validade = to_int(payload.get("validade"))

        custo_base, preco_final = calc_preco_robusto(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas=despesas,
            margem_pct=margem,
        )

        data = {
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "custo_base_fmt": money_br(custo_base),
            "preco_final_fmt": money_br(preco_final),
            "validade": validade
        }
        return Response(json.dumps(data, ensure_ascii=False), mimetype="application/json")
    except Exception as e:
        return Response(f"Erro ao calcular: {e}", status=500, mimetype="text/plain")

@app.post("/api/pdf")
def api_pdf():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()
    ok, msg = validar_licenca(key)
    if not ok:
        return Response(msg, status=403, mimetype="text/plain")

    try:
        empresa = payload.get("empresa") or {}
        cliente = payload.get("cliente") or {}

        produto = (payload.get("produto") or "").strip() or "Serviço"
        custo_material = to_float(payload.get("custo_material"))
        horas = to_float(payload.get("horas"))
        valor_hora = to_float(payload.get("valor_hora"))
        despesas = to_float(payload.get("despesas"))
        margem = to_float(payload.get("margem"))
        validade = to_int(payload.get("validade"))

        custo_base, preco_final = calc_preco_robusto(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas=despesas,
            margem_pct=margem,
        )

        # Gera PDF
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buff = io.BytesIO()
        c = canvas.Canvas(buff, pagesize=A4)
        w, h = A4

        y = h - 50
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, y, "ORÇAMENTO - ARTE PREÇO PRO")

        y -= 30
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        y -= 25
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DADOS DA EMPRESA")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Nome: {empresa.get('nome','')}")
        y -= 14
        c.drawString(40, y, f"Telefone: {empresa.get('tel','')}")
        y -= 14
        c.drawString(40, y, f"E-mail: {empresa.get('email','')}")
        y -= 14
        c.drawString(40, y, f"Endereço: {empresa.get('end','')}")

        y -= 22
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DADOS DO CLIENTE")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Nome: {cliente.get('nome','')}")
        y -= 14
        c.drawString(40, y, f"Telefone: {cliente.get('tel','')}")
        y -= 14
        c.drawString(40, y, f"E-mail: {cliente.get('email','')}")
        y -= 14
        c.drawString(40, y, f"Endereço: {cliente.get('end','')}")

        y -= 22
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DETALHES DO SERVIÇO")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Produto/Serviço: {produto}")
        y -= 14
        c.drawString(40, y, f"Custo material: {money_br(custo_material)}")
        y -= 14
        c.drawString(40, y, f"Trabalho: {horas}h x {money_br(valor_hora)}")
        y -= 14
        c.drawString(40, y, f"Despesas extras: {money_br(despesas)}")

        # ✅ MARGEM NÃO APARECE NO PDF (REMOVIDA)

        y -= 22
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"Custo Base: {money_br(custo_base)}")
        y -= 22
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, y, f"Preço Final: {money_br(preco_final)}")

        y -= 22
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Validade: {validade} dia(s)")

        c.showPage()
        c.save()

        buff.seek(0)
        return send_file(
            buff,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="orcamento_arte_preco_pro.pdf",
        )

    except Exception as e:
        return Response(f"Erro ao gerar PDF: {e}", status=500, mimetype="text/plain")


# ============================================================
# Vercel entrypoint
# ============================================================
# Para Vercel Python Runtime: exporta "app"
# (o Vercel detecta o Flask app automaticamente)
