from flask import Flask, request, render_template_string, send_from_directory, redirect, url_for, session, jsonify
from core.pricing import calcular_preco
from core.license_core import validar_chave

app = Flask(__name__)
app.secret_key = "ARTEPRECO_SECRET_2026_SUPER"

# =========================
# PWA
# =========================
@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

# =========================
# API ATIVAÇÃO (COM DEVICE_ID OBRIGATÓRIO)
# =========================
@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    device_id = (data.get("device_id") or "").strip()

    if not device_id:
        return jsonify({"ok": False, "msg": "Falha ao identificar o aparelho. Limpe os dados do site e tente novamente."}), 400

    ok, info = validar_chave(key, device_id)

    if ok:
        session["activated"] = True
        session["key"] = key
        session["device_id"] = device_id
        return jsonify({"ok": True, "msg": info})

    return jsonify({"ok": False, "msg": info}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return ("", 204)

# =========================
# TELAS
# =========================
LOGIN_HTML = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ativação - Arte Preço Pro</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#4E6B3E">
<link rel="icon" href="/static/icon-192.png">
<style>
body { font-family: Arial; background:#DCE6D5; margin:18px;}
.card { max-width:520px; margin:auto; background:#EEF3EA; padding:16px; border-radius:12px;}
input { width:100%; padding:10px; margin-top:10px; font-size:16px;}
button { width:100%; padding:12px; margin-top:14px; font-size:18px; background:#4E6B3E; color:white; border:none; border-radius:8px;}
.msg { margin-top:12px; padding:10px; background:white; border-radius:10px; white-space:pre-wrap;}
.small { font-size: 13px; color:#4F5A4A; }
</style>
</head>
<body>
<div class="card">
<h2>Ativação do Arte Preço Pro</h2>
<div class="small">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>

<form id="formAtivar">
<input id="key" placeholder="Cole sua chave AP-..." required>
<button type="submit">Ativar</button>
</form>

<div id="msg" class="msg" style="display:none;"></div>
</div>

<script>
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

// UUID v4 fallback (para aparelhos que não têm crypto.randomUUID)
function uuidv4Fallback() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getDeviceId() {
  let id = localStorage.getItem("artepreco_device_id");
  if (!id) {
    try {
      if (crypto && crypto.randomUUID) id = crypto.randomUUID();
      else id = uuidv4Fallback();
    } catch (e) {
      id = uuidv4Fallback();
    }
    localStorage.setItem("artepreco_device_id", id);
  }
  return id;
}

function showMsg(t) {
  const el = document.getElementById("msg");
  el.style.display = "block";
  el.textContent = t;
}

async function callActivate(key) {
  const device_id = getDeviceId();
  const r = await fetch("/api/activate", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ key: key, device_id: device_id })
  });
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok && data.ok, msg: data.msg || "Erro ao ativar." };
}

// Auto ativar se já tiver chave salva
(async function autoActivate() {
  const savedKey = localStorage.getItem("artepreco_key");
  if (!savedKey) return;
  try {
    const res = await callActivate(savedKey);
    if (res.ok) {
      window.location.href = "/";
    } else {
      localStorage.removeItem("artepreco_key");
      showMsg(res.msg);
    }
  } catch (e) {
    showMsg("Não consegui conectar ao servidor. Verifique o Wi-Fi e tente novamente.");
  }
})();

document.getElementById("formAtivar").addEventListener("submit", async function(e) {
  e.preventDefault();
  const key = (document.getElementById("key").value || "").trim();
  if (!key) return;

  try {
    const res = await callActivate(key);
    if (res.ok) {
      localStorage.setItem("artepreco_key", key);
      window.location.href = "/";
    } else {
      showMsg(res.msg);
    }
  } catch (e) {
    showMsg("Não consegui conectar ao servidor. Verifique o Wi-Fi e tente novamente.");
  }
});
</script>
</body>
</html>
"""

APP_HTML = """
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Arte Preço Pro</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#4E6B3E">
<link rel="icon" href="/static/icon-192.png">
<style>
body { font-family: Arial; background:#DCE6D5; margin:18px;}
.card { max-width:520px; margin:auto; background:#EEF3EA; padding:16px; border-radius:12px;}
input { width:100%; padding:10px; margin-top:10px; font-size:16px;}
button { width:100%; padding:12px; margin-top:14px; font-size:18px; background:#4E6B3E; color:white; border:none; border-radius:8px;}
.res { margin-top:16px; padding:12px; background:white; border-radius:10px; }
.logout { background:#666; }
.msg { margin-top:12px; padding:10px; background:white; border-radius:10px; white-space:pre-wrap; display:none;}
</style>
</head>
<body>
<div class="card">
<h2>Arte Preço Pro</h2>

<button class="logout" type="button" onclick="doLogout()">Sair</button>
<div id="msg" class="msg"></div>

<form method="post">
<input name="produto" placeholder="Produto" required>
<input name="material" type="number" step="0.01" placeholder="Material (R$)" required>
<input name="horas" type="number" step="0.01" placeholder="Horas" required>
<input name="valor_hora" type="number" step="0.01" placeholder="Valor Hora (R$)" required>
<input name="despesas" type="number" step="0.01" placeholder="Despesas (R$)" required>
<input name="margem" type="number" step="0.01" placeholder="Margem (%)" required>
<input name="validade_dias" type="number" value="7" required>
<button type="submit">Calcular</button>
</form>

{% if resultado %}
<div class="res">
<b>Preço Final:</b> R$ {{ "%.2f"|format(resultado["preco_final"]) }}<br>
<b>Custo Total:</b> R$ {{ "%.2f"|format(resultado["custo_total"]) }}<br>
<b>Validade:</b> {{ resultado["data_validade"] }}
</div>
{% endif %}

</div>

<script>
function uuidv4Fallback() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getDeviceId() {
  let id = localStorage.getItem("artepreco_device_id");
  if (!id) {
    try {
      if (crypto && crypto.randomUUID) id = crypto.randomUUID();
      else id = uuidv4Fallback();
    } catch (e) {
      id = uuidv4Fallback();
    }
    localStorage.setItem("artepreco_device_id", id);
  }
  return id;
}

function showMsg(t) {
  const el = document.getElementById("msg");
  el.style.display = "block";
  el.textContent = t;
}

async function autoActivate() {
  const key = localStorage.getItem("artepreco_key");
  if (!key) return;

  const device_id = getDeviceId();
  try {
    const r = await fetch("/api/activate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ key: key, device_id: device_id })
    });

    const data = await r.json().catch(() => ({}));
    if (!r.ok || !data.ok) {
      localStorage.removeItem("artepreco_key");
      window.location.href = "/activate";
    }
  } catch (e) {
    showMsg("Sem conexão com o servidor. Verifique o Wi-Fi.");
  }
}

async function doLogout() {
  try { await fetch("/logout", { method: "POST" }); } catch(e) {}
  localStorage.removeItem("artepreco_key");
  window.location.href = "/activate";
}

autoActivate();
</script>
</body>
</html>
"""

def is_activated():
    return session.get("activated") is True

@app.route("/activate")
def activate():
    return render_template_string(LOGIN_HTML)

@app.route("/", methods=["GET", "POST"])
def home():
    if not is_activated():
        return redirect(url_for("activate"))

    resultado = None
    if request.method == "POST":
        resultado = calcular_preco(
            produto=request.form["produto"],
            material=float(request.form["material"]),
            horas=float(request.form["horas"]),
            valor_hora=float(request.form["valor_hora"]),
            despesas=float(request.form["despesas"]),
            margem=float(request.form["margem"]),
            validade_dias=int(request.form["validade_dias"]),
        )

    return render_template_string(APP_HTML, resultado=resultado)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)