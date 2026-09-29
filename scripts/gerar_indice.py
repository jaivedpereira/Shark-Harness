"""Gera o index.json do marketplace a partir dos plugins em marketplace/plugins.

Calcula o sha256 de cada arquivo (é o que o instalador confere) e valida que o
risco declarado no MANIFEST bate com o que o código faz de verdade.
"""

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nh.market import conferir_manifesto, conferir_risco  # noqa: E402

PASTA = RAIZ / "marketplace" / "plugins"
SAIDA = RAIZ / "marketplace" / "index.json"
BASE_URL = "https://raw.githubusercontent.com/jaivedpereira/Shark-Harness/main/marketplace/plugins"

KITS = [
    {"id": "dev", "nome": "Kit Dev", "descricao": "Para programar: versionamento no dia a dia.",
     "plugins": ["git"]},
    {"id": "obras", "nome": "Kit Obras", "descricao": "Cálculo de construção civil (Edificações).",
     "plugins": ["obras"]},
    {"id": "essencial", "nome": "Kit Essencial",
     "descricao": "O que eu instalaria primeiro: versionamento + utilidades de texto.",
     "plugins": ["git", "texto"]},
]


def ferramentas_do_codigo(codigo: str) -> list[str]:
    """Lê os reg.add(...) do código para listar as ferramentas sem executar nada."""
    return sorted(set(re.findall(r"reg\.add\(\s*([a-zA-Z_][\w]*)", codigo)))


def main() -> int:
    plugins = []
    problemas_totais = 0
    for arq in sorted(PASTA.glob("*.py")):
        codigo = arq.read_text(encoding="utf-8")
        man = conferir_manifesto(codigo)
        if not man:
            print(f"❌ {arq.name}: sem MANIFEST — o marketplace precisa dele")
            problemas_totais += 1
            continue
        risco = str(man.get("risco_max", "safe"))
        problemas = conferir_risco(codigo, risco)
        marca = "✅" if not problemas else "❌"
        print(f"{marca} {arq.name:10} risco={risco:6} ferramentas={len(ferramentas_do_codigo(codigo))}")
        for p in problemas:
            print(f"     ⚠️  {p}")
            problemas_totais += 1

        plugins.append({
            "id": man.get("id", arq.stem),
            "nome": man.get("nome", arq.stem),
            "versao": man.get("versao", "1.0.0"),
            "autor": man.get("autor", ""),
            "categoria": man.get("categoria", "outros"),
            "descricao": man.get("descricao", ""),
            "risco_max": risco,
            "requer": man.get("requer", []),
            "tags": man.get("tags", []),
            "plataformas": man.get("plataformas", []),
            "ferramentas": ferramentas_do_codigo(codigo),
            "sha256": hashlib.sha256(codigo.encode("utf-8")).hexdigest(),
            "tamanho": len(codigo.encode("utf-8")),
            "arquivo": f"{arq.stem}.py",
            "url": f"{BASE_URL}/{arq.stem}.py",
        })

    indice = {
        "versao": 1,
        "atualizado": date.today().isoformat(),
        "repositorio": "https://github.com/jaivedpereira/Shark-Harness",
        "plugins": plugins,
        "kits": KITS,
    }
    SAIDA.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n✅ {SAIDA.relative_to(RAIZ)} — {len(plugins)} plugin(s), {len(KITS)} kit(s)")
    if problemas_totais:
        print(f"⚠️  {problemas_totais} problema(s) de risco — o instalador vai recusar esses plugins")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
