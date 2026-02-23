# -*- coding: utf-8 -*-
from flask import Flask, request, render_template_string
from core.license_core import validar_chave

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Arte Preço Pro</title>
<style>
body{font-family:Arial;background:#DCE6D5;margin:0;padding:20px;}
.box{background:#EEF3EA;padding:20px;border-radius:12px;max-width:700px;margin:auto;}
input{width:100%;padding:12px;font-size:16px;border-radius:8px;border:1px solid #aaa;}
button{width:100%;padding:14px;margin-top:10px;font-size:16px;border:none;border-radius:8px;background:#4E6B3E;color:white;font-weight:bold;}
.msg{margin-top:10px;padding:10px;background:#fff;border-radius:8px;}
</style>
</head>
<body>
<div class="box">
<h1>Arte Preço Pro</h1>

<div id="ativacao">
<p>Cole sua chave AP-...</p>
<input id="keyInput" placeholder="AP-..." />
<button onclick="ativar()">Ativar</button>
<div id="msg" class="msg"></div>
</div>

<div id="app" style="display:none;">
<p>✅ <b id="status"></b></p>
<button onclick="logout()">Sair</button>
</div>

</div>

<script>
function ativar(){
    const key = document.getElementById("keyInput").value.trim();
    fetch("/validate",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({key:key})
    })
    .then(r=>r.json())
    .then(data=>{
        if(data.ok){
            localStorage.setItem("arte_preco_key", key);
            mostrarApp(data.msg);
        }else{
            document.getElementById("msg").innerText = data.msg;
        }
    });
}

function mostrarApp(msg){
    document.getElementById("ativacao").style.display="none";
    document.getElementById("app").style.display="block";
    document.getElementById("status").innerText = msg;
}

function logout(){
    localStorage.removeItem("arte_preco_key");
    location.reload();
}

window.onload=function(){
    const saved = localStorage.getItem("arte_preco_key");
    if(saved){
        fetch("/validate",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({key:saved})
        })
        .then(r=>r.json())
        .then(data=>{
            if(data.ok){
                mostrarApp(data.msg);
            }
        });
    }
}
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json()
    key = data.get("key","").strip()
    ok, msg = validar_chave(key)
    return {"ok": ok, "msg": msg}

if __name__ == "__main__":
    app.run()
