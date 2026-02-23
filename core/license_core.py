# core/license_core.py
import hmac
import hashlib
import base64
import json
import time

# 🔑 SEGREDO DO SEU APP (troque depois para um texto seu)
SECRET = b"ARTEPRECO_CHAVE_UNICA_2026_SEGREDO_FORTE_TROQUE_ISSO"

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def gerar_chave(cliente: str, dias_validade: int) -> str:
    payload = {
        "c": (cliente or "").strip().upper(),
        "exp": int(time.time()) + int(dias_validade) * 24 * 3600
    }
    msg = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(SECRET, msg, hashlib.sha256).digest()
    token = _b64url_encode(msg) + "." + _b64url_encode(sig)
    return "AP-" + token

def validar_chave(chave: str):
    try:
        chave = (chave or "").strip()

        if not chave.startswith("AP-"):
            return False, "Formato inválido."

        token = chave[3:]
        parts = token.split(".")
        if len(parts) != 2:
            return False, "Formato inválido."

        msg_b64, sig_b64 = parts
        msg = _b64url_decode(msg_b64)
        sig = _b64url_decode(sig_b64)

        sig_calc = hmac.new(SECRET, msg, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, sig_calc):
            return False, "Chave inválida."

        payload = json.loads(msg.decode("utf-8"))
        exp = int(payload.get("exp", 0))
        cliente = payload.get("c", "CLIENTE")

        if time.time() > exp:
            return False, "Chave expirada."

        return True, f"Ativado para {cliente}"
    except Exception:
        return False, "Chave inválida."
