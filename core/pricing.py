# core/pricing.py

from datetime import datetime, timedelta


def calcular_preco(produto, material, horas, valor_hora, despesas, margem, validade_dias=7):

    custo_mao_obra = horas * valor_hora
    custo_total = material + custo_mao_obra + despesas
    preco_final = custo_total + (custo_total * margem / 100.0)

    data_emissao = datetime.now()
    data_validade = data_emissao + timedelta(days=max(0, validade_dias))

    return {
        "produto": produto,
        "material": material,
        "horas": horas,
        "valor_hora": valor_hora,
        "custo_mao_obra": custo_mao_obra,
        "despesas": despesas,
        "custo_total": custo_total,
        "preco_final": preco_final,
        "data_emissao": data_emissao.strftime("%d/%m/%Y %H:%M"),
        "data_validade": data_validade.strftime("%d/%m/%Y"),
        "validade_dias": validade_dias,
    }