# app_web.py
import os
import io
import json
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_file, Response, render_template_string

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__, static_folder="static", static_url_path="/static")

# ---------------------------------------------------------------------
# Licença (tenta usar seu core.license_core, mas tem fallback)
# ---------------------------------------------------------------------
def validar_licenca(chave: str):
    """
    Retorna (ok: bool, msg: str)
    """
    chave = (chave or "").strip()
    if not chave.startswith("AP-"):
        return False, "Chave inválida (precisa começar com AP-)."

    # tenta usar seu validador
    try:
        from core.license_core import validar_chave  # seu módulo
        # seu validar_chave às vezes aceita 1 argumento apenas
        res = validar_chave(chave)
        # pode ser bool, ou (bool,msg)
        if isinstance(res, tuple) and len(res) >= 2:
            return bool(res[0]), str(res[1])
        return (True, "Ativado.") if res else (False, "Chave inválida.")
    except Exception:
        # fallback simples: aceita AP-... com 2 pontos (formato tipo JWT)
        parts = chave.split(".")
        if len(parts) >= 3:
            return True, "Ativado (fallback)."
        return False, "Formato inválido."

# ---------------------------------------------------------------------
# Templates (Jinja) - NÃO usa f-string com variáveis (isso evita NameError)
# ---------------------------------------------------------------------
TPL_BASE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{ title }}</title>

  <!-- PWA -->
  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#4E6B3E"/>
  <link rel="icon" href="/static/icon-192.png">

  <style>
    body{font-family:Arial, sans-serif;background:#dce6d5;margin:0;padding:18px}
    .card{max-width:560px;margin:0 auto;background:#eaf1e6;border-radius:14px;padding:18px;border:1px solid #c3d1bb}
    h1{margin:0 0 10px 0;font-size:38px}
    label{display:block;margin:10px 0 6px 0;font-weight:700}
    input,textarea{width:100%;padding:12px;border-radius:10px;border:1px solid #a7b59e;font-size:16px}
    .row{display:flex;gap:10px}
    .row > div{flex:1}
    button{width:100%;padding:14px;border:none;border-radius:12px;background:#4E6B3E;color:white;font-size:18px;font-weight:700;margin-top:14px}
    .btn2{background:#6d7e67}
    .msg{margin-top:12px;padding:12px;border-radius:10px;background:white;border:1px solid #d1d8cb}
    .ok{border-color:#7dbb7d}
    .bad{border-color:#d77}
    .small{font-size:13px;color:#444}
    .footer-actions{display:flex;gap:10px;margin-top:12px}
    .footer-actions button{margin-top:0}
    .big{font-size:34px;font-weight:900;margin-top:6px}
  </style>
</head>
<body>
  <div class="card">
    {{ body|safe }}
  </div>

<script>
  // registra SW (se existir)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
  }

  function getKey(){
    return localStorage.getItem('AP_KEY') || '';
  }
  function setKey(v){
    localStorage.setItem('AP_KEY', v);
  }
  function clearKey(){
    localStorage.removeItem('AP_KEY');
  }

  // Se tiver chave salva e estiver na home, manda pro app
  (function(){
    const path = location.pathname;
    if (path === '/' && getKey()){
      location.href = '/app';
    }
  })();
</script>

{{ extra_js|safe }}
</body>
</html>
"""

def money_br(v):
    try:
        v = float(v)
    except Exception:
        v = 0.0
    s = f"{v:,.2f}"
    # troca separadores pro padrão BR
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def calc_preco(custo_material, horas, valor_hora, despesas, margem_pct):
    custo_material = float(custo_material or 0)
    horas = float(horas or 0)
    valor_hora = float(valor_hora or 0)
    despesas = float(despesas or 0)
    margem_pct = float(margem_pct or 0)

    custo_base = custo_material + (horas * valor_hora) + despesas
    preco_final = custo_base * (1 + (margem_pct / 100.0))
    return custo_base, preco_final

# ---------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------
@app.get("/")
def home():
    body = """
      <h1>Ativação do Arte Preço Pro</h1>
      <div class="small">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
      <label>Chave</label>
      <input id="key" placeholder="Cole sua chave AP-..." autocomplete="off"/>
      <button onclick="ativar()">Ativar</button>
      <div id="msg" class="msg" style="display:none"></div>
    """

    extra_js = """
    <script>
      function showMsg(text, ok){
        const el = document.getElementById('msg');
        el.style.display = 'block';
        el.className = 'msg ' + (ok ? 'ok' : 'bad');
        el.textContent = text;
      }

      async function ativar(){
        const key = (document.getElementById('key').value || '').trim();
        if(!key){ showMsg('Cole a chave primeiro.', false); return; }
        try{
          const r = await fetch('/api/activate', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({key})
          });
          const j = await r.json();
          if(j.ok){
            localStorage.setItem('AP_KEY', key);
            showMsg('✅ ' + j.msg, true);
            setTimeout(()=>location.href='/app', 350);
          }else{
            showMsg('❌ ' + j.msg, false);
          }
        }catch(e){
          showMsg('Falha ao ativar. Verifique internet e tente novamente.', false);
        }
      }
    </script>
    """
    return render_template_string(TPL_BASE, title="Ativação", body=body, extra_js=extra_js)

@app.post("/api/activate")
def api_activate():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    ok, msg = validar_licenca(key)
    return jsonify({"ok": ok, "msg": msg})

@app.get("/app")
def app_page():
    body = """
      <h1>Arte Preço Pro</h1>

      <label>Dados da sua empresa (aparecem no PDF)</label>
      <input id="emp_nome" placeholder="Nome da empresa" />
      <div class="row">
        <div>
          <input id="emp_tel" placeholder="Telefone/WhatsApp" />
        </div>
        <div>
          <input id="emp_email" placeholder="E-mail" />
        </div>
      </div>
      <textarea id="emp_end" placeholder="Endereço completo" rows="2"></textarea>

      <label>Dados do cliente (para quem é o orçamento)</label>
      <input id="cli_nome" placeholder="Nome do cliente" />
      <div class="row">
        <div>
          <input id="cli_tel" placeholder="Telefone/WhatsApp do cliente" />
        </div>
        <div>
          <input id="cli_email" placeholder="E-mail do cliente" />
        </div>
      </div>
      <textarea id="cli_end" placeholder="Endereço do cliente (opcional)" rows="2"></textarea>

      <hr style="border:none;border-top:1px solid #c3d1bb;margin:16px 0">

      <label>Produto</label>
      <input id="produto" placeholder="Ex: Logo" />

      <label>Custo do Material (R$)</label>
      <input id="custo_material" inputmode="decimal" placeholder="Ex: 10" />

      <div class="row">
        <div>
          <label>Horas Trabalhadas</label>
          <input id="horas" inputmode="decimal" placeholder="Ex: 4" />
        </div>
        <div>
          <label>Valor da Hora (R$)</label>
          <input id="valor_hora" inputmode="decimal" placeholder="Ex: 30" />
        </div>
      </div>

      <label>Despesas Extras (R$)</label>
      <input id="despesas" inputmode="decimal" placeholder="Ex: 2" />

      <label>Margem de Lucro (%)</label>
      <input id="margem" inputmode="decimal" placeholder="Ex: 80" />

      <label>Validade (dias)</label>
      <input id="validade" inputmode="numeric" placeholder="Ex: 7" />

      <button onclick="calcular()">Calcular</button>

      <div id="out" class="msg" style="display:none"></div>

      <div class="footer-actions">
        <button class="btn2" onclick="sair()">Sair</button>
        <button onclick="gerarPDF()">Gerar PDF</button>
      </div>
    """

    extra_js = """
    <script>
      // carrega dados salvos
      function loadField(id, key){
        const v = localStorage.getItem(key);
        if(v !== null) document.getElementById(id).value = v;
      }
      function saveField(id, key){
        const v = document.getElementById(id).value || '';
        localStorage.setItem(key, v);
      }
      const map = [
        ['emp_nome','EMP_NOME'], ['emp_tel','EMP_TEL'], ['emp_email','EMP_EMAIL'], ['emp_end','EMP_END'],
        ['cli_nome','CLI_NOME'], ['cli_tel','CLI_TEL'], ['cli_email','CLI_EMAIL'], ['cli_end','CLI_END'],
      ];
      map.forEach(([id,k])=>loadField(id,k));
      map.forEach(([id,k])=>{
        document.getElementById(id).addEventListener('input', ()=>saveField(id,k));
      });

      function showOut(html, ok){
        const el = document.getElementById('out');
        el.style.display = 'block';
        el.className = 'msg ' + (ok ? 'ok' : 'bad');
        el.innerHTML = html;
      }

      function payload(){
        return {
          key: localStorage.getItem('AP_KEY') || '',
          empresa: {
            nome: document.getElementById('emp_nome').value || '',
            tel: document.getElementById('emp_tel').value || '',
            email: document.getElementById('emp_email').value || '',
            end: document.getElementById('emp_end').value || '',
          },
          cliente: {
            nome: document.getElementById('cli_nome').value || '',
            tel: document.getElementById('cli_tel').value || '',
            email: document.getElementById('cli_email').value || '',
            end: document.getElementById('cli_end').value || '',
          },
          produto: document.getElementById('produto').value || '',
          custo_material: document.getElementById('custo_material').value || '0',
          horas: document.getElementById('horas').value || '0',
          valor_hora: document.getElementById('valor_hora').value || '0',
          despesas: document.getElementById('despesas').value || '0',
          margem: document.getElementById('margem').value || '0',
          validade: document.getElementById('validade').value || '0',
        };
      }

      async function calcular(){
        try{
          const r = await fetch('/api/calc', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload())
          });
          const j = await r.json();
          if(!j.ok){
            showOut('❌ ' + j.msg, false);
            if(j.force_login) setTimeout(()=>location.href='/', 500);
            return;
          }
          showOut(
            '<div><b>Produto:</b> ' + j.produto + '</div>' +
            '<div><b>Custo Base:</b> ' + j.custo_base_fmt + '</div>' +
            '<div class="big">Preço Final: ' + j.preco_final_fmt + '</div>' +
            '<div class="small">Validade: ' + j.validade + ' dia(s)</div>',
            true
          );
        }catch(e){
          showOut('Falha ao calcular. Tente novamente.', false);
        }
      }

      async function gerarPDF(){
        try{
          const r = await fetch('/api/pdf', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload())
          });
          if(!r.ok){
            const t = await r.text();
            showOut('❌ Falha ao gerar PDF: ' + t, false);
            return;
          }
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'orcamento_arte_preco_pro.pdf';
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        }catch(e){
          showOut('Falha ao gerar PDF. Tente novamente.', false);
        }
      }

      function sair(){
        // não apaga a chave (pra não ficar pedindo ativação)
        // só volta pro topo da página
        window.scrollTo({top:0, behavior:'smooth'});
      }

      // se não tiver chave, manda pra ativação
      if(!(localStorage.getItem('AP_KEY') || '')){
        location.href = '/';
      }
    </script>
    """
    return render_template_string(TPL_BASE, title="Arte Preço Pro", body=body, extra_js=extra_js)

@app.post("/api/calc")
def api_calc():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()

    ok, msg = validar_licenca(key)
    if not ok:
        return jsonify({"ok": False, "msg": msg, "force_login": True})

    try:
        produto = (payload.get("produto") or "").strip() or "Serviço"
        custo_material = payload.get("custo_material", 0)
        horas = payload.get("horas", 0)
        valor_hora = payload.get("valor_hora", 0)
        despesas = payload.get("despesas", 0)
        margem = payload.get("margem", 0)
        validade = int(float(payload.get("validade", 0) or 0))

        custo_base, preco_final = calc_preco(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas=despesas,
            margem_pct=margem,
        )
        return jsonify({
            "ok": True,
            "produto": produto,
            "validade": validade,
            "custo_base": custo_base,
            "preco_final": preco_final,
            "custo_base_fmt": money_br(custo_base),
            "preco_final_fmt": money_br(preco_final),
        })
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao calcular: {e}"}), 500

@app.post("/api/pdf")
def api_pdf():
    payload = request.get_json(silent=True) or {}
    key = (payload.get("key") or "").strip()

    ok, msg = validar_licenca(key)
    if not ok:
        return Response(msg, status=403, mimetype="text/plain")

    try:
        empresa = payload.get("empresa") or {}
        cliente = payload.get("cliente") or {}

        produto = (payload.get("produto") or "").strip() or "Serviço"
        custo_material = payload.get("custo_material", 0)
        horas = payload.get("horas", 0)
        valor_hora = payload.get("valor_hora", 0)
        despesas = payload.get("despesas", 0)
        margem = payload.get("margem", 0)
        validade = int(float(payload.get("validade", 0) or 0))

        custo_base, preco_final = calc_preco(
            custo_material=custo_material,
            horas=horas,
            valor_hora=valor_hora,
            despesas=despesas,
            margem_pct=margem,
        )

        # PDF
        buff = io.BytesIO()
        c = canvas.Canvas(buff, pagesize=A4)
        w, h = A4

        y = h - 50
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, y, "ORÇAMENTO - ARTE PREÇO PRO")

        y -= 30
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        y -= 25
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DADOS DA EMPRESA")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Nome: {empresa.get('nome','')}")
        y -= 14
        c.drawString(40, y, f"Telefone: {empresa.get('tel','')}")
        y -= 14
        c.drawString(40, y, f"E-mail: {empresa.get('email','')}")
        y -= 14
        c.drawString(40, y, f"Endereço: {empresa.get('end','')}")

        y -= 22
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DADOS DO CLIENTE")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Nome: {cliente.get('nome','')}")
        y -= 14
        c.drawString(40, y, f"Telefone: {cliente.get('tel','')}")
        y -= 14
        c.drawString(40, y, f"E-mail: {cliente.get('email','')}")
        y -= 14
        c.drawString(40, y, f"Endereço: {cliente.get('end','')}")

        y -= 22
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "DETALHES DO SERVIÇO")
        y -= 16
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Produto/Serviço: {produto}")
        y -= 14
        c.drawString(40, y, f"Custo material: {money_br(custo_material)}")
        y -= 14
        c.drawString(40, y, f"Trabalho: {horas}h x {money_br(valor_hora)}")
        y -= 14
        c.drawString(40, y, f"Despesas extras: {money_br(despesas)}")
        y -= 14
        c.drawString(40, y, f"Margem: {margem}%")

        y -= 22
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"Custo Base: {money_br(custo_base)}")
        y -= 22
        c.setFont("Helvetica-Bold", 18)
        c.drawString(40, y, f"Preço Final: {money_br(preco_final)}")

        y -= 22
        c.setFont("Helvetica", 11)
        c.drawString(40, y, f"Validade: {validade} dia(s)")

        c.showPage()
        c.save()
        buff.seek(0)

        return send_file(
            buff,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="orcamento_arte_preco_pro.pdf",
        )
    except Exception as e:
        return Response(f"Erro ao gerar PDF: {e}", status=500, mimetype="text/plain")


# Vercel procura a variável "app"
# (não precisa de app.run() aqui)
