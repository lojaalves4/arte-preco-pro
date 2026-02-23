# -*- coding: utf-8 -*-
from flask import Flask, request, render_template_string, jsonify
from datetime import datetime, timedelta

from core.license_core import validar_chave

app = Flask(__name__)

APP_VERSION = "v3-calc"

# ===== Helpers =====
def to_float_br(value: str) -> float:
    s = (value or "").strip()
    if not s:
        return 0.0
    s = s.replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)

def money_br(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular(payload: dict) -> dict:
    produto = (payload.get("produto") or "").strip()
    material = to_float_br(payload.get("material") or "0")
    horas = to_float_br(payload.get("horas") or "0")
    valor_hora = to_float_br(payload.get("valor_hora") or "0")
    despesas = to_float_br(payload.get("despesas") or "0")
    margem = to_float_br(payload.get("margem") or "0")
    validade_dias = int((payload.get("validade_dias") or "7").strip() or "7")

    if not produto:
        return {"ok": False, "msg": "Informe o nome do produto."}

    custo_mao_obra = horas * valor_hora
    custo_total = material + custo_mao_obra + despesas
    preco_final = custo_total + (custo_total * margem / 100.0)

    data_emissao = datetime.now()
    data_validade = data_emissao + timedelta(days=max(0, validade_dias))

    return {
        "ok": True,
        "produto": produto,
        "material": material,
        "horas": horas,
        "valor_hora": valor_hora,
        "despesas": despesas,
        "margem": margem,
        "validade_dias": validade_dias,
        "custo_mao_obra": custo_mao_obra,
        "custo_total": custo_total,
        "preco_final": preco_final,
        "data_emissao": data_emissao.strftime("%d/%m/%Y %H:%M"),
        "data_validade": data_validade.strftime("%d/%m/%Y"),
        "preco_final_fmt": money_br(preco_final),
        "custo_total_fmt": money_br(custo_total),
        "custo_mao_obra_fmt": money_br(custo_mao_obra),
        "material_fmt": money_br(material),
        "valor_hora_fmt": money_br(valor_hora),
        "despesas_fmt": money_br(despesas),
    }

# ===== UI =====
HTML = f"""
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Arte Preço Pro</title>
<style>
body{{font-family:Arial;background:#DCE6D5;margin:0;padding:16px;}}
.card{{background:#EEF3EA;padding:18px;border-radius:14px;max-width:820px;margin:auto;}}
h1{{margin:0 0 6px 0;font-size:34px;}}
small{{color:#4F5A4A;}}
label{{font-weight:bold;display:block;margin-top:12px;margin-bottom:6px;}}
input,textarea{{width:100%;padding:12px;font-size:16px;border-radius:10px;border:1px solid #aaa;box-sizing:border-box;}}
textarea{{min-height:90px;}}
.btn{{width:100%;padding:14px;margin-top:14px;font-size:16px;border:none;border-radius:10px;font-weight:bold;}}
.btn-main{{background:#4E6B3E;color:white;}}
.btn-gray{{background:#666;color:white;}}
.btn-red{{background:#B00020;color:white;}}
.msg{{margin-top:12px;padding:12px;background:#fff;border-radius:10px;}}
.row{{display:flex;gap:10px;flex-wrap:wrap;}}
.row .col{{flex:1;min-width:160px;}}
.big{{font-size:22px;font-weight:bold;}}
hr{{border:none;border-top:1px solid rgba(0,0,0,.15);margin:16px 0;}}
</style>
</head>
<body>
<div class="card">
  <h1>Arte Preço Pro</h1>
  <small>{APP_VERSION}</small>

  <!-- Ativação -->
  <div id="ativacao">
    <p>Cole sua chave AP-...</p>
    <input id="keyInput" placeholder="AP-..." />
    <button class="btn btn-main" onclick="ativar()">Ativar</button>
    <div id="msg" class="msg"></div>
  </div>

  <!-- App -->
  <div id="app" style="display:none;">
    <div class="msg">✅ <b id="status"></b></div>

    <hr>

    <div class="row">
      <div class="col">
        <label>Produto</label>
        <input id="produto" placeholder="Ex: Logo Barber Prime" />
      </div>
      <div class="col">
        <label>Validade (dias)</label>
        <input id="validade_dias" value="7" inputmode="numeric" />
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>Custo do Material (R$)</label>
        <input id="material" placeholder="0,00" inputmode="decimal" />
      </div>
      <div class="col">
        <label>Horas Trabalhadas</label>
        <input id="horas" placeholder="0" inputmode="decimal" />
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>Valor da Hora (R$)</label>
        <input id="valor_hora" placeholder="0,00" inputmode="decimal" />
      </div>
      <div class="col">
        <label>Despesas Extras (R$)</label>
        <input id="despesas" placeholder="0,00" inputmode="decimal" />
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label>Margem de Lucro (%)</label>
        <input id="margem" placeholder="0" inputmode="decimal" />
      </div>
    </div>

    <label>Observações</label>
    <textarea id="obs" placeholder="(opcional)"></textarea>

    <button class="btn btn-main" onclick="calcularPreco()">Calcular</button>

    <div id="resultado" class="msg" style="display:none;"></div>

    <div class="row" style="margin-top:10px;">
      <button class="btn btn-gray" style="flex:1;" onclick="fechar()">Fechar</button>
      <button class="btn btn-red" style="flex:1;" onclick="desativar()">Desativar</button>
    </div>

    <div id="msg2" class="msg" style="display:none;"></div>
  </div>
</div>

<script>
const STORAGE_KEY = "arte_preco_key";

function ativar(){{
  const key = document.getElementById("keyInput").value.trim();
  fetch("/validate", {{
    method:"POST",
    headers:{{"Content-Type":"application/json"}},
    body:JSON.stringify({{key:key}})
  }})
  .then(r=>r.json())
  .then(data=>{{
    if(data.ok){{
      localStorage.setItem(STORAGE_KEY, key);
      mostrarApp(data.msg);
    }} else {{
      document.getElementById("msg").innerText = data.msg;
    }}
  }})
  .catch(()=> {{
    document.getElementById("msg").innerText = "Erro de conexão ao validar.";
  }});
}}

function mostrarApp(msg){{
  document.getElementById("ativacao").style.display="none";
  document.getElementById("app").style.display="block";
  document.getElementById("status").innerText = msg;
}}

function fechar(){{
  const el = document.getElementById("msg2");
  el.style.display = "block";
  el.innerText = "Pode fechar o app (Home/Recentes). A ativação ficará salva.";
}}

function desativar(){{
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
}}

function payloadCalc(){{
  return {{
    produto: document.getElementById("produto").value,
    material: document.getElementById("material").value,
    horas: document.getElementById("horas").value,
    valor_hora: document.getElementById("valor_hora").value,
    despesas: document.getElementById("despesas").value,
    margem: document.getElementById("margem").value,
    validade_dias: document.getElementById("validade_dias").value,
    obs: document.getElementById("obs").value
  }};
}}

function calcularPreco(){{
  const key = localStorage.getItem(STORAGE_KEY) || "";
  fetch("/calc", {{
    method:"POST",
    headers:{{"Content-Type":"application/json"}},
    body:JSON.stringify({{ key:key, ...payloadCalc() }})
  }})
  .then(r=>r.json())
  .then(data=>{{
    const box = document.getElementById("resultado");
    box.style.display = "block";
    if(!data.ok){{
      box.innerHTML = "<b>Erro:</b> " + (data.msg || "Falha ao calcular.");
      return;
    }}
    box.innerHTML = `
      <div class="big">Preço Final: ${data.preco_final_fmt}</div>
      <div style="margin-top:8px;">
        <b>Custo total:</b> ${data.custo_total_fmt}<br>
        <b>Mão de obra:</b> ${data.horas} h x ${data.valor_hora_fmt} = ${data.custo_mao_obra_fmt}<br>
        <b>Material:</b> ${data.material_fmt}<br>
        <b>Despesas:</b> ${data.despesas_fmt}<br>
        <b>Emissão:</b> ${data.data_emissao}<br>
        <b>Válido até:</b> ${data.data_validade} (${data.validade_dias} dias)
      </div>
    `;
  }})
  .catch(()=> {{
    const box = document.getElementById("resultado");
    box.style.display = "block";
    box.innerHTML = "<b>Erro:</b> Não consegui calcular (sem conexão).";
  }});
}}

window.onload = function(){{
  const saved = localStorage.getItem(STORAGE_KEY);
  if(saved){{
    fetch("/validate", {{
      method:"POST",
      headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{key:saved}})
    }})
    .then(r=>r.json())
    .then(data=>{{
      if(data.ok){{
        mostrarApp(data.msg);
      }} else {{
        localStorage.removeItem(STORAGE_KEY);
      }}
    }})
    .catch(()=>{{}});
  }}
}}
</script>
</body>
</html>
"""

# ===== Routes =====
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True) or {}
    key = (data.get("key") or "").strip()
    ok, msg = validar_chave(key)
    return jsonify({"ok": bool(ok), "msg": msg})

@app.route("/calc", methods=["POST"])
def calc():
    data = request.get_json(force=True) or {}
    key = (data.get("key") or "").strip()

    ok, msg = validar_chave(key)
    if not ok:
        return jsonify({"ok": False, "msg": "Chave inválida ou não ativada. Desative e ative novamente."})

    r = calcular(data)
    return jsonify(r)

if __name__ == "__main__":
    app.run()
