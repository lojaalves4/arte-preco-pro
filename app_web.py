import os
import time
import traceback
from datetime import datetime

from flask import Flask, request, make_response

# PDF (leve e estável)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)

APP_TITLE = "Arte Preço Pro"


# -----------------------------
# Helpers: storage + safe parse
# -----------------------------
def _to_float(v, default=0.0):
    try:
        if v is None:
            return default
        v = str(v).strip().replace(".", "").replace(",", ".")
        return float(v) if v else default
    except Exception:
        return default


def _to_int(v, default=0):
    try:
        if v is None:
            return default
        v = str(v).strip()
        return int(float(v)) if v else default
    except Exception:
        return default


def _brl(valor: float) -> str:
    # formata R$ 1.234,56
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


# --------------------------------
# License: tenta usar core existente
# (compatível com 1 ou 2 parâmetros)
# --------------------------------
def validar_chave_flex(chave: str, device_id: str = "web_device"):
    """
    Retorna: (ok: bool, msg: str)
    """
    try:
        from core.license_core import validar_chave  # seu core
        import inspect

        sig = inspect.signature(validar_chave)
        if len(sig.parameters) == 1:
            return validar_chave(chave)
        else:
            return validar_chave(chave, device_id)
    except Exception as e:
        # Se por algum motivo o core falhar, não derruba o app (evita 500)
        return (False, f"Falha no validador de licença: {str(e)}")


# -----------------------------
# Cálculo (estável)
# -----------------------------
def calcular_preco_local(custo_material, horas, valor_hora, despesas_extras, margem_lucro):
    custo_base = custo_material + (horas * valor_hora) + despesas_extras
    preco_final = custo_base * (1.0 + (margem_lucro / 100.0))
    return custo_base, preco_final


# -----------------------------
# PDF
# -----------------------------
def gerar_pdf_orcamento(dados):
    """
    dados: dict com empresa, cliente e valores
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ORÇAMENTO - ARTE PREÇO PRO")

    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "DADOS DA EMPRESA")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Empresa: {dados.get('empresa_nome','')}")
    y -= 14
    c.drawString(50, y, f"Contato: {dados.get('empresa_contato','')}")
    y -= 14
    c.drawString(50, y, f"Endereço: {dados.get('empresa_endereco','')}")

    y -= 22
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "DADOS DO CLIENTE")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Cliente: {dados.get('cliente_nome','')}")
    y -= 14
    c.drawString(50, y, f"Contato: {dados.get('cliente_contato','')}")
    y -= 14
    c.drawString(50, y, f"Endereço: {dados.get('cliente_endereco','')}")

    y -= 22
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "SERVIÇO")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Produto/Serviço: {dados.get('produto','')}")
    y -= 14
    c.drawString(50, y, f"Custo do material: {_brl(dados.get('custo_material',0.0))}")
    y -= 14
    c.drawString(50, y, f"Horas trabalhadas: {dados.get('horas',0)}")
    y -= 14
    c.drawString(50, y, f"Valor/hora: {_brl(dados.get('valor_hora',0.0))}")
    y -= 14
    c.drawString(50, y, f"Despesas extras: {_brl(dados.get('despesas_extras',0.0))}")
    y -= 14
    c.drawString(50, y, f"Margem de lucro: {dados.get('margem_lucro',0)}%")
    y -= 14
    c.drawString(50, y, f"Validade: {dados.get('validade_dias',0)} dia(s)")

    y -= 22
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"TOTAL: {_brl(dados.get('preco_final',0.0))}")

    y -= 30
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Observação: Este orçamento pode sofrer alterações conforme briefing e escopo.")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


# -----------------------------
# UI HTML (uma página)
# -----------------------------
def page(html_body: str, title: str = APP_TITLE):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>

  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4A6B3E">
  <link rel="icon" href="/static/icon-192.png">

  <style>
    body {{
      margin: 0; padding: 0;
      font-family: Arial, sans-serif;
      background: #DCE5D5;
      color: #1b1b1b;
    }}
    .wrap {{
      max-width: 520px;
      margin: 0 auto;
      padding: 16px;
    }}
    h1 {{
      font-size: 40px;
      margin: 12px 0 8px;
    }}
    .card {{
      background: #E8EFE2;
      border-radius: 14px;
      padding: 14px;
      border: 1px solid rgba(0,0,0,0.06);
    }}
    label {{ font-weight: 700; display:block; margin-top: 10px; }}
    input {{
      width: 100%;
      box-sizing: border-box;
      padding: 12px;
      border-radius: 10px;
      border: 1px solid rgba(0,0,0,0.18);
      font-size: 16px;
      background: #fff;
      margin-top: 6px;
    }}
    .row {{
      display:flex;
      gap:10px;
    }}
    .row > div {{ flex: 1; }}
    button {{
      width: 100%;
      padding: 14px;
      border: 0;
      border-radius: 12px;
      background: #4A6B3E;
      color: white;
      font-size: 18px;
      font-weight: 800;
      margin-top: 16px;
    }}
    .btn2 {{
      background: #2f2f2f;
    }}
    .muted {{
      opacity: .8;
      font-size: 13px;
      margin-top: 8px;
    }}
    .ok {{
      background:#eaf6ea; border:1px solid #a8d5a8;
      padding:10px; border-radius:10px; margin-top:10px;
    }}
    .err {{
      background:#ffecec; border:1px solid #f0b2b2;
      padding:10px; border-radius:10px; margin-top:10px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    {html_body}
  </div>

<script>
  // PWA SW
  if ('serviceWorker' in navigator) {{
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{{}});
  }}

  // Licença salva
  const licKey = "artepreco_license";
  const orgKey = "artepreco_company";

  function getSavedLicense() {{
    return localStorage.getItem(licKey) || "";
  }}
  function saveLicense(k) {{
    localStorage.setItem(licKey, k);
  }}

  // Empresa salva
  function saveCompany() {{
    const data = {{
      empresa_nome: document.getElementById("empresa_nome")?.value || "",
      empresa_contato: document.getElementById("empresa_contato")?.value || "",
      empresa_endereco: document.getElementById("empresa_endereco")?.value || ""
    }};
    localStorage.setItem(orgKey, JSON.stringify(data));
  }}
  function loadCompany() {{
    try {{
      const raw = localStorage.getItem(orgKey);
      if(!raw) return;
      const d = JSON.parse(raw);
      if(document.getElementById("empresa_nome")) document.getElementById("empresa_nome").value = d.empresa_nome || "";
      if(document.getElementById("empresa_contato")) document.getElementById("empresa_contato").value = d.empresa_contato || "";
      if(document.getElementById("empresa_endereco")) document.getElementById("empresa_endereco").value = d.empresa_endereco || "";
    }} catch(e) {{}}
  }}

  // Ao entrar: preenche licença no input (se existir) e empresa (se existir)
  window.addEventListener("load", () => {{
    const lic = getSavedLicense();
    const licInput = document.getElementById("license");
    if (licInput && lic) licInput.value = lic;

    loadCompany();
  }});

  // Botão ativar
  async function ativar() {{
    const k = (document.getElementById("license")?.value || "").trim();
    if(!k) {{
      alert("Cole a chave AP-...");
      return;
    }}
    const r = await fetch("/api/activate", {{
      method: "POST",
      headers: {{ "Content-Type":"application/json" }},
      body: JSON.stringify({{ license: k }})
    }});
    const j = await r.json().catch(()=>({{ok:false, msg:"Erro"}}));
    if(j.ok) {{
      saveLicense(k);
      window.location.href = "/app";
    }} else {{
      const box = document.getElementById("activate_msg");
      if(box) {{
        box.className = "err";
        box.textContent = j.msg || "Erro ao ativar.";
      }} else {{
        alert(j.msg || "Erro ao ativar.");
      }}
    }}
  }}

  // Salvar empresa
  function salvarEmpresa() {{
    saveCompany();
    const box = document.getElementById("empresa_msg");
    if(box) {{
      box.className="ok";
      box.textContent="✅ Dados da empresa salvos neste aparelho.";
    }}
  }}

  // Calcular + PDF
  async function calcular() {{
    // trava menos: desabilita botão
    const btn = document.getElementById("btn_calc");
    if(btn) btn.disabled = true;

    saveCompany();

    const payload = {{
      produto: (document.getElementById("produto")?.value || "").trim(),
      custo_material: document.getElementById("custo_material")?.value,
      horas: document.getElementById("horas")?.value,
      valor_hora: document.getElementById("valor_hora")?.value,
      despesas_extras: document.getElementById("despesas_extras")?.value,
      margem_lucro: document.getElementById("margem_lucro")?.value,
      validade_dias: document.getElementById("validade_dias")?.value,

      empresa_nome: document.getElementById("empresa_nome")?.value || "",
      empresa_contato: document.getElementById("empresa_contato")?.value || "",
      empresa_endereco: document.getElementById("empresa_endereco")?.value || "",

      cliente_nome: document.getElementById("cliente_nome")?.value || "",
      cliente_contato: document.getElementById("cliente_contato")?.value || "",
      cliente_endereco: document.getElementById("cliente_endereco")?.value || "",

      license: getSavedLicense()
    }};

    const r = await fetch("/api/calc", {{
      method:"POST",
      headers: {{ "Content-Type":"application/json" }},
      body: JSON.stringify(payload)
    }});
    const j = await r.json().catch(()=>({{ok:false, msg:"Erro"}}));

    if(btn) btn.disabled = false;

    const box = document.getElementById("result");
    if(!box) return;

    if(!j.ok) {{
      box.className="err";
      box.innerText = j.msg || "Erro ao calcular.";
      return;
    }}

    box.className="ok";
    box.innerHTML = `
      <div><b>Produto:</b> ${j.produto}</div>
      <div><b>Custo Base:</b> ${j.custo_base_fmt}</div>
      <div style="font-size:26px; font-weight:900; margin-top:8px;">
        Preço Final: ${j.preco_final_fmt}
      </div>
      <div class="muted">Validade: ${j.validade_dias} dia(s)</div>

      <button onclick="baixarPDF()" style="margin-top:12px;">Gerar PDF</button>
    `;

    // guarda último cálculo p/ PDF
    window.__LAST_CALC__ = j;
  }}

  async function baixarPDF() {{
    const last = window.__LAST_CALC__;
    if(!last || !last.ok) {{
      alert("Faça um cálculo primeiro.");
      return;
    }}
    const r = await fetch("/api/pdf", {{
      method:"POST",
      headers: {{ "Content-Type":"application/json" }},
      body: JSON.stringify({{ license: getSavedLicense(), calc: last }})
    }});
    if(!r.ok) {{
      alert("Erro ao gerar PDF.");
      return;
    }}
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = last.pdf_nome || "orcamento.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }}
</script>

</body>
</html>"""


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def home():
    body = """
      <h1>Arte Preço Pro</h1>
      <div class="card">
        <b>Ativação do Arte Preço Pro</b>
        <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
        <input id="license" placeholder="Cole sua chave AP-...">
        <button onclick="ativar()">Ativar</button>
        <div id="activate_msg" class="muted"></div>
      </div>
    """
    return page(body, APP_TITLE)


@app.post("/api/activate")
def api_activate():
    try:
        data = request.get_json(force=True) or {}
        chave = (data.get("license") or "").strip()
        if not chave:
            return {"ok": False, "msg": "Chave vazia."}, 400

        ok, msg = validar_chave_flex(chave, "web_device")
        return {"ok": bool(ok), "msg": msg}, (200 if ok else 403)
    except Exception:
        return {"ok": False, "msg": "Erro interno ao ativar."}, 500


@app.get("/app")
def app_page():
    body = f"""
      <h1>{APP_TITLE}</h1>

      <div class="card">
        <b>DADOS DA EMPRESA</b>
        <label>Nome da Empresa</label>
        <input id="empresa_nome" placeholder="Ex: PJA Studio Design">

        <label>Contato (WhatsApp / Tel / Email)</label>
        <input id="empresa_contato" placeholder="Ex: (22) 9xxxx-xxxx / email@...">

        <label>Endereço</label>
        <input id="empresa_endereco" placeholder="Ex: Rio das Ostras - RJ">

        <button class="btn2" onclick="salvarEmpresa()">Salvar dados da empresa</button>
        <div id="empresa_msg" class="muted"></div>
      </div>

      <div style="height:12px;"></div>

      <div class="card">
        <b>DADOS DO CLIENTE</b>

        <label>Nome do Cliente</label>
        <input id="cliente_nome" placeholder="Ex: João da Silva">

        <label>Contato do Cliente</label>
        <input id="cliente_contato" placeholder="Ex: (xx) 9xxxx-xxxx">

        <label>Endereço do Cliente</label>
        <input id="cliente_endereco" placeholder="Ex: Cidade / Bairro">
      </div>

      <div style="height:12px;"></div>

      <div class="card">
        <b>ORÇAMENTO</b>

        <label>Produto</label>
        <input id="produto" placeholder="Ex: Logo">

        <label>Custo do Material (R$)</label>
        <input id="custo_material" placeholder="Ex: 10">

        <div class="row">
          <div>
            <label>Horas Trabalhadas</label>
            <input id="horas" placeholder="Ex: 4">
          </div>
          <div>
            <label>Valor da Hora (R$)</label>
            <input id="valor_hora" placeholder="Ex: 30">
          </div>
        </div>

        <label>Despesas Extras (R$)</label>
        <input id="despesas_extras" placeholder="Ex: 2">

        <label>Margem de Lucro (%)</label>
        <input id="margem_lucro" placeholder="Ex: 80">

        <label>Validade (dias)</label>
        <input id="validade_dias" placeholder="Ex: 7">

        <button id="btn_calc" onclick="calcular()">Calcular</button>

        <div id="result" class="muted"></div>
      </div>
    """
    return page(body, APP_TITLE)


@app.post("/api/calc")
def api_calc():
    try:
        d = request.get_json(force=True) or {}

        chave = (d.get("license") or "").strip()
        ok, msg = validar_chave_flex(chave, "web_device")
        if not ok:
            return {"ok": False, "msg": "Licença inválida ou não ativada."}, 403

        produto = (d.get("produto") or "").strip() or "Serviço"
        custo_material = _to_float(d.get("custo_material"), 0.0)
        horas = _to_float(d.get("horas"), 0.0)
        valor_hora = _to_float(d.get("valor_hora"), 0.0)
        despesas_extras = _to_float(d.get("despesas_extras"), 0.0)
        margem_lucro = _to_float(d.get("margem_lucro"), 0.0)
        validade_dias = _to_int(d.get("validade_dias"), 7)

        custo_base, preco_final = calcular_preco_local(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas_extras=despesas_extras,
            margem_lucro=margem_lucro,
        )

        resp = {
            "ok": True,
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "custo_base_fmt": _brl(custo_base),
            "preco_final_fmt": _brl(preco_final),
            "validade_dias": validade_dias,

            "empresa_nome": d.get("empresa_nome",""),
            "empresa_contato": d.get("empresa_contato",""),
            "empresa_endereco": d.get("empresa_endereco",""),
            "cliente_nome": d.get("cliente_nome",""),
            "cliente_contato": d.get("cliente_contato",""),
            "cliente_endereco": d.get("cliente_endereco",""),
        }

        # nome amigável do PDF
        safe_prod = "".join([c for c in produto if c.isalnum() or c in " _-"]).strip().replace(" ", "_")
        resp["pdf_nome"] = f"orcamento_{safe_prod or 'servico'}.pdf"

        return resp, 200

    except Exception:
        # nunca derruba (evita 500 sem mensagem)
        return {"ok": False, "msg": "Erro interno ao calcular."}, 500


@app.post("/api/pdf")
def api_pdf():
    try:
        d = request.get_json(force=True) or {}
        chave = (d.get("license") or "").strip()
        ok, msg = validar_chave_flex(chave, "web_device")
        if not ok:
            return {"ok": False, "msg": "Licença inválida."}, 403

        calc = d.get("calc") or {}
        if not calc.get("ok"):
            return {"ok": False, "msg": "Sem cálculo válido."}, 400

        pdf_bytes = gerar_pdf_orcamento({
            "empresa_nome": calc.get("empresa_nome",""),
            "empresa_contato": calc.get("empresa_contato",""),
            "empresa_endereco": calc.get("empresa_endereco",""),

            "cliente_nome": calc.get("cliente_nome",""),
            "cliente_contato": calc.get("cliente_contato",""),
            "cliente_endereco": calc.get("cliente_endereco",""),

            "produto": calc.get("produto",""),
            "custo_material": float(calc.get("custo_material", 0.0)) if str(calc.get("custo_material","")).strip() else 0.0,
            "horas": float(calc.get("horas", 0.0)) if str(calc.get("horas","")).strip() else 0.0,
            "valor_hora": float(calc.get("valor_hora", 0.0)) if str(calc.get("valor_hora","")).strip() else 0.0,
            "despesas_extras": float(calc.get("despesas_extras", 0.0)) if str(calc.get("despesas_extras","")).strip() else 0.0,
            "margem_lucro": float(calc.get("margem_lucro", 0.0)) if str(calc.get("margem_lucro","")).strip() else 0.0,
            "validade_dias": int(calc.get("validade_dias", 7)),
            "preco_final": float(calc.get("preco_final", 0.0)),
        })

        filename = calc.get("pdf_nome") or "orcamento.pdf"
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    except Exception:
        return {"ok": False, "msg": "Erro interno ao gerar PDF."}, 500


# handler (Vercel python runtime)
# a Vercel descobre automaticamente o app Flask pelo "app"
