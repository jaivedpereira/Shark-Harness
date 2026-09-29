"""nano-harness (nh) — um harness de agente com arquitetura "tudo é plugin".

Inspirado no DeepSeek Harness (dsh): um núcleo mínimo que só sabe registrar e
invocar ferramentas; todo o resto (shell, arquivos, agendamento, controle do
dispositivo) entra como plugin.

Três frentes usam o MESMO registry de ferramentas:
  - servidor MCP  (nh/mcp_server.py)  → Claude Code, Cursor, OpenCode/LunaCode
  - CLI           (nh/cli.py)         → humano no terminal
  - agente LLM    (nh/agent.py)       → function calling
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
