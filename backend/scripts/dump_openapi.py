#!/usr/bin/env python3
"""Dump determinístico do OpenAPI schema do app FastAPI.

Uso:
    python backend/scripts/dump_openapi.py

Saída para stdout: JSON com sort_keys=True, ensure_ascii=False, indent=2.
Determinístico: mesmo input -> mesmo output byte-a-byte (sort_keys garante ordem estavel).

Usado pelo gen:api do frontend:
    python backend/scripts/dump_openapi.py | openapi-typescript /dev/stdin ...

Contexto: o frontend nao pode apontar para http://127.0.0.1:8000/openapi.json
diretamente em CI (o backend pode nao estar rodando). Este script gera o
mesmo JSON que o FastAPI serviria, sem precisar do servidor HTTP.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Forca stdout UTF-8 (necessario no Windows com cp1252 default)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")

# Garante que o src do backend esta no path
src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src))

from blog.main import create_app  # noqa: E402

app = create_app()
schema = app.openapi()

# sort_keys=True garante determinismo independente de insercao no dict
# ensure_ascii=False preserva caracteres Unicode (acentos nos descriptions)
# indent=2 para legibilidade e diff legivel no PR
sys.stdout.write(json.dumps(schema, sort_keys=True, ensure_ascii=False, indent=2))
sys.stdout.write("\n")
