# app_web.py  (VERSÃO PROFISSIONAL COM DADOS DA EMPRESA)

from flask import Flask, request, jsonify, send_from_directory, make_response
from datetime import datetime
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    from core.license_core import validar_chave
except Exception:
    validar_chave = None

app = Flask(__name__, static_folder="static")

# =========================================
# DADOS DA EMPRESA (PADRÃO)
# O CLIENTE QUE COMPRAR PODE EDITAR ISSO
# =========================================
EMPRESA_NOME = os.getenv("EMPRESA_NOME", "PJA Studio Design")
EMPRESA_CONTATO = os.getenv("EMPRESA_CONTATO", "(24) 99999-9999")
EMPRESA_EMAIL = os.getenv("EMPRESA_EMAIL", "contato@seudominio.com")
EMPRESA_ENDERECO = os.getenv("EMPRESA_ENDERECO", "Rio de Janeiro - RJ")


# ============================
# Helpers
# ============================
def brl(valor: float) -> str:
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def calcular_preco_simples(custo_material, horas, valor_hora, despesas, margem):
    custo_base = float(custo_material) + (float(horas) * float(valor_hora)) + float(despesas)
    preco_final = custo_base * (1.0 + (float(margem) / 100.0))
    return custo_base, preco_final


# ============================
# GERAR PDF PROFISSIONAL
# ============================
def gerar_pdf_orcamento(dados: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    y = h - 50

    # EMPRESA
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, EMPRESA_NOME)
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Contato: {EMPRESA_CONTATO}")
    y -= 14
    c.drawString(40, y, f"E-mail: {EMPRESA_EMAIL}")
    y -= 14
    c.drawString(40, y, f"Endereço: {EMPRESA_ENDERECO}")

    y -= 30
    c.line(40, y, w - 40, y)

    y -= 30
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "ORÇAMENTO")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    y -= 25

    # CLIENTE
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Dados do Cliente")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Nome: {dados.get('cliente_nome','')}")
    y -= 16
    c.drawString(40, y, f"Contato: {dados.get('cliente_contato','')}")
    y -= 16
    c.drawString(40, y, f"Endereço: {dados.get('cliente_endereco','')}")
    y -= 30

    # SERVIÇO
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Detalhes do Serviço")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Produto: {dados.get('produto','')}")
    y -= 16
    c.drawString(40, y, f"Custo Base: {dados.get('custo_base_fmt','')}")
    y -= 25

    # TOTAL DESTACADO
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, y, f"Preço Final: {dados.get('preco_final_fmt','')}")
    y -= 30

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Validade da proposta: {dados.get('validade',0)} dia(s)")

    y -= 40
    c.line(40, y, w - 40, y)

    y -= 20
    c.setFont("Helvetica", 9)
    c.drawString(40, y, "Gerado pelo sistema Arte Preço Pro")

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
# API
# ============================
PDF_CACHE = {}


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


@app.post("/api/calcular")
def api_calcular():
    data = request.get_json(silent=True) or {}

    produto = data.get("produto","")
    custo_material = float(data.get("custo_material") or 0)
    horas = float(data.get("horas") or 0)
    valor_hora = float(data.get("valor_hora") or 0)
    despesas = float(data.get("despesas") or 0)
    margem = float(data.get("margem") or 0)
    validade = int(data.get("validade") or 0)

    cliente_nome = data.get("cliente_nome","")
    cliente_contato = data.get("cliente_contato","")
    cliente_endereco = data.get("cliente_endereco","")

    custo_base, preco_final = calcular_preco_simples(
        custo_material, horas, valor_hora, despesas, margem
    )

    custo_base_fmt = brl(custo_base)
    preco_final_fmt = brl(preco_final)

    key_pdf = str(datetime.now().timestamp())

    PDF_CACHE[key_pdf] = {
        "cliente_nome": cliente_nome,
        "cliente_contato": cliente_contato,
        "cliente_endereco": cliente_endereco,
        "produto": produto,
        "custo_base_fmt": custo_base_fmt,
        "preco_final_fmt": preco_final_fmt,
        "validade": validade,
    }

    return jsonify(
        ok=True,
        custo_base_fmt=custo_base_fmt,
        preco_final_fmt=preco_final_fmt,
        validade=validade,
        key_pdf=key_pdf
    )


@app.get("/api/pdf")
def api_pdf():
    key = request.args.get("key")
    dados = PDF_CACHE.get(key)

    if not dados:
        return "PDF não encontrado", 404

    pdf_bytes = gerar_pdf_orcamento(dados)
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "attachment; filename=orcamento.pdf"
    return resp


if __name__ == "__main__":
    app.run(debug=True)
