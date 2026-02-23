# -*- coding: utf-8 -*-
from flask import Flask, request, render_template_string
from core.license_core import validar_chave

app = Flask(__name__)

APP_VERSION = "v2-localstorage"

HTML = f"""
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Arte Preço Pro</title>
<style>
body{{font-family:Arial;background:#DCE6D5;margin:0;padding:20px;}}
.box{{background:#EEF3EA;padding:20px;border-radius:12px;max-width:720px;margin:auto;}}
h1{{margin:0 0 10px 0;}}
small{{color:#4F5A4A;}}
input{{width:100%;padding:12px;font-size:16px;border-radius:8px;border:1px solid #aaa;}}
.btn{{width:100%;padding:14px;margin-top:10px;font-size:16px;border:none;border-radius:8px;font-weight:bold;}}
.btn-main{{background:#4E6B3E;color:white;}}
.btn-gray{{background:#666;color:white;}}
.btn-red{{background:#B00020;color:white;}}
.msg{{margin-top:10px;padding:10px;background:#fff;border-radius:8px;}}
.row{{display:flex;gap:10px;}}
.row button{{flex:1;}}
</style>
</head>
<body>
<div class="box">
  <h1>Arte Preço Pro</h1>
  <small>{APP_VERSION}</small>

  <div id="ativacao">
    <p>Cole sua chave AP-...</p>
    <input id="keyInput" placeholder="AP-..." />
    <button class="btn btn-main" onclick="ativar()">Ativar</button>
    <div id="msg" class="msg"></div>
  </div>

  <div id="app" style="display:none;">
    <div class="msg">✅ <b id="status"></b></div>
    <p>Para sair do app sem perder a ativação, use o botão Home do celular.</p>

    <div class="row">
      <button class="btn btn-gray" onclick="fechar()">Fechar</button>
      <button class="btn btn-red" onclick="desativar()">Desativar</button>
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
  // Não apaga licença. Só orienta o usuário a fechar o app.
  const el = document.getElementById("msg2");
  el.style.display = "block";
  el.innerText = "Pode fechar o app (Home/Recentes). A ativação ficará salva.";
}}

function desativar(){{
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
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
        // Se a chave salva ficou inválida, remove
        localStorage.removeItem(STORAGE_KEY);
      }}
    }})
    .catch(()=>{{ /* se falhar, mantém tela de ativação */ }});
  }}
}}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True) or {}
    key = (data.get("key") or "").strip()
    ok, msg = validar_chave(key)
    return {"ok": bool(ok), "msg": msg}

if __name__ == "__main__":
    app.run()
