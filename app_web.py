import os
import json
import time
import base64
import hmac
import hashlib
import sqlite3
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from flask import Flask, request, make_response, redirect, render_template_string, send_from_directory

# ============================================================
# APP CONFIG
# ============================================================

app = Flask(__name__, static_folder=None)

# Diretório de arquivos estáticos (manifest, sw, ícones)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

APP_SECRET = os.environ.get("APP_SECRET", "ARTEPRECO_SUPER_SEGREDO_2026")

# ============================================================
# ✅ 0) Rotas de PWA (manifest, service worker, ícones)
#    (Vercel + Flask às vezes não serve /static sozinho)
# ============================================================

@app.get("/manifest.webmanifest")
def manifest_webmanifest():
    # Preferimos entregar o manifest que está em /static/manifest.json
    path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(path):
        resp = make_response(send_from_directory(STATIC_DIR, "manifest.json"))
        resp.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
        resp.headers["Cache-Control"] = "no-store"
        return resp
    # fallback mínimo (caso alguém apague o arquivo)
    data = {
        "name": "Arte Preço Pro",
        "short_name": "ArtePreço",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#DCE6D5",
        "theme_color": "#4E683E",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    resp = make_response(json.dumps(data, ensure_ascii=False))
    resp.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/sw.js")
def service_worker():
    # Entrega o SW que está em /static/sw.js
    path = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(path):
        resp = make_response(send_from_directory(STATIC_DIR, "sw.js"))
        resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
        resp.headers["Cache-Control"] = "no-store"
        return resp
    # fallback (offline bem simples)
    js = """const CACHE_NAME='artepreco-v1';
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE_NAME)); });
self.addEventListener('fetch', e => { e.respondWith(fetch(e.request).catch(()=>caches.match(e.request))); });
"""
    resp = make_response(js)
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/static/<path:filename>")
def static_files(filename):
    # Serve qualquer arquivo dentro da pasta /static
    return send_from_directory(STATIC_DIR, filename)

@app.get("/favicon.ico")
def favicon():
    # Evita erro 404 no console
    fav = os.path.join(STATIC_DIR, "icon-192.png")
    if os.path.exists(fav):
        return send_from_directory(STATIC_DIR, "icon-192.png")
    return ("", 204)

# ============================================================
# LICENÇA (CHAVE AP-...)
# ============================================================

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def gerar_chave(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body_b64 = _b64url(body)
    sig = hmac.new(APP_SECRET.encode("utf-8"), body_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64url(sig)
    return f"AP-{body_b64}.{sig_b64}"

def validar_chave(chave: str) -> Tuple[bool, str, Optional[dict]]:
    if not chave or not chave.startswith("AP-"):
        return False, "Formato inválido.", None

    try:
        token = chave[3:]
        body_b64, sig_b64 = token.split(".", 1)
        expected_sig = hmac.new(APP_SECRET.encode("utf-8"), body_b64.encode("utf-8"), hashlib.sha256).digest()
        if _b64url(expected_sig) != sig_b64:
            return False, "Assinatura inválida.", None

        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        if exp and time.time() > exp:
            return False, "Chave expirada.", payload

        return True, "OK", payload
    except Exception as e:
        return False, f"Erro ao validar chave: {e}", None

# ============================================================
# PERSISTÊNCIA (DB simples) + CONFIG DA EMPRESA
# ============================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "artepreco.db")

def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kv (
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)
    conn.commit()
    conn.close()

db_init()

def kv_get(k: str, default: str = "") -> str:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT v FROM kv WHERE k=?", (k,))
    row = cur.fetchone()
    conn.close()
    return (row["v"] if row else default)

def kv_set(k: str, v: str) -> None:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
    conn.commit()
    conn.close()

# chaves
KV_ACTIVATED = "activated_key"
KV_COMPANY_JSON = "company_json"

# ============================================================
# REGRAS DE CÁLCULO
# ============================================================

@dataclass
class CalcInput:
    produto: str
    custo_material: float
    horas_trabalhadas: float
    valor_hora: float
    despesas_extras: float
    margem_lucro_pct: float
    validade_dias: int

@dataclass
class CalcResult:
    custo_base: float
    preco_final: float
    preco_final_fmt: str
    custo_base_fmt: str

def _fmt_brl(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def calcular_preco(ci: CalcInput) -> CalcResult:
    custo_trabalho = max(ci.horas_trabalhadas, 0) * max(ci.valor_hora, 0)
    custo_base = max(ci.custo_material, 0) + max(ci.despesas_extras, 0) + custo_trabalho
    mult = 1.0 + (max(ci.margem_lucro_pct, 0) / 100.0)
    preco_final = custo_base * mult
    return CalcResult(
        custo_base=custo_base,
        preco_final=preco_final,
        preco_final_fmt=_fmt_brl(preco_final),
        custo_base_fmt=_fmt_brl(custo_base),
    )

# ============================================================
# PDF (GERAÇÃO SIMPLES)
# ============================================================

def gerar_pdf_bytes(dados_empresa: dict, dados_cliente: dict, ci: CalcInput, cr: CalcResult) -> bytes:
    # PDF simples via texto (sem lib externa) — funciona bem na Vercel
    # Estrutura minimalista PDF (ok para uso)
    # Observação: NÃO mostramos margem no PDF (como você pediu).
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    empresa_nome = dados_empresa.get("nome", "").strip()
    empresa_tel = dados_empresa.get("telefone", "").strip()
    empresa_email = dados_empresa.get("email", "").strip()
    empresa_end = dados_empresa.get("endereco", "").strip()

    cliente_nome = dados_cliente.get("nome", "").strip()
    cliente_tel = dados_cliente.get("telefone", "").strip()
    cliente_email = dados_cliente.get("email", "").strip()
    cliente_end = dados_cliente.get("endereco", "").strip()

    lines = []
    lines.append("ORCAMENTO - ARTE PRECO PRO")
    lines.append("")
    lines.append(f"Data: {now}")
    lines.append("")
    lines.append("DADOS DA EMPRESA")
    lines.append(f"Nome: {empresa_nome}")
    lines.append(f"Telefone: {empresa_tel}")
    lines.append(f"E-mail: {empresa_email}")
    lines.append(f"Endereço: {empresa_end}")
    lines.append("")
    lines.append("DADOS DO CLIENTE")
    lines.append(f"Nome: {cliente_nome}")
    lines.append(f"Telefone: {cliente_tel}")
    lines.append(f"E-mail: {cliente_email}")
    lines.append(f"Endereço: {cliente_end}")
    lines.append("")
    lines.append("DETALHES DO SERVIÇO")
    lines.append(f"Produto/Serviço: {ci.produto}")
    lines.append(f"Custo material: {_fmt_brl(ci.custo_material)}")
    lines.append(f"Trabalho: {ci.horas_trabalhadas:g}h x {_fmt_brl(ci.valor_hora)}")
    lines.append(f"Despesas extras: {_fmt_brl(ci.despesas_extras)}")
    lines.append("")
    lines.append(f"Custo Base: {cr.custo_base_fmt}")
    lines.append(f"Preco Final: {cr.preco_final_fmt}")
    lines.append(f"Validade: {ci.validade_dias} dia(s)")
    text = "\n".join(lines)

    # PDF básico (texto)
    # monta um PDF simples com fonte padrão
    def pdf_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_stream = "BT\n/F1 14 Tf\n50 760 Td\n"
    y = 0
    for line in text.split("\n"):
        if y != 0:
            content_stream += "0 -18 Td\n"
        content_stream += f"({pdf_escape(line)}) Tj\n"
        y += 1
    content_stream += "ET\n"
    content_bytes = content_stream.encode("latin-1", errors="ignore")

    objects = []
    offsets = []

    def add_obj(s: bytes):
        offsets.append(sum(len(o) for o in objects))
        objects.append(s)

    # PDF header
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    objects.append(header)

    # 1) catalog
    add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2) pages
    add_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3) page
    add_obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")
    # 4) font
    add_obj(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    # 5) contents
    add_obj(f"5 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n".encode("utf-8") + content_bytes + b"\nendstream\nendobj\n")

    # xref
    xref_start = sum(len(o) for o in objects)
    # compute real offsets (including header)
    # rebuild xref offsets by scanning objects is complex; we used running offsets list
    # Let's compute actual offsets by re-walking
    full = b"".join(objects)
    # But we need xref entries; easiest: compute by finding "1 0 obj" etc offsets
    # We'll do a simple find
    def find_offset(marker: bytes) -> int:
        return full.find(marker)

    off1 = find_offset(b"1 0 obj")
    off2 = find_offset(b"2 0 obj")
    off3 = find_offset(b"3 0 obj")
    off4 = find_offset(b"4 0 obj")
    off5 = find_offset(b"5 0 obj")

    xref = "xref\n0 6\n0000000000 65535 f \n".encode("utf-8")
    for off in [off1, off2, off3, off4, off5]:
        xref += f"{off:010d} 00000 n \n".encode("utf-8")

    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("utf-8")

    return full + xref + trailer

# ============================================================
# TELAS + FLUXO
# ============================================================

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Arte Preço Pro</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <meta name="theme-color" content="#4E683E" />
  <link rel="icon" href="/static/icon-192.png" />
  <link rel="apple-touch-icon" href="/static/icon-192.png" />
  <style>
    :root{
      --bg:#DCE6D5;
      --card:#EAF1E6;
      --dark:#4E683E;
      --dark2:#3B5330;
      --txt:#1a1a1a;
      --muted:#444;
      --radius:18px;
    }
    body{
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background:var(--bg);
      color:var(--txt);
    }
    .wrap{
      max-width:760px;
      margin:0 auto;
      padding:18px;
    }
    .card{
      background:var(--card);
      border-radius:var(--radius);
      padding:18px;
      box-shadow:0 4px 16px rgba(0,0,0,.08);
      margin-bottom:18px;
    }
    h1{
      margin:0 0 10px 0;
      font-size:28px;
      letter-spacing:.3px;
    }
    h2{
      margin:0 0 10px 0;
      font-size:18px;
      color:var(--dark2);
    }
    .row{
      display:flex;
      gap:12px;
      flex-wrap:wrap;
    }
    .col{
      flex:1;
      min-width:220px;
    }
    label{
      display:block;
      font-weight:700;
      margin:10px 0 6px;
      color:var(--muted);
    }
    input{
      width:100%;
      box-sizing:border-box;
      border:1px solid rgba(0,0,0,.12);
      border-radius:14px;
      padding:12px 12px;
      font-size:16px;
      outline:none;
      background:#fff;
    }
    input:focus{
      border-color:rgba(78,104,62,.45);
      box-shadow:0 0 0 3px rgba(78,104,62,.15);
    }
    .btn{
      width:100%;
      border:0;
      padding:14px 14px;
      font-size:18px;
      font-weight:800;
      border-radius:14px;
      cursor:pointer;
      background:var(--dark);
      color:#fff;
      margin-top:14px;
    }
    .btn:active{ transform: translateY(1px); }
    .btn.secondary{
      background:#6b6b6b;
    }
    .btn.outline{
      background:transparent;
      color:var(--dark);
      border:2px solid var(--dark);
    }
    .small{
      font-size:14px;
      color:#333;
      margin-top:6px;
    }
    .result{
      margin-top:18px;
      padding:14px;
      background:#fff;
      border-radius:16px;
      border:1px solid rgba(0,0,0,.10);
    }
    .big{
      font-size:34px;
      font-weight:900;
      color:#000;
      margin-top:4px;
    }
    .muted{
      color:#444;
      font-size:15px;
    }
    .warn{
      margin-top:10px;
      color:#7a4b00;
      font-weight:700;
    }
    .footer-actions{
      display:flex;
      gap:12px;
      margin-top:14px;
      flex-wrap:wrap;
    }
    .footer-actions .btn{
      flex:1;
      min-width:220px;
      margin-top:0;
    }
  </style>
  <script>
    // Registra o Service Worker (para instalação/offline)
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(()=>{});
      });
    }
  </script>
</head>
<body>
  <div class="wrap">
    {% if not activated %}
      <div class="card">
        <h1>Ativação do Arte Preço Pro</h1>
        <div class="small">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
        <form method="POST" action="/ativar">
          <label>Chave</label>
          <input name="chave" placeholder="Cole sua chave AP-..." required />
          <button class="btn" type="submit">Ativar</button>
        </form>
        {% if msg %}
          <div class="warn">{{msg}}</div>
        {% endif %}
      </div>
    {% else %}
      <div class="card">
        <h1>Arte Preço Pro</h1>
        <div class="small">Preencha e clique em <b>Calcular</b>. Depois gere o PDF.</div>

        <form method="POST" action="/calcular">
          <label>Produto</label>
          <input name="produto" value="{{form.produto}}" placeholder="Ex: Logo" required />

          <label>Custo do Material (R$)</label>
          <input name="custo_material" value="{{form.custo_material}}" placeholder="Ex: 10" inputmode="decimal" required />

          <div class="row">
            <div class="col">
              <label>Horas Trabalhadas</label>
              <input name="horas_trabalhadas" value="{{form.horas_trabalhadas}}" placeholder="Ex: 4" inputmode="decimal" required />
            </div>
            <div class="col">
              <label>Valor da Hora (R$)</label>
              <input name="valor_hora" value="{{form.valor_hora}}" placeholder="Ex: 30" inputmode="decimal" required />
            </div>
          </div>

          <label>Despesas Extras (R$)</label>
          <input name="despesas_extras" value="{{form.despesas_extras}}" placeholder="Ex: 2" inputmode="decimal" required />

          <label>Margem de Lucro (%)</label>
          <input name="margem_lucro_pct" value="{{form.margem_lucro_pct}}" placeholder="Ex: 80" inputmode="decimal" required />

          <label>Validade (dias)</label>
          <input name="validade_dias" value="{{form.validade_dias}}" placeholder="Ex: 7" inputmode="numeric" required />

          <button class="btn" type="submit">Calcular</button>
        </form>

        {% if result %}
          <div class="result">
            <div><b>Produto:</b> {{result.produto}}</div>
            <div><b>Custo Base:</b> {{result.custo_base_fmt}}</div>
            <div class="big">Preço Final: {{result.preco_final_fmt}}</div>
            <div class="muted">Validade: {{result.validade_dias}} dia(s)</div>

            <div class="footer-actions">
              <form method="GET" action="/pdf" style="flex:1;">
                <button class="btn outline" type="submit">Gerar PDF</button>
              </form>

              <form method="GET" action="/empresa" style="flex:1;">
                <button class="btn outline" type="submit">Dados da empresa</button>
              </form>

              <form method="GET" action="/cliente" style="flex:1;">
                <button class="btn outline" type="submit">Dados do cliente</button>
              </form>
            </div>
          </div>
        {% endif %}
      </div>

      <div class="card">
        <div class="footer-actions">
          <form method="POST" action="/sair" style="flex:1;">
            <button class="btn secondary" type="submit">Sair</button>
          </form>
          <form method="POST" action="/revalidar" style="flex:1;">
            <button class="btn" type="submit">Revalidar chave</button>
          </form>
        </div>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""

# ============================================================
# REGRAS DE CÁLCULO
# ============================================================

@dataclass
class CalcInput:
    produto: str
    custo_material: float
    horas_trabalhadas: float
    valor_hora: float
    despesas_extras: float
    margem_lucro_pct: float
    validade_dias: int

@dataclass
class CalcResult:
    custo_base: float
    preco_final: float
    preco_final_fmt: str
    custo_base_fmt: str

def _fmt_brl(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def calcular_preco(ci: CalcInput) -> CalcResult:
    custo_trabalho = max(ci.horas_trabalhadas, 0) * max(ci.valor_hora, 0)
    custo_base = max(ci.custo_material, 0) + max(ci.despesas_extras, 0) + custo_trabalho
    mult = 1.0 + (max(ci.margem_lucro_pct, 0) / 100.0)
    preco_final = custo_base * mult
    return CalcResult(
        custo_base=custo_base,
        preco_final=preco_final,
        preco_final_fmt=_fmt_brl(preco_final),
        custo_base_fmt=_fmt_brl(custo_base),
    )

# ============================================================
# PDF (GERAÇÃO SIMPLES)
# ============================================================

def gerar_pdf_bytes(dados_empresa: dict, dados_cliente: dict, ci: CalcInput, cr: CalcResult) -> bytes:
    # PDF simples via texto (sem lib externa) — funciona bem na Vercel
    # Estrutura minimalista PDF (ok para uso)
    # Observação: NÃO mostramos margem no PDF (como você pediu).
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    empresa_nome = dados_empresa.get("nome", "").strip()
    empresa_tel = dados_empresa.get("telefone", "").strip()
    empresa_email = dados_empresa.get("email", "").strip()
    empresa_end = dados_empresa.get("endereco", "").strip()

    cliente_nome = dados_cliente.get("nome", "").strip()
    cliente_tel = dados_cliente.get("telefone", "").strip()
    cliente_email = dados_cliente.get("email", "").strip()
    cliente_end = dados_cliente.get("endereco", "").strip()

    lines = []
    lines.append("ORCAMENTO - ARTE PRECO PRO")
    lines.append("")
    lines.append(f"Data: {now}")
    lines.append("")
    lines.append("DADOS DA EMPRESA")
    lines.append(f"Nome: {empresa_nome}")
    lines.append(f"Telefone: {empresa_tel}")
    lines.append(f"E-mail: {empresa_email}")
    lines.append(f"Endereço: {empresa_end}")
    lines.append("")
    lines.append("DADOS DO CLIENTE")
    lines.append(f"Nome: {cliente_nome}")
    lines.append(f"Telefone: {cliente_tel}")
    lines.append(f"E-mail: {cliente_email}")
    lines.append(f"Endereço: {cliente_end}")
    lines.append("")
    lines.append("DETALHES DO SERVIÇO")
    lines.append(f"Produto/Serviço: {ci.produto}")
    lines.append(f"Custo material: {_fmt_brl(ci.custo_material)}")
    lines.append(f"Trabalho: {ci.horas_trabalhadas:g}h x {_fmt_brl(ci.valor_hora)}")
    lines.append(f"Despesas extras: {_fmt_brl(ci.despesas_extras)}")
    lines.append("")
    lines.append(f"Custo Base: {cr.custo_base_fmt}")
    lines.append(f"Preco Final: {cr.preco_final_fmt}")
    lines.append(f"Validade: {ci.validade_dias} dia(s)")
    text = "\n".join(lines)

    # PDF básico (texto)
    # monta um PDF simples com fonte padrão
    def pdf_escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_stream = "BT\n/F1 14 Tf\n50 760 Td\n"
    y = 0
    for line in text.split("\n"):
        if y != 0:
            content_stream += "0 -18 Td\n"
        content_stream += f"({pdf_escape(line)}) Tj\n"
        y += 1
    content_stream += "ET\n"
    content_bytes = content_stream.encode("latin-1", errors="ignore")

    objects = []
    offsets = []

    def add_obj(s: bytes):
        offsets.append(sum(len(o) for o in objects))
        objects.append(s)

    # PDF header
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    objects.append(header)

    # 1) catalog
    add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2) pages
    add_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3) page
    add_obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")
    # 4) font
    add_obj(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    # 5) contents
    add_obj(f"5 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n".encode("utf-8") + content_bytes + b"\nendstream\nendobj\n")

    # xref
    xref_start = sum(len(o) for o in objects)
    # compute real offsets (including header)
    # rebuild xref offsets by scanning objects is complex; we used running offsets list
    # Let's compute actual offsets by re-walking
    full = b"".join(objects)
    # But we need xref entries; easiest: compute by finding "1 0 obj" etc offsets
    # We'll do a simple find
    def find_offset(marker: bytes) -> int:
        return full.find(marker)

    off1 = find_offset(b"1 0 obj")
    off2 = find_offset(b"2 0 obj")
    off3 = find_offset(b"3 0 obj")
    off4 = find_offset(b"4 0 obj")
    off5 = find_offset(b"5 0 obj")

    xref = "xref\n0 6\n0000000000 65535 f \n".encode("utf-8")
    for off in [off1, off2, off3, off4, off5]:
        xref += f"{off:010d} 00000 n \n".encode("utf-8")

    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("utf-8")

    return full + xref + trailer

# ============================================================
# TELAS + FLUXO
# ============================================================

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Arte Preço Pro</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <meta name="theme-color" content="#4E683E" />
  <link rel="icon" href="/static/icon-192.png" />
  <link rel="apple-touch-icon" href="/static/icon-192.png" />
  <style>
    :root{
      --bg:#DCE6D5;
      --card:#EAF1E6;
      --dark:#4E683E;
      --dark2:#3B5330;
      --txt:#1a1a1a;
      --muted:#444;
      --radius:18px;
    }
    body{
      margin:0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background:var(--bg);
      color:var(--txt);
    }
    .wrap{
      max-width:760px;
      margin:0 auto;
      padding:18px;
    }
    .card{
      background:var(--card);
      border-radius:var(--radius);
      padding:18px;
      box-shadow:0 4px 16px rgba(0,0,0,.08);
      margin-bottom:18px;
    }
    h1{
      margin:0 0 10px 0;
      font-size:28px;
      letter-spacing:.3px;
    }
    h2{
      margin:0 0 10px 0;
      font-size:18px;
      color:var(--dark2);
    }
    .row{
      display:flex;
      gap:12px;
      flex-wrap:wrap;
    }
    .col{
      flex:1;
      min-width:220px;
    }
    label{
      display:block;
      font-weight:700;
      margin:10px 0 6px;
      color:var(--muted);
    }
    input{
      width:100%;
      box-sizing:border-box;
      border:1px solid rgba(0,0,0,.12);
      border-radius:14px;
      padding:12px 12px;
      font-size:16px;
      outline:none;
      background:#fff;
    }
    input:focus{
      border-color:rgba(78,104,62,.45);
      box-shadow:0 0 0 3px rgba(78,104,62,.15);
    }
    .btn{
      width:100%;
      border:0;
      padding:14px 14px;
      font-size:18px;
      font-weight:800;
      border-radius:14px;
      cursor:pointer;
      background:var(--dark);
      color:#fff;
      margin-top:14px;
    }
    .btn:active{ transform: translateY(1px); }
    .btn.secondary{
      background:#6b6b6b;
    }
    .btn.outline{
      background:transparent;
      color:var(--dark);
      border:2px solid var(--dark);
    }
    .small{
      font-size:14px;
      color:#333;
      margin-top:6px;
    }
    .result{
      margin-top:18px;
      padding:14px;
      background:#fff;
      border-radius:16px;
      border:1px solid rgba(0,0,0,.10);
    }
    .big{
      font-size:34px;
      font-weight:900;
      color:#000;
      margin-top:4px;
    }
    .muted{
      color:#444;
      font-size:15px;
    }
    .warn{
      margin-top:10px;
      color:#7a4b00;
      font-weight:700;
    }
    .footer-actions{
      display:flex;
      gap:12px;
      margin-top:14px;
      flex-wrap:wrap;
    }
    .footer-actions .btn{
      flex:1;
      min-width:220px;
      margin-top:0;
    }
  </style>
  <script>
    // Registra o Service Worker (para instalação/offline)
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(()=>{});
      });
    }
  </script>
</head>
<body>
  <div class="wrap">
    {% if not activated %}
      <div class="card">
        <h1>Ativação do Arte Preço Pro</h1>
        <div class="small">Cole a chave AP-... (uma vez). O app lembra automaticamente.</div>
        <form method="POST" action="/ativar">
          <label>Chave</label>
          <input name="chave" placeholder="Cole sua chave AP-..." required />
          <button class="btn" type="submit">Ativar</button>
        </form>
        {% if msg %}
          <div class="warn">{{msg}}</div>
        {% endif %}
      </div>
    {% else %}
      <div class="card">
        <h1>Arte Preço Pro</h1>
        <div class="small">Preencha e clique em <b>Calcular</b>. Depois gere o PDF.</div>

        <form method="POST" action="/calcular">
          <label>Produto</label>
          <input name="produto" value="{{form.produto}}" placeholder="Ex: Logo" required />

          <label>Custo do Material (R$)</label>
          <input name="custo_material" value="{{form.custo_material}}" placeholder="Ex: 10" inputmode="decimal" required />

          <div class="row">
            <div class="col">
              <label>Horas Trabalhadas</label>
              <input name="horas_trabalhadas" value="{{form.horas_trabalhadas}}" placeholder="Ex: 4" inputmode="decimal" required />
            </div>
            <div class="col">
              <label>Valor da Hora (R$)</label>
              <input name="valor_hora" value="{{form.valor_hora}}" placeholder="Ex: 30" inputmode="decimal" required />
            </div>
          </div>

          <label>Despesas Extras (R$)</label>
          <input name="despesas_extras" value="{{form.despesas_extras}}" placeholder="Ex: 2" inputmode="decimal" required />

          <label>Margem de Lucro (%)</label>
          <input name="margem_lucro_pct" value="{{form.margem_lucro_pct}}" placeholder="Ex: 80" inputmode="decimal" required />

          <label>Validade (dias)</label>
          <input name="validade_dias" value="{{form.validade_dias}}" placeholder="Ex: 7" inputmode="numeric" required />

          <button class="btn" type="submit">Calcular</button>
        </form>

        {% if result %}
          <div class="result">
            <div><b>Produto:</b> {{result.produto}}</div>
            <div><b>Custo Base:</b> {{result.custo_base_fmt}}</div>
            <div class="big">Preço Final: {{result.preco_final_fmt}}</div>
            <div class="muted">Validade: {{result.validade_dias}} dia(s)</div>

            <div class="footer-actions">
              <form method="GET" action="/pdf" style="flex:1;">
                <button class="btn outline" type="submit">Gerar PDF</button>
              </form>

              <form method="GET" action="/empresa" style="flex:1;">
                <button class="btn outline" type="submit">Dados da empresa</button>
              </form>

              <form method="GET" action="/cliente" style="flex:1;">
                <button class="btn outline" type="submit">Dados do cliente</button>
              </form>
            </div>
          </div>
        {% endif %}
      </div>

      <div class="card">
        <div class="footer-actions">
          <form method="POST" action="/sair" style="flex:1;">
            <button class="btn secondary" type="submit">Sair</button>
          </form>
          <form method="POST" action="/revalidar" style="flex:1;">
            <button class="btn" type="submit">Revalidar chave</button>
          </form>
        </div>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""
