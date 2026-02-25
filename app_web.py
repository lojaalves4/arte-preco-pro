import os
import json
import base64
import time
from datetime import datetime

from flask import Flask, request, redirect, make_response

# ==========================================
#  CONFIG
# ==========================================
APP_NAME = "Arte Preço Pro"

# Cookies
COOKIE_KEY = "ap_lic_key"
COOKIE_COMPANY = "ap_company_data"

# (Opcional) para identificar o navegador/instalação
DEVICE_KEY = "ap_device_id"

# Segredo do servidor (Vercel ENV)
APP_SECRET = os.environ.get("APP_SECRET", "ARTEPRECO_SUPER_SEGREDO_2026")

# ==========================================
#  APP
#  IMPORTANTE: static_folder/static_url_path
#  para servir /static/* corretamente e o PWABuilder encontrar manifest/sw/icons
# ==========================================
app = Flask(__name__, static_folder="static", static_url_path="/static")


# ==========================================
#  HELPERS
# ==========================================
def _now_fmt():
    try:
        return datetime.now().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _get_cookie(req, name):
    try:
        return req.cookies.get(name, "")
    except Exception:
        return ""


def _set_cookie(resp, name, value, max_age_days=365):
    try:
        resp.set_cookie(
            name,
            value,
            max_age=max_age_days * 24 * 60 * 60,
            samesite="Lax",
            secure=True,
            httponly=False,
        )
    except Exception:
        pass
    return resp


def _clear_cookie(resp, name):
    try:
        resp.set_cookie(name, "", expires=0)
    except Exception:
        pass
    return resp


def _safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(".", "").replace(",", ".")
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def _safe_int(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, int):
            return v
        s = str(v).strip()
        if s == "":
            return default
        return int(float(s.replace(",", ".")))
    except Exception:
        return default


def _fmt_money(v):
    try:
        vv = float(v)
    except Exception:
        vv = 0.0
    # pt-BR simples
    s = f"{vv:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(payload_b64: str) -> str:
    # assinatura simples (não-cripto forte) para manter compatível com seu projeto
    # se você já tinha outro método de assinatura, me manda que eu ajusto.
    import hmac
    import hashlib

    return _b64url(hmac.new(APP_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest())


def gerar_chave(exp_ts: int) -> str:
    payload = {"c": "ARTE_PECO_PRO", "exp": int(exp_ts)}
    payload_b = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url(payload_b)
    sig = _sign(payload_b64)
    return f"AP-{payload_b64}.{sig}"


def validar_chave(token: str) -> (bool, str):
    try:
        if not token or not token.startswith("AP-"):
            return False, "Formato inválido"
        body = token[3:]
        if "." not in body:
            return False, "Formato inválido"
        payload_b64, sig = body.split(".", 1)
        if _sign(payload_b64) != sig:
            return False, "Assinatura inválida"

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        if exp <= 0:
            return False, "Sem expiração"
        if int(time.time()) > exp:
            return False, "Chave expirada"
        return True, "OK"
    except Exception:
        return False, "Erro ao validar"


def _get_device_id(req):
    did = _get_cookie(req, DEVICE_KEY)
    if did:
        return did
    # cria um id simples
    did = _b64url(os.urandom(12))
    return did


def calcular_preco(custo_material, horas, valor_hora, despesas_extras, margem_pct):
    """
    cálculo padrão:
      custo_base = custo_material + (horas * valor_hora) + despesas_extras
      preco_final = custo_base * (1 + margem_pct/100)
    """
    custo_base = float(custo_material) + (float(horas) * float(valor_hora)) + float(despesas_extras)
    preco_final = custo_base * (1.0 + float(margem_pct) / 100.0)
    return custo_base, preco_final


# ==========================================
#  HTML
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="manifest" href="/static/manifest.json" />
  <meta name="theme-color" content="#4E633E" />
  <link rel="icon" href="/static/icon-192.png" />
  <link rel="apple-touch-icon" href="/static/icon-192.png" />
  <title>Arte Preço Pro</title>
  <style>
    :root{
      --bg: #DCE5D5;
      --card: #E9EFE5;
      --accent: #4E633E;
      --accent2: #38512D;
      --text: #111;
      --muted: #3a3a3a;
      --border: #b8c5b1;
      --white: #fff;
    }
    body{ font-family: Arial, Helvetica, sans-serif; background: var(--bg); margin:0; padding:16px; color: var(--text); }
    .wrap{ max-width: 560px; margin: 0 auto; }
    .card{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 14px; box-shadow: 0 2px 6px rgba(0,0,0,.06); }
    h1{ margin:0 0 10px 0; font-size: 34px; letter-spacing: -0.5px; }
    h2{ margin:14px 0 10px 0; font-size: 18px; }
    label{ display:block; font-weight: 700; margin: 10px 0 6px; }
    input, textarea{ width: 100%; padding: 12px; font-size: 16px; border-radius: 10px; border: 1px solid var(--border); background: var(--white); box-sizing: border-box; }
    .row{ display:flex; gap: 12px; }
    .row > div{ flex:1; }
    .btn{ background: var(--accent); color: #fff; font-weight: 800; border:0; border-radius: 12px; padding: 14px 14px; font-size: 18px; width: 100%; cursor:pointer; }
    .btn:hover{ background: var(--accent2); }
    .btn2{ background: #3a3a3a; color:#fff; font-weight:800; border:0; border-radius: 12px; padding: 12px 14px; font-size: 16px; width: 100%; cursor:pointer; }
    .btn3{ background: var(--accent); color:#fff; font-weight:800; border:0; border-radius: 12px; padding: 12px 14px; font-size: 16px; width: 100%; cursor:pointer; }
    .mt{ margin-top: 12px; }
    .big{ font-size: 36px; font-weight: 900; margin: 6px 0 2px; }
    .muted{ color: var(--muted); }
    .warn{ background:#fff7e6; border:1px solid #ffd9a8; padding:10px; border-radius:12px; margin-top:10px; }
    .ok{ background:#e9fff0; border:1px solid #b8f0c7; padding:10px; border-radius:12px; margin-top:10px; }
    .mini{ font-size: 12px; color: var(--muted); }
    .footer{ margin-top: 12px; display:flex; gap: 10px; }
    .footer .btn2, .footer .btn3{ width: 50%; }
    .hide{ display:none; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="card" id="box-ativacao">
    <h1>Ativação do Arte Preço Pro</h1>
    <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
    <label>Chave</label>
    <input id="licKey" placeholder="Cole sua chave AP-..." />
    <button class="btn mt" onclick="ativar()">Ativar</button>
    <div id="msgAtivar" class="warn hide"></div>
  </div>

  <div class="card hide" id="box-app">
    <h1>Arte Preço Pro</h1>
    <div class="muted">Preencha os dados e gere o orçamento em PDF.</div>

    <h2>Dados da Empresa</h2>
    <label>Nome</label>
    <input id="emp_nome" placeholder="Ex: PJ Studio Design" />
    <label>Telefone</label>
    <input id="emp_tel" placeholder="Ex: (24) 99999-9999" />
    <label>E-mail</label>
    <input id="emp_email" placeholder="Ex: contato@empresa.com" />
    <label>Endereço</label>
    <input id="emp_end" placeholder="Ex: Rua..., nº..., Cidade" />

    <h2>Dados do Cliente</h2>
    <label>Nome</label>
    <input id="cli_nome" placeholder="Ex: Nome do cliente" />
    <label>Telefone</label>
    <input id="cli_tel" placeholder="Ex: (24) 99999-9999" />
    <label>E-mail</label>
    <input id="cli_email" placeholder="Ex: cliente@email.com" />
    <label>Endereço</label>
    <input id="cli_end" placeholder="Ex: Rua..., nº..., Cidade" />

    <h2>Detalhes do Serviço</h2>
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

    <button class="btn mt" onclick="calcular()">Calcular</button>

    <div id="resultado" class="ok hide">
      <div><b>Produto:</b> <span id="r_prod"></span></div>
      <div><b>Custo Base:</b> R$ <span id="r_base"></span></div>
      <div class="big">Preço Final: R$ <span id="r_final"></span></div>
      <div class="muted">Validade: <span id="r_val"></span> dia(s)</div>
    </div>

    <button class="btn3 mt hide" id="btnPdf" onclick="gerarPDF()">Gerar PDF</button>

    <div class="footer mt">
      <button class="btn2" onclick="sair()">Sair</button>
      <button class="btn3" onclick="limparDados()">Limpar dados</button>
    </div>

    <div class="mini mt">
      Dica: Para instalar, use o menu do Chrome → “Adicionar à tela inicial”.
    </div>
  </div>
</div>

<script>
  // PWA: registra o Service Worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/static/sw.js").catch(() => {});
    });
  }

  function show(el){ el.classList.remove("hide"); }
  function hide(el){ el.classList.add("hide"); }

  function saveLocal(key, obj){
    try{ localStorage.setItem(key, JSON.stringify(obj)); }catch(e){}
  }
  function loadLocal(key){
    try{
      const s = localStorage.getItem(key);
      if(!s) return null;
      return JSON.parse(s);
    }catch(e){ return null; }
  }
  function delLocal(key){
    try{ localStorage.removeItem(key); }catch(e){}
  }

  function setFields(prefix, data){
    if(!data) return;
    Object.keys(data).forEach(k=>{
      const el = document.getElementById(prefix + "_" + k);
      if(el) el.value = data[k] || "";
    });
  }

  function getFields(prefix, keys){
    const out = {};
    keys.forEach(k=>{
      const el = document.getElementById(prefix + "_" + k);
      out[k] = el ? (el.value || "") : "";
    });
    return out;
  }

  async function postJSON(url, payload){
    const res = await fetch(url, {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });
    return { ok: res.ok, status: res.status, data: await res.json().catch(()=>({})) };
  }

  async function ativar(){
    const key = document.getElementById("licKey").value.trim();
    const box = document.getElementById("msgAtivar");
    hide(box);

    if(!key){
      box.textContent = "Cole a chave AP-... para ativar.";
      show(box);
      return;
    }

    const resp = await postJSON("/api/ativar", { key });
    if(!resp.ok || !resp.data || !resp.data.ok){
      box.textContent = (resp.data && resp.data.msg) ? resp.data.msg : "Falha ao ativar.";
      show(box);
      return;
    }

    // salva no localStorage para não pedir sempre
    saveLocal("ap_key", { key });

    // abre app
    hide(document.getElementById("box-ativacao"));
    show(document.getElementById("box-app"));
    carregarPreferencias();
  }

  function carregarPreferencias(){
    const emp = loadLocal("ap_emp");
    const cli = loadLocal("ap_cli");
    const last = loadLocal("ap_last");

    setFields("emp", emp);
    setFields("cli", cli);

    if(last){
      const map = {
        produto: "produto",
        custo_material: "custo_material",
        horas: "horas",
        valor_hora: "valor_hora",
        despesas: "despesas",
        margem: "margem",
        validade: "validade",
      };
      Object.keys(map).forEach(k=>{
        const el = document.getElementById(map[k]);
        if(el && last[k] !== undefined) el.value = last[k];
      });
    }
  }

  function persistirPreferencias(){
    saveLocal("ap_emp", getFields("emp", ["nome","tel","email","end"]));
    saveLocal("ap_cli", getFields("cli", ["nome","tel","email","end"]));
    saveLocal("ap_last", {
      produto: document.getElementById("produto").value,
      custo_material: document.getElementById("custo_material").value,
      horas: document.getElementById("horas").value,
      valor_hora: document.getElementById("valor_hora").value,
      despesas: document.getElementById("despesas").value,
      margem: document.getElementById("margem").value,
      validade: document.getElementById("validade").value,
    });
  }

  async function calcular(){
    persistirPreferencias();

    const payload = {
      produto: document.getElementById("produto").value.trim(),
      custo_material: document.getElementById("custo_material").value,
      horas: document.getElementById("horas").value,
      valor_hora: document.getElementById("valor_hora").value,
      despesas: document.getElementById("despesas").value,
      margem: document.getElementById("margem").value,
      validade: document.getElementById("validade").value,
    };

    const resp = await postJSON("/api/calcular", payload);
    if(!resp.ok || !resp.data || !resp.data.ok){
      alert((resp.data && resp.data.msg) ? resp.data.msg : "Erro ao calcular.");
      return;
    }

    document.getElementById("r_prod").textContent = resp.data.produto || "";
    document.getElementById("r_base").textContent = resp.data.custo_base_fmt || "0,00";
    document.getElementById("r_final").textContent = resp.data.preco_final_fmt || "0,00";
    document.getElementById("r_val").textContent = resp.data.validade || "0";

    show(document.getElementById("resultado"));
    show(document.getElementById("btnPdf"));
  }

  async function gerarPDF(){
    persistirPreferencias();

    const payload = {
      empresa: getFields("emp", ["nome","tel","email","end"]),
      cliente: getFields("cli", ["nome","tel","email","end"]),
      produto: document.getElementById("produto").value.trim(),
      custo_material: document.getElementById("custo_material").value,
      horas: document.getElementById("horas").value,
      valor_hora: document.getElementById("valor_hora").value,
      despesas: document.getElementById("despesas").value,
      // margem NÃO vai aparecer no PDF (você pediu remover)
      margem: document.getElementById("margem").value,
      validade: document.getElementById("validade").value,
    };

    const res = await fetch("/api/pdf", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });

    if(!res.ok){
      alert("Falha ao gerar PDF.");
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
  }

  function limparDados(){
    if(!confirm("Deseja limpar dados salvos (empresa/cliente/orçamento)?")) return;
    delLocal("ap_emp");
    delLocal("ap_cli");
    delLocal("ap_last");
    // não apaga a chave
    alert("Dados limpos.");
  }

  function sair(){
    // volta para tela de ativação (mantém chave salva)
    show(document.getElementById("box-ativacao"));
    hide(document.getElementById("box-app"));
  }

  // auto-ativar se já tiver chave salva
  (function(){
    const k = loadLocal("ap_key");
    if(k && k.key){
      document.getElementById("licKey").value = k.key;
      ativar();
    }
  })();
</script>
</body>
</html>
"""

# ==========================================
#  ROUTES
# ==========================================
@app.get("/")
def home():
    return HTML


@app.post("/api/ativar")
def api_ativar():
    try:
        data = request.get_json(force=True, silent=True) or {}
        key = (data.get("key") or "").strip()

        ok, msg = validar_chave(key)
        if not ok:
            return {"ok": False, "msg": msg}, 200

        # cria/garante device_id
        did = _get_cookie(request, DEVICE_KEY) or _get_device_id(request)

        resp = make_response({"ok": True, "msg": "Ativado"})
        resp = _set_cookie(resp, DEVICE_KEY, did, 3650)
        resp = _set_cookie(resp, COOKIE_KEY, key, 3650)
        return resp
    except Exception:
        return {"ok": False, "msg": "Erro interno"}, 200


@app.post("/api/calcular")
def api_calcular():
    try:
        # valida se tem chave no cookie/local (app manda pela ativação)
        lic = _get_cookie(request, COOKIE_KEY)
        if not lic:
            return {"ok": False, "msg": "Chave não encontrada. Ative novamente."}, 200

        ok, msg = validar_chave(lic)
        if not ok:
            return {"ok": False, "msg": f"Chave inválida: {msg}"}, 200

        data = request.get_json(force=True, silent=True) or {}

        produto = (data.get("produto") or "").strip()
        custo_material = _safe_float(data.get("custo_material"), 0.0)
        horas = _safe_float(data.get("horas"), 0.0)
        valor_hora = _safe_float(data.get("valor_hora"), 0.0)
        despesas = _safe_float(data.get("despesas"), 0.0)
        margem = _safe_float(data.get("margem"), 0.0)
        validade = _safe_int(data.get("validade"), 0)

        if not produto:
            produto = "Serviço"

        custo_base, preco_final = calcular_preco(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas_extras=despesas,
            margem_pct=margem,
        )

        return {
            "ok": True,
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "custo_base_fmt": _fmt_money(custo_base),
            "preco_final_fmt": _fmt_money(preco_final),
            "validade": validade,
        }, 200
    except TypeError as e:
        # quando algum argumento muda (proteção)
        return {"ok": False, "msg": f"Erro de parâmetros no cálculo: {e}"}, 200
    except Exception:
        return {"ok": False, "msg": "Erro interno ao calcular"}, 200


@app.post("/api/pdf")
def api_pdf():
    """
    Gera um PDF simples em HTML->PDF via navegador (blob).
    Aqui retornamos um PDF básico (bytes) para download/abertura.
    """
    try:
        lic = _get_cookie(request, COOKIE_KEY)
        if not lic:
            return {"ok": False, "msg": "Chave não encontrada. Ative novamente."}, 200

        ok, msg = validar_chave(lic)
        if not ok:
            return {"ok": False, "msg": f"Chave inválida: {msg}"}, 200

        data = request.get_json(force=True, silent=True) or {}

        empresa = data.get("empresa") or {}
        cliente = data.get("cliente") or {}

        produto = (data.get("produto") or "").strip() or "Serviço"
        custo_material = _safe_float(data.get("custo_material"), 0.0)
        horas = _safe_float(data.get("horas"), 0.0)
        valor_hora = _safe_float(data.get("valor_hora"), 0.0)
        despesas = _safe_float(data.get("despesas"), 0.0)
        margem = _safe_float(data.get("margem"), 0.0)
        validade = _safe_int(data.get("validade"), 0)

        custo_base, preco_final = calcular_preco(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas_extras=despesas,
            margem_pct=margem,
        )

        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # IMPORTANTE: você pediu REMOVER a margem do PDF.
        # Então NÃO mostramos margem no PDF.
        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

        html_pdf = f"""
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: Arial, Helvetica, sans-serif; }}
            h1 {{ margin:0 0 10px 0; }}
            .sec {{ margin-top: 12px; }}
            .big {{ font-size: 28px; font-weight: 900; margin-top: 10px; }}
            .muted {{ color:#444; }}
          </style>
        </head>
        <body>
          <h1>ORÇAMENTO - ARTE PREÇO PRO</h1>
          <div class="muted">Data: {_now_fmt()}</div>

          <div class="sec">
            <h3>DADOS DA EMPRESA</h3>
            <div>Nome: {empresa.get("nome","")}</div>
            <div>Telefone: {empresa.get("tel","")}</div>
            <div>E-mail: {empresa.get("email","")}</div>
            <div>Endereço: {empresa.get("end","")}</div>
          </div>

          <div class="sec">
            <h3>DADOS DO CLIENTE</h3>
            <div>Nome: {cliente.get("nome","")}</div>
            <div>Telefone: {cliente.get("tel","")}</div>
            <div>E-mail: {cliente.get("email","")}</div>
            <div>Endereço: {cliente.get("end","")}</div>
          </div>

          <div class="sec">
            <h3>DETALHES DO SERVIÇO</h3>
            <div>Produto/Serviço: {produto}</div>
            <div>Custo material: R$ {_fmt_money(custo_material)}</div>
            <div>Trabalho: {horas:g}h x R$ {_fmt_money(valor_hora)}</div>
            <div>Despesas extras: R$ {_fmt_money(despesas)}</div>

            <div class="big">Custo Base: R$ {_fmt_money(custo_base)}</div>
            <div class="big">Preço Final: R$ {_fmt_money(preco_final)}</div>
            <div class="muted">Validade: {validade} dia(s)</div>
          </div>
        </body>
        </html>
        """

        # Gera PDF com reportlab (server-side)
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm

            from io import BytesIO

            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            w, h = A4

            y = h - 20 * mm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(20 * mm, y, "ORÇAMENTO - ARTE PREÇO PRO")
            y -= 8 * mm
            c.setFont("Helvetica", 10)
            c.drawString(20 * mm, y, f"Data: {_now_fmt()}")

            y -= 12 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, "DADOS DA EMPRESA")
            y -= 6 * mm
            c.setFont("Helvetica", 10)
            c.drawString(20 * mm, y, f"Nome: {empresa.get('nome','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Telefone: {empresa.get('tel','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"E-mail: {empresa.get('email','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Endereço: {empresa.get('end','')}")

            y -= 10 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, "DADOS DO CLIENTE")
            y -= 6 * mm
            c.setFont("Helvetica", 10)
            c.drawString(20 * mm, y, f"Nome: {cliente.get('nome','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Telefone: {cliente.get('tel','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"E-mail: {cliente.get('email','')}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Endereço: {cliente.get('end','')}")

            y -= 10 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, "DETALHES DO SERVIÇO")
            y -= 6 * mm
            c.setFont("Helvetica", 10)
            c.drawString(20 * mm, y, f"Produto/Serviço: {produto}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Custo material: R$ {_fmt_money(custo_material)}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Trabalho: {horas:g}h x R$ {_fmt_money(valor_hora)}")
            y -= 5 * mm
            c.drawString(20 * mm, y, f"Despesas extras: R$ {_fmt_money(despesas)}")

            y -= 10 * mm
            c.setFont("Helvetica-Bold", 16)
            c.drawString(20 * mm, y, f"Custo Base: R$ {_fmt_money(custo_base)}")
            y -= 10 * mm
            c.drawString(20 * mm, y, f"Preço Final: R$ {_fmt_money(preco_final)}")

            y -= 10 * mm
            c.setFont("Helvetica", 10)
            c.drawString(20 * mm, y, f"Validade: {validade} dia(s)")

            c.showPage()
            c.save()

            pdf_bytes = buffer.getvalue()
            buffer.close()

            resp = make_response(pdf_bytes)
            resp.headers["Content-Type"] = "application/pdf"
            resp.headers["Content-Disposition"] = 'inline; filename="orcamento_arte_preco_pro.pdf"'
            return resp
        except Exception:
            # fallback: retorna HTML (o navegador pode imprimir em PDF)
            resp = make_response(html_pdf)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp

    except Exception:
        return {"ok": False, "msg": "Erro interno ao gerar PDF"}, 200

# ==========================================
#  VERCEL ENTRYPOINT
# ==========================================
# Vercel usa `app` automaticamente ao importar o módulo.
# Não coloque app.run() aqui.
# ==========================================


# (Opcional) healthcheck
@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME}, 200
