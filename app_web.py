# ============================================================
# ROTAS PRINCIPAIS
# ============================================================

@app.route("/")
def index():
    return HTML

@app.post("/api/calc")
def api_calc():
    data = request.json
    ok, msg = validar_licenca(data.get("key"))
    if not ok:
        return Response(msg, status=403)

    custo_material = to_float(data.get("custo_material"))
    horas = to_float(data.get("horas"))
    valor_hora = to_float(data.get("valor_hora"))
    despesas = to_float(data.get("despesas"))
    margem = to_float(data.get("margem"))

    custo_base, preco_final = calc_preco(
        custo_material, horas, valor_hora, despesas, margem
    )

    return {
        "custo_base_fmt": money_br(custo_base),
        "preco_final_fmt": money_br(preco_final)
    }

@app.get("/health")
def health():
    return "ok"
