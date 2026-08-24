# backend/app/rate_limit.py
# Rate limiting por IP com janela deslizante em memória (doc 08 §4.4).
# Limite <= 0 desativa o mecanismo: desenvolvimento local e suíte de testes
# permanecem intactos; a implantação ativa via variáveis de ambiente
# (backend/.env.example). Estado é por processo — pendência registrada para
# store compartilhado caso a API escale horizontalmente.
import math
import os
import threading
import time

JANELA_SEGUNDOS = int(os.getenv("RATE_LIMIT_JANELA_SEGUNDOS", "60"))
LIMITE_LOGIN = int(os.getenv("RATE_LIMIT_LOGIN_MAX", "0"))
LIMITE_REGISTRO = int(os.getenv("RATE_LIMIT_REGISTRO_MAX", "0"))

_lock = threading.Lock()
_janelas: dict[str, list[float]] = {}


def registrar_tentativa(escopo: str, limite: int, chave: str) -> int | None:
    """Registra a tentativa do escopo/chave. Devolve None quando permitida;
    quando bloqueada, devolve os segundos restantes da janela (Retry-After).
    Tentativas bloqueadas não prorrogam a janela."""
    if limite <= 0:
        return None
    agora = time.monotonic()
    with _lock:
        janela = _janelas.setdefault(f"{escopo}:{chave}", [])
        while janela and agora - janela[0] >= JANELA_SEGUNDOS:
            janela.pop(0)
        if len(janela) >= limite:
            return max(1, math.ceil(JANELA_SEGUNDOS - (agora - janela[0])))
        janela.append(agora)
        return None


def limpar_estado() -> None:
    """Zera os contadores (uso exclusivo da suíte de testes)."""
    with _lock:
        _janelas.clear()
