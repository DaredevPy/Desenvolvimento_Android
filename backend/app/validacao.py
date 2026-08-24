# backend/app/validacao.py
# Limites de tamanho para campos JSON livres (doc 08 §4.1: schemas estritos).
# O esquema formal desses objetos permanece decisão pendente (STATUS §8);
# aqui apenas se rejeita entrada excessiva.
import json
from typing import Any

MAX_JSON_CAMPO = 4000


def exigir_json_compacto(nome_campo: str, valor: Any) -> Any:
    if len(json.dumps(valor, ensure_ascii=False)) > MAX_JSON_CAMPO:
        raise ValueError(f"{nome_campo} excede o tamanho máximo de {MAX_JSON_CAMPO} caracteres.")
    return valor
