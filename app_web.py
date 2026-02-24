# app_web.py
import os
import io
import json
import base64
import hashlib
from datetime import datetime

from flask import Flask, request, jsonify, send_file, render_template_string, make_response

# ============================================================
# ✅ 1) Flask APP precisa existir ANTES de usar @app.route
# ============================================================
app = Flask(__name__)

# ============================================================
# ✅ 2) Licença (usa seu core se existir)
# ============================================================
def _validar_chave_backend(chave: str):
    """
    Retorna (ok: bool, msg: str).
    Usa core.license_core.validar_chave se existir.
    """
    chave = (chave or "").strip()
    if not chave:
        return False, "Chave vazia."

    try:
        from core.license_core import validar_chave  # type: ignore
        ret = validar_chave(chave)
        # Pode retornar bool ou (bool, msg)
        if isinstance(ret, tuple) and len(ret) >= 2:
            return bool(ret[0]), str(ret[1])
        return bool(ret), "OK"
    except Exception as e:
        return False, f"Erro ao validar chave: {e}"

# ============================================================
# ✅ 3) Cálculo (fallback interno) — sem depender de assinatura externa
# ============================================================
def calcular_preco_fallback(custo_material, horas_trabalhadas, valor_hora, despesas_extras, margem_lucro):
    """
    Regra simples e estável:
    custo_base = custo_material + (horas * valor_hora) + despesas_extras
    preco_final = custo_base * (1 + margem/100)
    """
    custo_base = float(custo_material) + (float(horas_trabalhadas) * float(valor_hora)) + float(despesas_extras)
    preco_final = custo_base * (1.0 + (float(margem_lucro) / 100.0))
    return custo_base, preco_final

def _fmt_brl(valor: float) -> str:
    # Formato brasileiro: 1.234,56
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

# ============================================================
# ✅ 4) PDF (reportlab com fallback para fpdf)
# ============================================================
def gerar_pdf_bytes(dados: dict) -> bytes:
    """
    Gera PDF de orçamento. (Não inclui "Margem" no PDF, como você pediu.)
    """
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.units import mm  # type: ignore

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        largura, altura = A4

        y = altura - 20 * mm

        def linha(txt, dy=6*mm, bold=False):
            nonlocal y
            if bold:
                c.setFont("Helvetica-Bold", 12)
            else:
                c.setFont("Helvetica", 11)
            c.drawString(20*mm, y, txt)
            y -= dy

        c.setTitle("ORÇAMENTO - ARTE PREÇO PRO")

        linha("ORÇAMENTO - ARTE PREÇO PRO", bold=True, dy=8*mm)
        linha(f"Data: {dados.get('data_hora', '')}", dy=10*mm)

        linha("DADOS DA EMPRESA", bold=True)
        linha(f"Nome: {dados.get('empresa_nome','')}")
        linha(f"Telefone: {dados.get('empresa_tel','')}")
        linha(f"E-mail: {dados.get('empresa_email','')}")
        linha(f"Endereço: {dados.get('empresa_endereco','')}", dy=10*mm)

        linha("DADOS DO CLIENTE", bold=True)
        linha(f"Nome: {dados.get('cliente_nome','')}")
        linha(f"Telefone: {dados.get('cliente_tel','')}")
        linha(f"E-mail: {dados.get('cliente_email','')}")
        linha(f"Endereço: {dados.get('cliente_endereco','')}", dy=10*mm)

        linha("DETALHES DO SERVIÇO", bold=True)
        linha(f"Produto/Serviço: {dados.get('produto','')}")
        linha(f"Custo material: {_fmt_brl(float(dados.get('custo_material',0) or 0))}")
        linha(f"Trabalho: {dados.get('horas_trabalhadas','')}h  x  {_fmt_brl(float(dados.get('valor_hora',0) or 0))}")
        linha(f"Despesas extras: {_fmt_brl(float(dados.get('despesas_extras',0) or 0))}", dy=10*mm)

        linha(f"Custo Base: {_fmt_brl(float(dados.get('custo_base',0) or 0))}", bold=True, dy=8*mm)
        linha(f"Preço Final: {_fmt_brl(float(dados.get('preco_final',0) or 0))}", bold=True, dy=10*mm)
        linha(f"Validade: {dados.get('validade_dias','')} dia(s)")

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    except Exception:
        # fallback fpdf
        try:
            from fpdf import FPDF  # type: ignore

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "ORÇAMENTO - ARTE PREÇO PRO", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.ln(2)
            pdf.cell(0, 8, f"Data: {dados.get('data_hora', '')}", ln=True)
            pdf.ln(4)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "DADOS DA EMPRESA", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 7, f"Nome: {dados.get('empresa_nome','')}", ln=True)
            pdf.cell(0, 7, f"Telefone: {dados.get('empresa_tel','')}", ln=True)
            pdf.cell(0, 7, f"E-mail: {dados.get('empresa_email','')}", ln=True)
            pdf.multi_cell(0, 7, f"Endereço: {dados.get('empresa_endereco','')}")
            pdf.ln(3)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "DADOS DO CLIENTE", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 7, f"Nome: {dados.get('cliente_nome','')}", ln=True)
            pdf.cell(0, 7, f"Telefone: {dados.get('cliente_tel','')}", ln=True)
            pdf.cell(0, 7, f"E-mail: {dados.get('cliente_email','')}", ln=True)
            pdf.multi_cell(0, 7, f"Endereço: {dados.get('cliente_endereco','')}")
            pdf.ln(3)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "DETALHES DO SERVIÇO", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 7, f"Produto/Serviço: {dados.get('produto','')}", ln=True)
            pdf.cell(0, 7, f"Custo material: {_fmt_brl(float(dados.get('custo_material',0) or 0))}", ln=True)
            pdf.cell(0, 7, f"Trabalho: {dados.get('horas_trabalhadas','')}h x {_fmt_brl(float(dados.get('valor_hora',0) or 0))}", ln=True)
            pdf.cell(0, 7, f"Despesas extras: {_fmt_brl(float(dados.get('despesas_extras',0) or 0))}", ln=True)
            pdf.ln(3)

            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 9, f"Custo Base: {_fmt_brl(float(dados.get('custo_base',0) or 0))}", ln=True)
            pdf.cell(0, 9, f"Preço Final: {_fmt_brl(float(dados.get('preco_final',0) or 0))}", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 7, f"Validade: {dados.get('validade_dias','')} dia(s)", ln=True)

            out = pdf.output(dest="S").encode("latin1")
            return out

        except Exception as e2:
            raise RuntimeError(f"Sem gerador de PDF disponível (reportlab/fpdf). Erro: {e2}")

# ============================================================
# ✅ 5) Front (uma página só, salva dados no localStorage)
# ============================================================
HTML = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Arte Preço Pro</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;background:#dce7d6;margin:0;padding:0}
    .wrap{max-width:720px;margin:0 auto;padding:16px}
    .card{background:#eef4ea;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
    h1{margin:6px 0 12px 0}
    label{font-weight:700;display:block;margin:10px 0 6px}
    input{width:100%;padding:12px;border-radius:10px;border:1px solid #c9d6c2;font-size:16px}
    .row{display:flex;gap:12px}
    .row>div{flex:1}
    button{width:100%;padding:14px;border:none;border-radius:12px;background:#49683e;color:#fff;font-size:18px;font-weight:700;margin-top:14px}
    button.secondary{background:#6b6b6b}
    .muted{opacity:.85}
    .ok{background:#e8ffe8;border:1px solid #9ad49a;padding:10px;border-radius:10px;margin-top:12px}
    .err{background:#ffecec;border:1px solid #e0a1a1;padding:10px;border-radius:10px;margin-top:12px}
    .small{font-size:13px}
    .topbtns{display:flex;gap:10px;margin-bottom:10px}
    .topbtns button{margin-top:0}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card" id="appCard">
      <h1>Arte Preço Pro</h1>

      <div id="telaAtivacao" style="display:none">
        <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
        <label>Chave</label>
        <input id="licInput" placeholder="Cole sua chave AP-..." />
        <button onclick="ativar()">Ativar</button>
        <div id="ativMsg"></div>
      </div>

      <div id="telaPrincipal" style="display:none">
        <div class="topbtns">
          <button class="secondary" onclick="abrirEmpresa()">Dados da empresa</button>
          <button class="secondary" onclick="abrirCliente()">Dados do cliente</button>
          <button class="secondary" onclick="limparTudo()">Limpar dados</button>
        </div>

        <label>Produto</label>
        <input id="produto" placeholder="Ex: Logo" />

        <label>Custo do Material (R$)</label>
        <input id="custo_material" inputmode="decimal" placeholder="Ex: 10" />

        <div class="row">
          <div>
            <label>Horas Trabalhadas</label>
            <input id="horas_trabalhadas" inputmode="decimal" placeholder="Ex: 4" />
          </div>
          <div>
            <label>Valor da Hora (R$)</label>
            <input id="valor_hora" inputmode="decimal" placeholder="Ex: 30" />
          </div>
        </div>

        <label>Despesas Extras (R$)</label>
        <input id="despesas_extras" inputmode="decimal" placeholder="Ex: 2" />

        <label>Margem de Lucro (%)</label>
        <input id="margem_lucro" inputmode="decimal" placeholder="Ex: 80" />

        <label>Validade (dias)</label>
        <input id="validade_dias" inputmode="numeric" placeholder="Ex: 7" />

        <button onclick="calcular()">Calcular</button>

        <div id="resultado"></div>

        <button id="btnPdf" style="display:none" onclick="baixarPdf()">Gerar PDF</button>
        <button class="secondary" onclick="revalidar()">Revalidar chave</button>
      </div>
    </div>
  </div>

<script>
  function lsGet(k, defVal=""){ try { return localStorage.getItem(k) ?? defVal } catch(e){ return defVal } }
  function lsSet(k,v){ try { localStorage.setItem(k,v) } catch(e){} }
  function num(v){
    if(!v) return 0;
    v = (""+v).trim().replaceAll(".", "").replace(",", ".");
    let n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  }

  function mostrarAtivacao(){
    document.getElementById("telaAtivacao").style.display = "block";
    document.getElementById("telaPrincipal").style.display = "none";
    document.getElementById("ativMsg").innerHTML = "";
    document.getElementById("licInput").value = "";
  }
  function mostrarPrincipal(){
    document.getElementById("telaAtivacao").style.display = "none";
    document.getElementById("telaPrincipal").style.display = "block";
    carregarCampos();
  }

  async function ativar(){
    const chave = document.getElementById("licInput").value.trim();
    const r = await fetch("/api/activate", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({chave})});
    const j = await r.json();
    const box = document.getElementById("ativMsg");
    if(j.ok){
      lsSet("ap_license", chave);
      box.innerHTML = `<div class="ok">✅ ${j.msg}</div>`;
      setTimeout(mostrarPrincipal, 350);
    }else{
      box.innerHTML = `<div class="err">❌ ${j.msg}</div>`;
    }
  }

  async function revalidar(){
    const chave = lsGet("ap_license","");
    if(!chave){ mostrarAtivacao(); return; }
    const r = await fetch("/api/activate", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({chave})});
    const j = await r.json();
    if(!j.ok){
      alert("Chave inválida. Ative novamente.");
      localStorage.removeItem("ap_license");
      mostrarAtivacao();
    }else{
      alert("Chave OK!");
    }
  }

  function salvarCampos(){
    ["produto","custo_material","horas_trabalhadas","valor_hora","despesas_extras","margem_lucro","validade_dias"].forEach(id=>{
      lsSet("f_"+id, document.getElementById(id).value);
    });
  }
  function carregarCampos(){
    ["produto","custo_material","horas_trabalhadas","valor_hora","despesas_extras","margem_lucro","validade_dias"].forEach(id=>{
      document.getElementById(id).value = lsGet("f_"+id,"");
    });
  }

  function abrirEmpresa(){
    const nome = prompt("Nome da empresa:", lsGet("empresa_nome","")) ?? "";
    const tel = prompt("Telefone da empresa:", lsGet("empresa_tel","")) ?? "";
    const email = prompt("E-mail da empresa:", lsGet("empresa_email","")) ?? "";
    const end = prompt("Endereço da empresa:", lsGet("empresa_endereco","")) ?? "";
    lsSet("empresa_nome", nome); lsSet("empresa_tel", tel); lsSet("empresa_email", email); lsSet("empresa_endereco", end);
    alert("Dados da empresa salvos!");
  }

  function abrirCliente(){
    const nome = prompt("Nome do cliente:", lsGet("cliente_nome","")) ?? "";
    const tel = prompt("Telefone do cliente:", lsGet("cliente_tel","")) ?? "";
    const email = prompt("E-mail do cliente:", lsGet("cliente_email","")) ?? "";
    const end = prompt("Endereço do cliente:", lsGet("cliente_endereco","")) ?? "";
    lsSet("cliente_nome", nome); lsSet("cliente_tel", tel); lsSet("cliente_email", email); lsSet("cliente_endereco", end);
    alert("Dados do cliente salvos!");
  }

  function limparTudo(){
    if(!confirm("Deseja limpar todos os dados salvos deste app?")) return;
    [
      "ap_license",
      "empresa_nome","empresa_tel","empresa_email","empresa_endereco",
      "cliente_nome","cliente_tel","cliente_email","cliente_endereco",
      "f_produto","f_custo_material","f_horas_trabalhadas","f_valor_hora","f_despesas_extras","f_margem_lucro","f_validade_dias"
    ].forEach(k=>{ try{ localStorage.removeItem(k) }catch(e){} });
    document.getElementById("resultado").innerHTML = "";
    document.getElementById("btnPdf").style.display = "none";
    mostrarAtivacao();
  }

  let ultimoPayload = null;

  async function calcular(){
    salvarCampos();
    const chave = lsGet("ap_license","");
    if(!chave){ mostrarAtivacao(); return; }

    const payload = {
      chave,
      produto: document.getElementById("produto").value.trim(),
      custo_material: num(document.getElementById("custo_material").value),
      horas_trabalhadas: num(document.getElementById("horas_trabalhadas").value),
      valor_hora: num(document.getElementById("valor_hora").value),
      despesas_extras: num(document.getElementById("despesas_extras").value),
      margem_lucro: num(document.getElementById("margem_lucro").value),
      validade_dias: (document.getElementById("validade_dias").value || "").trim(),
      empresa_nome: lsGet("empresa_nome",""),
      empresa_tel: lsGet("empresa_tel",""),
      empresa_email: lsGet("empresa_email",""),
      empresa_endereco: lsGet("empresa_endereco",""),
      cliente_nome: lsGet("cliente_nome",""),
      cliente_tel: lsGet("cliente_tel",""),
      cliente_email: lsGet("cliente_email",""),
      cliente_endereco: lsGet("cliente_endereco","")
    };

    const r = await fetch("/api/calc", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const j = await r.json();

    if(!j.ok){
      document.getElementById("resultado").innerHTML = `<div class="err">❌ ${j.msg}</div>`;
      document.getElementById("btnPdf").style.display = "none";
      return;
    }

    ultimoPayload = payload;

    document.getElementById("resultado").innerHTML = `
      <div class="ok">
        <div><b>Produto:</b> ${j.produto}</div>
        <div><b>Custo Base:</b> ${j.custo_base_fmt}</div>
        <div style="font-size:26px;margin-top:6px"><b>Preço Final:</b> ${j.preco_final_fmt}</div>
        <div class="muted">Validade: ${j.validade_dias} dia(s)</div>
      </div>
      <div class="small muted" style="margin-top:6px">Obs: a margem não aparece no PDF.</div>
    `;

    document.getElementById("btnPdf").style.display = "block";
  }

  async function baixarPdf(){
    if(!ultimoPayload){ alert("Calcule primeiro."); return; }
    const r = await fetch("/api/pdf", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(ultimoPayload)});
    if(!r.ok){
      alert("Erro ao gerar PDF.");
      return;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orcamento-arte-preco-pro.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=>URL.revokeObjectURL(url), 3000);
  }

  (function init(){
    const chave = lsGet("ap_license","");
    if(!chave) mostrarAtivacao();
    else mostrarPrincipal();
  })();
</script>
</body>
</html>
"""

# ============================================================
# ✅ 6) Rotas
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML)

@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()
    ok, msg = _validar_chave_backend(chave)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/calc", methods=["POST"])
def api_calc():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    ok, msg = _validar_chave_backend(chave)
    if not ok:
        return jsonify({"ok": False, "msg": msg})

    try:
        produto = (data.get("produto") or "").strip() or "Serviço"
        custo_material = float(data.get("custo_material") or 0)
        horas_trabalhadas = float(data.get("horas_trabalhadas") or 0)
        valor_hora = float(data.get("valor_hora") or 0)
        despesas_extras = float(data.get("despesas_extras") or 0)
        margem_lucro = float(data.get("margem_lucro") or 0)
        validade_dias = str(data.get("validade_dias") or "").strip() or "7"

        custo_base, preco_final = calcular_preco_fallback(
            custo_material=custo_material,
            horas_trabalhadas=horas_trabalhadas,
            valor_hora=valor_hora,
            despesas_extras=despesas_extras,
            margem_lucro=margem_lucro,
        )

        return jsonify({
            "ok": True,
            "produto": produto,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "custo_base_fmt": _fmt_brl(custo_base),
            "preco_final_fmt": _fmt_brl(preco_final),
            "validade_dias": validade_dias
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao calcular: {e}"})

@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    ok, msg = _validar_chave_backend(chave)
    if not ok:
        return jsonify({"ok": False, "msg": msg}), 403

    try:
        produto = (data.get("produto") or "").strip() or "Serviço"
        custo_material = float(data.get("custo_material") or 0)
        horas_trabalhadas = float(data.get("horas_trabalhadas") or 0)
        valor_hora = float(data.get("valor_hora") or 0)
        despesas_extras = float(data.get("despesas_extras") or 0)
        margem_lucro = float(data.get("margem_lucro") or 0)
        validade_dias = str(data.get("validade_dias") or "").strip() or "7"

        custo_base, preco_final = calcular_preco_fallback(
            custo_material=custo_material,
            horas_trabalhadas=horas_trabalhadas,
            valor_hora=valor_hora,
            despesas_extras=despesas_extras,
            margem_lucro=margem_lucro
        )

        dados_pdf = {
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "empresa_nome": (data.get("empresa_nome") or "").strip(),
            "empresa_tel": (data.get("empresa_tel") or "").strip(),
            "empresa_email": (data.get("empresa_email") or "").strip(),
            "empresa_endereco": (data.get("empresa_endereco") or "").strip(),
            "cliente_nome": (data.get("cliente_nome") or "").strip(),
            "cliente_tel": (data.get("cliente_tel") or "").strip(),
            "cliente_email": (data.get("cliente_email") or "").strip(),
            "cliente_endereco": (data.get("cliente_endereco") or "").strip(),
            "produto": produto,
            "custo_material": custo_material,
            "horas_trabalhadas": horas_trabalhadas,
            "valor_hora": valor_hora,
            "despesas_extras": despesas_extras,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "validade_dias": validade_dias,
        }

        pdf_bytes = gerar_pdf_bytes(dados_pdf)
        f = io.BytesIO(pdf_bytes)
        f.seek(0)
        return send_file(
            f,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="orcamento-arte-preco-pro.pdf",
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao gerar PDF: {e}"}), 500

# ============================================================
# ✅ Local run (opcional)
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
