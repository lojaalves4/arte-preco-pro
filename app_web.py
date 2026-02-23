import os
from flask import Flask, request, jsonify, render_template_string

# Importa seu validador
from core.license_core import validar_chave

# Tenta importar cálculo do core, mas não depende dele
try:
    from core.pricing import calcular_preco  # opcional
except Exception:
    calcular_preco = None


app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---------------------------
# Utilitários
# ---------------------------
def _to_float(v):
    try:
        if v is None:
            return 0.0
        if isinstance(v, str):
            v = v.replace(".", "").replace(",", ".").strip()
        return float(v)
    except Exception:
        return 0.0


def _fmt_brl(valor: float) -> str:
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _calcular_local(payload: dict) -> dict:
    produto = (payload.get("produto") or "").strip()
    custo_material = _to_float(payload.get("custo_material"))
    horas = _to_float(payload.get("horas"))
    valor_hora = _to_float(payload.get("valor_hora"))
    despesas_extras = _to_float(payload.get("despesas_extras"))
    margem_lucro = _to_float(payload.get("margem_lucro"))  # %
    validade_dias = int(_to_float(payload.get("validade_dias") or 7))

    custo_base = custo_material + (horas * valor_hora) + despesas_extras
    preco_final = custo_base * (1.0 + (margem_lucro / 100.0))

    return {
        "produto": produto,
        "custo_base": round(custo_base, 2),
        "preco_final": round(preco_final, 2),
        "custo_base_fmt": _fmt_brl(custo_base),
        "preco_final_fmt": _fmt_brl(preco_final),
        "validade_dias": validade_dias,
        "fonte_calculo": "fallback_interno",
    }


def _normalizar_resultado(resultado: dict) -> dict:
    if not isinstance(resultado, dict):
        return {"resultado": str(resultado), "fonte_calculo": "core_pricing"}

    # garante campos padrão e formatações
    if "custo_base" in resultado and "custo_base_fmt" not in resultado:
        resultado["custo_base_fmt"] = _fmt_brl(_to_float(resultado.get("custo_base")))
    if "preco_final" in resultado and "preco_final_fmt" not in resultado:
        resultado["preco_final_fmt"] = _fmt_brl(_to_float(resultado.get("preco_final")))
    if "validade_dias" not in resultado:
        resultado["validade_dias"] = 7
    resultado.setdefault("fonte_calculo", "core_pricing")
    return resultado


# ---------------------------
# ROTAS API
# ---------------------------
@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/ativar")
def api_ativar():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    if not chave:
        return jsonify({"ok": False, "msg": "Cole a chave AP-..."}), 400

    ok, msg = validar_chave(chave)  # ✅ 1 parâmetro
    return jsonify({"ok": bool(ok), "msg": msg})


@app.post("/api/calcular")
def api_calcular():
    data = request.get_json(silent=True) or {}
    chave = (data.get("chave") or "").strip()

    if not chave:
        return jsonify({"ok": False, "msg": "Chave não informada."}), 400

    ok, msg = validar_chave(chave)
    if not ok:
        return jsonify({"ok": False, "msg": msg}), 403

    # Tenta cálculo do core.pricing, mas se der QUALQUER erro, usa fallback
    try:
        if callable(calcular_preco):
            try:
                resultado = calcular_preco(
                    produto=(data.get("produto") or "").strip(),
                    custo_material=_to_float(data.get("custo_material")),
                    horas=_to_float(data.get("horas")),
                    valor_hora=_to_float(data.get("valor_hora")),
                    despesas_extras=_to_float(data.get("despesas_extras")),
                    margem_lucro=_to_float(data.get("margem_lucro")),
                    validade_dias=int(_to_float(data.get("validade_dias") or 7)),
                )
                resultado = _normalizar_resultado(resultado)
                return jsonify({"ok": True, "msg": "Cálculo concluído.", "data": resultado})
            except Exception as e_core:
                # cai para fallback, mas avisa o motivo
                fb = _calcular_local(data)
                fb["aviso"] = f"Core pricing falhou e usei fallback. Motivo: {e_core}"
                return jsonify({"ok": True, "msg": "Cálculo concluído (fallback).", "data": fb})

        # sem core.pricing -> fallback
        fb = _calcular_local(data)
        fb["aviso"] = "core.pricing não encontrado; usei cálculo interno."
        return jsonify({"ok": True, "msg": "Cálculo concluído (fallback).", "data": fb})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao calcular: {e}"}), 500


# ---------------------------
# PÁGINA WEB (PWA)
# ---------------------------
HTML = r"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Arte Preço Pro</title>

  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4E6B3E">

  <style>
    body { font-family: Arial, sans-serif; background: #DCE6D5; margin: 0; padding: 0; }
    .wrap { max-width: 680px; margin: 0 auto; padding: 24px; }
    .card { background: #E9F0E2; border-radius: 12px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
    h1 { margin: 0 0 14px 0; font-size: 34px; }
    label { display:block; margin-top: 12px; font-weight: 700; }
    input { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #bbb; font-size: 16px; }
    button { width: 100%; padding: 14px; margin-top: 16px; border-radius: 10px; border: 0; font-size: 18px; cursor:pointer; }
    .btn { background: #4E6B3E; color: #fff; }
    .btn2 { background: #6A6A6A; color: #fff; }
    .msg { margin-top: 12px; padding: 12px; border-radius: 10px; background: #fff; border: 1px solid #d0d0d0; }
    .ok { border-color: #2f8f2f; }
    .err { border-color: #c73333; }
    .row { display:flex; gap: 10px; }
    .row > div { flex: 1; }
    .big { font-size: 22px; font-weight: 900; margin-top: 12px; }
    .muted { color:#333; opacity: .85; }
    .small { font-size: 13px; opacity: .85; margin-top: 8px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Arte Preço Pro</h1>

      <div id="box_ativacao">
        <div class="muted">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>

        <label>Chave</label>
        <input id="inp_chave" placeholder="Cole sua chave AP-..." autocomplete="off"/>

        <button class="btn" id="btn_ativar">Ativar</button>

        <div id="msg_ativar" class="msg" style="display:none;"></div>
      </div>

      <div id="box_app" style="display:none;">
        <div id="status_ok" class="msg ok" style="display:none;"></div>

        <label>Produto</label>
        <input id="produto" placeholder="Ex: Banner / Logo / Cartão"/>

        <label>Custo do Material (R$)</label>
        <input id="custo_material" inputmode="decimal" placeholder="Ex: 12,50"/>

        <div class="row">
          <div>
            <label>Horas Trabalhadas</label>
            <input id="horas" inputmode="decimal" placeholder="Ex: 1,5"/>
          </div>
          <div>
            <label>Valor da Hora (R$)</label>
            <input id="valor_hora" inputmode="decimal" placeholder="Ex: 35"/>
          </div>
        </div>

        <label>Despesas Extras (R$)</label>
        <input id="despesas_extras" inputmode="decimal" placeholder="Ex: 5,00"/>

        <label>Margem de Lucro (%)</label>
        <input id="margem_lucro" inputmode="decimal" placeholder="Ex: 40"/>

        <label>Validade (dias)</label>
        <input id="validade_dias" inputmode="numeric" value="7"/>

        <button class="btn" id="btn_calcular">Calcular</button>

        <div id="resultado" class="msg" style="display:none;"></div>

        <div class="row">
          <div><button class="btn2" id="btn_sair">Sair</button></div>
          <div><button class="btn" id="btn_revalidar">Revalidar chave</button></div>
        </div>

        <div id="msg_app" class="msg" style="display:none;"></div>
      </div>

    </div>
  </div>

<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
  }

  function showMsg(el, text, ok){
    el.style.display = "block";
    el.classList.remove("ok","err");
    el.classList.add(ok ? "ok" : "err");
    el.textContent = text;
  }

  function getKey(){ return localStorage.getItem("AP_KEY") || ""; }
  function setKey(k){ localStorage.setItem("AP_KEY", k); }
  function clearKey(){ localStorage.removeItem("AP_KEY"); }

  function showApp(msg){
    document.getElementById("box_ativacao").style.display = "none";
    document.getElementById("box_app").style.display = "block";
    const st = document.getElementById("status_ok");
    showMsg(st, msg || "✅ Ativado.", true);
  }

  function showActivation(){
    document.getElementById("box_ativacao").style.display = "block";
    document.getElementById("box_app").style.display = "none";
  }

  async function postJSON(url, body){
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    const j = await r.json().catch(()=>({ok:false,msg:"Resposta inválida"}));
    return { status: r.status, data: j };
  }

  async function ativar(chave){
    const msg = document.getElementById("msg_ativar");
    const res = await postJSON("/api/ativar", { chave });
    if(res.data.ok){
      setKey(chave);
      showApp(res.data.msg || "✅ Ativado.");
      msg.style.display = "none";
    } else {
      showMsg(msg, res.data.msg || "Chave inválida.", false);
    }
  }

  async function revalidar(){
    const chave = getKey();
    const msg = document.getElementById("msg_app");
    if(!chave){ showActivation(); return; }

    const res = await postJSON("/api/ativar", { chave });
    if(res.data.ok){
      showMsg(msg, res.data.msg || "✅ Chave ok.", true);
    } else {
      clearKey();
      showActivation();
      showMsg(document.getElementById("msg_ativar"), res.data.msg || "Chave inválida.", false);
    }
  }

  async function calcular(){
    const chave = getKey();
    const out = document.getElementById("resultado");
    const msg = document.getElementById("msg_app");

    if(!chave){ showActivation(); return; }

    const payload = {
      chave: chave,
      produto: document.getElementById("produto").value,
      custo_material: document.getElementById("custo_material").value,
      horas: document.getElementById("horas").value,
      valor_hora: document.getElementById("valor_hora").value,
      despesas_extras: document.getElementById("despesas_extras").value,
      margem_lucro: document.getElementById("margem_lucro").value,
      validade_dias: document.getElementById("validade_dias").value
    };

    const res = await postJSON("/api/calcular", payload);

    if(res.data.ok){
      const d = res.data.data || {};
      out.style.display = "block";
      out.classList.remove("err"); out.classList.add("ok");

      const aviso = d.aviso ? `<div class="small">⚠️ ${d.aviso}</div>` : "";
      const fonte = d.fonte_calculo ? `<div class="small">Fonte: ${d.fonte_calculo}</div>` : "";

      out.innerHTML = `
        <div><b>Produto:</b> ${d.produto || "-"}</div>
        <div><b>Custo Base:</b> ${d.custo_base_fmt || d.custo_base || "-"}</div>
        <div class="big">Preço Final: ${d.preco_final_fmt || d.preco_final || "-"}</div>
        <div class="muted">Validade: ${d.validade_dias || 7} dia(s)</div>
        ${fonte}
        ${aviso}
      `;
      msg.style.display = "none";
      return;
    }

    // erro
    if(res.status === 403){
      clearKey();
      showActivation();
      showMsg(document.getElementById("msg_ativar"), res.data.msg || "Chave inválida.", false);
      return;
    }

    showMsg(msg, res.data.msg || "Erro ao calcular.", false);
  }

  document.getElementById("btn_ativar").addEventListener("click", ()=>{
    const chave = document.getElementById("inp_chave").value.trim();
    ativar(chave);
  });

  document.getElementById("btn_calcular").addEventListener("click", calcular);

  document.getElementById("btn_sair").addEventListener("click", ()=>{
    showActivation();
    document.getElementById("inp_chave").value = getKey();
    showMsg(document.getElementById("msg_ativar"), "Chave salva. Se quiser, clique Ativar novamente.", true);
  });

  document.getElementById("btn_revalidar").addEventListener("click", revalidar);

  window.addEventListener("load", async ()=>{
    const chave = getKey();
    if(chave){
      document.getElementById("inp_chave").value = chave;
      const res = await postJSON("/api/ativar", { chave });
      if(res.data.ok){
        showApp("✅ Chave reconhecida. App liberado.");
      } else {
        clearKey();
        showActivation();
      }
    }
  });
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(HTML)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
