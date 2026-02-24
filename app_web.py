# app_web.py - VERSÃO SEGURA

from flask import Flask, request, jsonify, make_response
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)


def brl(valor):
    valor = float(valor)
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def calcular(custo_material, horas, valor_hora, despesas, margem):
    custo_base = custo_material + (horas * valor_hora) + despesas
    preco_final = custo_base * (1 + margem / 100)
    return custo_base, preco_final


@app.route("/")
def home():
    return """
    <h1>Arte Preço Pro</h1>
    <p>Sistema ativo.</p>
    """


@app.route("/api/calcular", methods=["POST"])
def api_calcular():
    data = request.json

    custo_material = float(data.get("custo_material", 0))
    horas = float(data.get("horas", 0))
    valor_hora = float(data.get("valor_hora", 0))
    despesas = float(data.get("despesas", 0))
    margem = float(data.get("margem", 0))

    custo_base, preco_final = calcular(
        custo_material, horas, valor_hora, despesas, margem
    )

    return jsonify({
        "ok": True,
        "custo_base": brl(custo_base),
        "preco_final": brl(preco_final)
    })


@app.route("/api/pdf", methods=["POST"])
def api_pdf():
    data = request.json

    custo_material = float(data.get("custo_material", 0))
    horas = float(data.get("horas", 0))
    valor_hora = float(data.get("valor_hora", 0))
    despesas = float(data.get("despesas", 0))
    margem = float(data.get("margem", 0))

    custo_base, preco_final = calcular(
        custo_material, horas, valor_hora, despesas, margem
    )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 50, "Orçamento - Arte Preço Pro")

    c.setFont("Helvetica", 12)
    c.drawString(40, h - 100, f"Custo Base: {brl(custo_base)}")
    c.drawString(40, h - 130, f"Preço Final: {brl(preco_final)}")

    c.save()
    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=orcamento.pdf"

    return response
