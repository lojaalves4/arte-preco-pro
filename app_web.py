# -*- coding: utf-8 -*-
import os
import json
import hashlib
from flask import Flask, request, redirect, make_response, render_template_string

# ===== Import da licença (chave única) =====
from core.license_core import validar_chave

APP_NAME = "Arte Preço Pro"

app = Flask(__name__)

# Cookie onde salvamos a chave no navegador (funciona no celular e PC)
COOKIE_KEY = "arte_preco_license"
COOKIE_DAYS = 3650

HTML_ACTIVATE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Ativação - Arte Preço Pro</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;background:#DCE6D5;margin:0;padding:24px;}
    .box{max-width:720px;margin:0 auto;background:#EEF3EA;border-radius:14px;padding:20px;border:1px solid #c7d3c0;}
    h1{margin:0 0 10px 0;font-size:26px;}
    p{margin:6px 0;color:#2b2b2b}
    input{width:100%;padding:14px;font-size:16px;border-radius:10px;border:1px solid #aab8a3;}
    button{width:100%;margin-top:12px;padding:14px;font-size:18px;border-radius:12px;border:none;background:#4E6B3E;color:#fff;font-weight:700;}
    .msg{margin-top:12px;padding:12px;border-radius:10px;background:#fff;border:1px solid #d1d1d1;}
    .row{display:flex;gap:10px;margin-top:10px;}
    .btn2{flex:1;background:#666;}
    .btn3{flex:1;background:#6E8B57;}
    small{color:#4F5A4A}
    code{word-break:break-all}
  </style>
</head>
<body>
  <div class="box">
    <h1>Ativação do Arte Preço Pro</h1>
    <p>Cole a chave <b>AP-...</b> (uma vez). O app lembra automaticamente.</p>

    <form method="POST" action="/activate">
      <input name="license_key" placeholder="Cole sua chave AP-..." value="{{prefill}}" autocomplete="off" />
      <button type="submit">Ativar</button>
    </form>

    <div class="row">
      <form method="POST" action="/logout" style="flex:1;">
        <button class="btn2" type="submit">Sair</button>
      </form>

      <form method="GET" action="/" style="flex:1;">
        <button class="btn3" type="submit">Atualizar</button>
      </form>
    </div>

    {% if msg %}
      <div class="msg">{{msg}}</div>
    {% endif %}

    {% if debug %}
      <div class="msg">
        <b>Debug:</b><br/>
        <small>Chave recebida:</small> <code>{{debug_key}}</code><br/>
        <small>Resultado:</small> <code>{{debug_result}}</code>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""

HTML_APP = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Arte Preço Pro</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;background:#DCE6D5;margin:0;padding:24px;}
    .box{max-width:860px;margin:0 auto;background:#EEF3EA;border-radius:14px;padding:20px;border:1px solid #c7d3c0;}
    h1{margin:0 0 12px 0;}
    .ok{background:#fff;border:1px solid #d1d1d1;padding:12px;border-radius:10px;margin-bottom:14px;}
    a{color:#2b2b2b}
    button{padding:12px 16px;border-radius:10px;border:none;background:#666;color:#fff;font-weight:700;}
  </style>
</head>
<body>
  <div class="box">
    <h1>Arte Preço Pro</h1>
    <div class="ok">✅ {{status}}</div>
    <p>Seu app está liberado. (A próxima tela/funcionalidades podem ficar aqui.)</p>

    <form method="POST" action="/logout">
      <button type="submit">Sair</button>
    </form>
  </div>
</body>
</html>
"""

def _get_cookie_key(req) -> str:
    return (req.cookies.get(COOKIE_KEY) or "").strip()

def _device_fingerprint(req) -> str:
    # NÃO é “travar por aparelho”. É só um identificador leve para debug (não impede ativação).
    ua = (req.headers.get("User-Agent") or "")
    ip = (req.headers.get("X-Forwarded-For") or req.remote_addr or "")
    raw = f"{ua}|{ip}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()[:16]

@app.get("/")
def index():
    # Se já tem cookie, valida e entra
    saved = _get_cookie_key(request)
    if saved:
        ok, msg = validar_chave(saved)
        if ok:
            return render_template_string(HTML_APP, status=msg)
        # se cookie inválido, cai na ativação e mostra o motivo
        return render_template_string(HTML_ACTIVATE, msg=f"Chave salva inválida: {msg}", prefill="", debug=False)

    # sem cookie -> tela de ativação
    return render_template_string(HTML_ACTIVATE, msg="", prefill="", debug=False)

@app.post("/activate")
def activate():
    try:
        key = (request.form.get("license_key") or "").strip()

        if not key:
            return render_template_string(HTML_ACTIVATE, msg="Cole a chave AP-...", prefill="", debug=False)

        # valida (chave única)
        ok, msg = validar_chave(key)

        if not ok:
            # mostra motivo real
            return render_template_string(HTML_ACTIVATE, msg=msg, prefill=key, debug=True, debug_key=key, debug_result=(ok, msg))

        # salva em cookie por muitos anos
        resp = make_response(redirect("/"))
        resp.set_cookie(COOKIE_KEY, key, max_age=COOKIE_DAYS * 24 * 3600, httponly=False, samesite="Lax")
        return resp

    except Exception as e:
        # Mostra erro real em tela (para nunca ficar no escuro)
        return render_template_string(
            HTML_ACTIVATE,
            msg=f"Erro ao ativar: {type(e).__name__}: {e}",
            prefill=(request.form.get('license_key') or ""),
            debug=True,
            debug_key=(request.form.get("license_key") or ""),
            debug_result="EXCEPTION"
        )

@app.post("/logout")
def logout():
    # Apaga o cookie (Sair funciona de verdade)
    resp = make_response(redirect("/"))
    resp.set_cookie(COOKIE_KEY, "", expires=0)
    return resp

if __name__ == "__main__":
    # local
    app.run(host="0.0.0.0", port=5000, debug=True)
