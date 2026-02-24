# app_web.py  (VERSÃO FINAL: TELA + ATIVAÇÃO + CÁLCULO + PDF)
# APAGA TUDO E COLA ESTE ARQUIVO INTEIRO

from flask import Flask, request, jsonify, make_response, send_from_directory
from datetime import datetime
import os
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    from core.license_core import validar_chave
except Exception:
    validar_chave = None


app = Flask(__name__, static_folder="static")


# =========================================================
# DADOS PADRÃO DA EMPRESA (QUEM COMPRAR O APP PODE EDITAR)
# Você pode trocar aqui, ou usar variáveis da Vercel:
# EMPRESA_NOME, EMPRESA_CONTATO, EMPRESA_EMAIL, EMPRESA_ENDERECO
# =========================================================
EMPRESA_NOME = os.getenv("EMPRESA_NOME", "PJA Studio Design")
EMPRESA_CONTATO = os.getenv("EMPRESA_CONTATO", "(24) 99999-9999")
EMPRESA_EMAIL = os.getenv("EMPRESA_EMAIL", "contato@seudominio.com")
EMPRESA_ENDERECO = os.getenv("EMPRESA_ENDERECO", "Rio de Janeiro - RJ")


# ============================
# Helpers
# ============================
def brl(valor: float) -> str:
    try:
        v = float(valor)
    except Exception:
        v = 0.0
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def calcular_preco(custo_material, horas, valor_hora, despesas, margem):
    custo_base = float(custo_material) + (float(horas) * float(valor_hora)) + float(despesas)
    preco_final = custo_base * (1.0 + (float(margem) / 100.0))
    return custo_base, preco_final


def gerar_pdf_orcamento(dados: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    y = h - 50

    # Cabeçalho empresa
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, dados.get("empresa_nome", EMPRESA_NOME))
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Contato: {dados.get('empresa_contato', EMPRESA_CONTATO)}")
    y -= 14
    c.drawString(40, y, f"E-mail: {dados.get('empresa_email', EMPRESA_EMAIL)}")
    y -= 14
    c.drawString(40, y, f"Endereço: {dados.get('empresa_endereco', EMPRESA_ENDERECO)}")

    y -= 24
    c.line(40, y, w - 40, y)

    y -= 28
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "ORÇAMENTO")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 22

    # Cliente
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Cliente")
    y -= 16
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Nome: {dados.get('cliente_nome', '')}")
    y -= 14
    c.drawString(40, y, f"Contato: {dados.get('cliente_contato', '')}")
    y -= 14
    c.drawString(40, y, f"Endereço: {dados.get('cliente_endereco', '')}")

    y -= 22
    c.line(40, y, w - 40, y)
    y -= 22

    # Serviço
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Serviço")
    y -= 16
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Produto/Serviço: {dados.get('produto', '')}")
    y -= 16
    c.drawString(40, y, f"Custo do Material: {dados.get('custo_material_fmt', '')}")
    y -= 16
    c.drawString(40, y, f"Horas Trabalhadas: {dados.get('horas', '')}")
    y -= 16
    c.drawString(40, y, f"Valor da Hora: {dados.get('valor_hora_fmt', '')}")
    y -= 16
    c.drawString(40, y, f"Despesas Extras: {dados.get('despesas_fmt', '')}")
    y -= 16
    c.drawString(40, y, f"Margem de Lucro: {dados.get('margem', '')}%")
    y -= 22

    # Totais
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, f"Custo Base: {dados.get('custo_base_fmt', '')}")
    y -= 28
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, y, f"Preço Final: {dados.get('preco_final_fmt', '')}")
    y -= 24

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Validade do orçamento: {dados.get('validade', 0)} dia(s)")

    y -= 30
    c.setFont("Helvetica", 9)
    c.drawString(40, y, "Gerado pelo Arte Preço Pro")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()


# ============================
# STATIC
# ============================
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ============================
# TELA PRINCIPAL (HTML)
# ============================
@app.get("/")
def index():
    html = r"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Arte Preço Pro</title>

  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4A6B3E">
  <style>
    body{font-family:Arial,Helvetica,sans-serif;background:#dce5d5;margin:0}
    .wrap{max-width:620px;margin:0 auto;padding:18px}
    .card{background:#e7efe1;border-radius:14px;padding:16px;margin:12px 0;box-shadow:0 1px 0 rgba(0,0,0,.06)}
    h1{margin:6px 0 12px 0}
    label{display:block;font-weight:700;margin:10px 0 6px}
    input{width:100%;padding:12px;border-radius:10px;border:1px solid #c1cbb8;font-size:16px;box-sizing:border-box;background:#fff}
    .row{display:flex;gap:10px}
    .row > div{flex:1}
    .btn{width:100%;padding:14px;border:0;border-radius:12px;font-size:18px;font-weight:700;cursor:pointer}
    .btn-primary{background:#4A6B3E;color:#fff}
    .btn-secondary{background:#2f2f2f;color:#fff}
    .btn-outline{background:#fff;border:2px solid #4A6B3E;color:#4A6B3E}
    .msg{padding:10px;border-radius:10px;margin-top:10px;background:#fff}
    .ok{border-left:6px solid #2f8f2f}
    .err{border-left:6px solid #b00020}
    .muted{opacity:.75;font-size:13px}
    .small{font-size:13px}
    .hidden{display:none}
    .big{font-size:34px;font-weight:800;margin:10px 0}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Arte Preço Pro</h1>
      <div class="muted">Ative uma vez. Depois o app lembra no celular.</div>

      <label>Chave de Ativação</label>
      <input id="chave" placeholder="Cole a chave AP-..." />

      <button class="btn btn-primary" id="btnAtivar">Ativar</button>
      <div id="msgAtiv" class="msg hidden"></div>
    </div>

    <div class="card hidden" id="areaApp">
      <h2>Dados da Empresa (Fornecedor)</h2>
      <div class="muted small">Quem comprar o app pode trocar esses dados aqui antes de gerar o PDF.</div>

      <label>Nome da Empresa</label>
      <input id="empresa_nome" />

      <label>Contato</label>
      <input id="empresa_contato" />

      <label>E-mail</label>
      <input id="empresa_email" />

      <label>Endereço</label>
      <input id="empresa_endereco" />

      <hr style="margin:16px 0;opacity:.2">

      <h2>Dados do Cliente</h2>
      <label>Nome do Cliente</label>
      <input id="cliente_nome" placeholder="Ex: Jorge Silva" />

      <label>Contato do Cliente</label>
      <input id="cliente_contato" placeholder="Ex: (21) 99999-9999" />

      <label>Endereço do Cliente</label>
      <input id="cliente_endereco" placeholder="Ex: Rua X, 123 - Cidade/UF" />

      <hr style="margin:16px 0;opacity:.2">

      <h2>Orçamento</h2>

      <label>Produto/Serviço</label>
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
      <input id="despesas" inputmode="decimal" placeholder="Ex: 2" />

      <label>Margem de Lucro (%)</label>
      <input id="margem" inputmode="decimal" placeholder="Ex: 80" />

      <label>Validade (dias)</label>
      <input id="validade" inputmode="numeric" placeholder="Ex: 7" />

      <button class="btn btn-primary" id="btnCalcular">Calcular</button>

      <div id="resultado" class="msg hidden"></div>

      <div class="row" style="margin-top:12px">
        <div><button class="btn btn-outline" id="btnPDF" disabled>Gerar PDF</button></div>
        <div><button class="btn btn-secondary" id="btnSair">Sair</button></div>
      </div>

      <div class="muted small" style="margin-top:10px">
        Dica: se aparecer apenas “Adicionar à tela inicial”, é normal no Android/Chrome. Vai criar um atalho tipo app.
      </div>
    </div>
  </div>

<script>
  // Defaults vindos do servidor
  const DEFAULTS = {
    empresa_nome: "__EMPRESA_NOME__",
    empresa_contato: "__EMPRESA_CONTATO__",
    empresa_email: "__EMPRESA_EMAIL__",
    empresa_endereco: "__EMPRESA_ENDERECO__"
  };

  const $ = (id) => document.getElementById(id);

  const msg = (el, text, ok=true) => {
    el.classList.remove("hidden");
    el.classList.toggle("ok", ok);
    el.classList.toggle("err", !ok);
    el.textContent = text;
  };

  const setLoading = (btn, loading) => {
    btn.disabled = loading;
    btn.dataset.old = btn.dataset.old || btn.textContent;
    btn.textContent = loading ? "Aguarde..." : btn.dataset.old;
  };

  // Carregar dados salvos
  function loadSaved() {
    const chave = localStorage.getItem("ap_chave") || "";
    $("chave").value = chave;

    // dados empresa/cliente/orcamento
    const fields = [
      "empresa_nome","empresa_contato","empresa_email","empresa_endereco",
      "cliente_nome","cliente_contato","cliente_endereco",
      "produto","custo_material","horas","valor_hora","despesas","margem","validade"
    ];

    fields.forEach(f => {
      const v = localStorage.getItem("ap_" + f);
      if (v !== null && v !== undefined && v !== "") $(f).value = v;
    });

    // se não tiver nada da empresa, seta default do servidor
    if (!$("empresa_nome").value) $("empresa_nome").value = DEFAULTS.empresa_nome;
    if (!$("empresa_contato").value) $("empresa_contato").value = DEFAULTS.empresa_contato;
    if (!$("empresa_email").value) $("empresa_email").value = DEFAULTS.empresa_email;
    if (!$("empresa_endereco").value) $("empresa_endereco").value = DEFAULTS.empresa_endereco;

    const ativado = localStorage.getItem("ap_ativado") === "1";
    if (ativado) $("areaApp").classList.remove("hidden");
  }

  function saveField(id){
    localStorage.setItem("ap_" + id, $(id).value || "");
  }

  // Salvar ao digitar (evita perder)
  [
    "empresa_nome","empresa_contato","empresa_email","empresa_endereco",
    "cliente_nome","cliente_contato","cliente_endereco",
    "produto","custo_material","horas","valor_hora","despesas","margem","validade"
  ].forEach(id => {
    $(id).addEventListener("input", () => saveField(id));
  });

  // Ativar
  $("btnAtivar").addEventListener("click", async () => {
    const chave = $("chave").value.trim();
    localStorage.setItem("ap_chave", chave);

    const el = $("msgAtiv");
    setLoading($("btnAtivar"), true);
    try{
      const r = await fetch("/api/ativar", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({chave})
      });
      const j = await r.json().catch(() => ({}));
      if(!r.ok || !j.ok){
        msg(el, (j.msg || "Erro ao ativar."), false);
        localStorage.removeItem("ap_ativado");
        $("areaApp").classList.add("hidden");
        return;
      }
      msg(el, "✅ " + (j.msg || "Ativado."), true);
      localStorage.setItem("ap_ativado", "1");
      $("areaApp").classList.remove("hidden");
    }catch(e){
      msg(el, "Erro de conexão ao ativar.", false);
    }finally{
      setLoading($("btnAtivar"), false);
    }
  });

  let lastPayload = null;

  // Calcular
  $("btnCalcular").addEventListener("click", async () => {
    const btn = $("btnCalcular");
    const out = $("resultado");
    $("btnPDF").disabled = true;

    const payload = {
      // empresa
      empresa_nome: $("empresa_nome").value.trim(),
      empresa_contato: $("empresa_contato").value.trim(),
      empresa_email: $("empresa_email").value.trim(),
      empresa_endereco: $("empresa_endereco").value.trim(),
      // cliente
      cliente_nome: $("cliente_nome").value.trim(),
      cliente_contato: $("cliente_contato").value.trim(),
      cliente_endereco: $("cliente_endereco").value.trim(),
      // orçamento
      produto: $("produto").value.trim(),
      custo_material: $("custo_material").value.trim(),
      horas: $("horas").value.trim(),
      valor_hora: $("valor_hora").value.trim(),
      despesas: $("despesas").value.trim(),
      margem: $("margem").value.trim(),
      validade: $("validade").value.trim()
    };

    // validação básica
    if(!payload.produto){
      msg(out, "Informe o Produto/Serviço.", false);
      return;
    }

    setLoading(btn, true);
    try{
      const r = await fetch("/api/calcular", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      const j = await r.json().catch(() => ({}));
      if(!r.ok || !j.ok){
        msg(out, j.msg || "Erro ao calcular.", false);
        return;
      }

      lastPayload = payload;

      out.classList.remove("hidden");
      out.classList.add("ok");
      out.classList.remove("err");
      out.innerHTML = `
        <div><b>Produto:</b> ${j.produto}</div>
        <div><b>Custo Base:</b> ${j.custo_base_fmt}</div>
        <div class="big">${j.preco_final_fmt}</div>
        <div>Validade: ${j.validade} dia(s)</div>
      `;

      $("btnPDF").disabled = false;

    }catch(e){
      msg(out, "Erro de conexão ao calcular.", false);
    }finally{
      setLoading(btn, false);
    }
  });

  // Gerar PDF (sem cache: envia os dados e recebe o PDF)
  $("btnPDF").addEventListener("click", async () => {
    if(!lastPayload) return;

    const btn = $("btnPDF");
    setLoading(btn, true);

    try{
      const r = await fetch("/api/pdf", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(lastPayload)
      });
      if(!r.ok){
        alert("Erro ao gerar PDF.");
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "orcamento.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }catch(e){
      alert("Erro de conexão ao gerar PDF.");
    }finally{
      setLoading(btn, false);
    }
  });

  $("btnSair").addEventListener("click", () => {
    // só esconde a área do app; mantém ativação salva
    $("areaApp").classList.add("hidden");
  });

  // Service Worker (PWA)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(()=>{});
  }

  loadSaved();
</script>
</body>
</html>
"""
    html = html.replace("__EMPRESA_NOME__", EMPRESA_NOME)
    html = html.replace("__EMPRESA_CONTATO__", EMPRESA_CONTATO)
    html = html.replace("__EMPRESA_EMAIL__", EMPRESA_EMAIL)
    html = html.replace("__EMPRESA_ENDERECO__", EMPRESA_ENDERECO)
    return html


# ============================
# API - ATIVAR
# ============================
@app.post("/api/ativar")
def api_ativar():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    if not chave.startswith("AP-"):
        return jsonify(ok=False, msg="Chave inválida."), 400

    if validar_chave is None:
        return jsonify(ok=True, msg="Ativado.")

    ok, msg = validar_chave(chave)
    if ok:
        return jsonify(ok=True, msg=msg)
    return jsonify(ok=False, msg=msg), 400


# ============================
# API - CALCULAR
# ============================
@app.post("/api/calcular")
def api_calcular():
    data = request.get_json(silent=True) or {}

    try:
        produto = (data.get("produto") or "").strip()
        custo_material = float(str(data.get("custo_material") or "0").replace(",", "."))
        horas = float(str(data.get("horas") or "0").replace(",", "."))
        valor_hora = float(str(data.get("valor_hora") or "0").replace(",", "."))
        despesas = float(str(data.get("despesas") or "0").replace(",", "."))
        margem = float(str(data.get("margem") or "0").replace(",", "."))
        validade = int(float(str(data.get("validade") or "0").replace(",", ".")))
    except Exception:
        return jsonify(ok=False, msg="Campos numéricos inválidos."), 400

    if not produto:
        return jsonify(ok=False, msg="Informe o produto/serviço."), 400

    custo_base, preco_final = calcular_preco(custo_material, horas, valor_hora, despesas, margem)

    return jsonify(
        ok=True,
        produto=produto,
        custo_base_fmt=brl(custo_base),
        preco_final_fmt=brl(preco_final),
        validade=validade
    )


# ============================
# API - PDF (POST, SEM CACHE)
# ============================
@app.post("/api/pdf")
def api_pdf():
    data = request.get_json(silent=True) or {}

    try:
        produto = (data.get("produto") or "").strip()
        custo_material = float(str(data.get("custo_material") or "0").replace(",", "."))
        horas = float(str(data.get("horas") or "0").replace(",", "."))
        valor_hora = float(str(data.get("valor_hora") or "0").replace(",", "."))
        despesas = float(str(data.get("despesas") or "0").replace(",", "."))
        margem = float(str(data.get("margem") or "0").replace(",", "."))
        validade = int(float(str(data.get("validade") or "0").replace(",", ".")))
    except Exception:
        return "Campos inválidos", 400

    custo_base, preco_final = calcular_preco(custo_material, horas, valor_hora, despesas, margem)

    pdf_data = {
        # empresa (pode vir do cliente, se ele editar na tela)
        "empresa_nome": (data.get("empresa_nome") or EMPRESA_NOME).strip(),
        "empresa_contato": (data.get("empresa_contato") or EMPRESA_CONTATO).strip(),
        "empresa_email": (data.get("empresa_email") or EMPRESA_EMAIL).strip(),
        "empresa_endereco": (data.get("empresa_endereco") or EMPRESA_ENDERECO).strip(),
        # cliente
        "cliente_nome": (data.get("cliente_nome") or "").strip(),
        "cliente_contato": (data.get("cliente_contato") or "").strip(),
        "cliente_endereco": (data.get("cliente_endereco") or "").strip(),
        # serviço e valores
        "produto": produto,
        "custo_material_fmt": brl(custo_material),
        "horas": horas,
        "valor_hora_fmt": brl(valor_hora),
        "despesas_fmt": brl(despesas),
        "margem": margem,
        "custo_base_fmt": brl(custo_base),
        "preco_final_fmt": brl(preco_final),
        "validade": validade,
    }

    pdf_bytes = gerar_pdf_orcamento(pdf_data)

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "attachment; filename=orcamento.pdf"
    return resp


if __name__ == "__main__":
    app.run(debug=True)
