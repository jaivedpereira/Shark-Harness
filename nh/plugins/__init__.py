"""Plugins do Shark Harness.

Cada módulo aqui expõe uma função `register(reg)` e registra suas ferramentas.
Para criar um plugin novo: crie `meu_plugin.py` neste diretório com

    from ..core import Registry

    def register(reg: Registry) -> None:
        reg.add(minha_funcao, risk="safe", plugin="meu_plugin")

e pronto — o núcleo descobre sozinho no próximo boot.
"""
