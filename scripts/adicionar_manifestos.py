"""Insere um bloco MANIFEST nos plugins embutidos (idempotente).

O marketplace lê o MANIFEST para mostrar nome, categoria, risco máximo e versão.
Os plugins que eu escrevi à mão já têm; este script completa os que faltam.
Rodar de novo não duplica nada.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

MANIFESTOS = {
    "shell": ("Terminal do dispositivo", "Rodar comandos no PC, Linux ou Termux: instalar pacote, usar git, mover arquivo.",
              "exec", "sistema", ["shell", "comando", "terminal"]),
    "code": ("Programar e testar", "Escrever e executar Python ou Node na hora, sem criar arquivo na mão.",
             "exec", "dev", ["python", "node", "código"]),
    "files": ("Arquivos", "Ler, escrever, listar, procurar por nome e por conteúdo, criar pasta e apagar.",
              "danger", "sistema", ["arquivo", "pasta", "disco"]),
    "net": ("Internet e APIs", "Consultar APIs, baixar arquivo, testar se um serviço está no ar, IP, CEP e clima.",
            "write", "rede", ["http", "api", "download", "cep", "clima"]),
    "archive": ("Backup e integridade", "Compactar em zip/tar.gz, extrair, conferir hash e achar o que ocupa espaço.",
                "write", "sistema", ["backup", "zip", "hash"]),
    "proc": ("Processos e serviços", "Ver o que está rodando, ver os processos do harness e encerrar o que travou.",
             "danger", "sistema", ["processo", "serviço", "matar"]),
    "schedule": ("Tarefas agendadas", "Criar tarefa que roda sozinha no horário (cron próprio), listar, pausar e remover.",
                 "exec", "automação", ["cron", "agendador", "automação"]),
    "device": ("Controle do aparelho", "Notificação, print de tela, área de transferência e abrir link/app.",
               "write", "dispositivo", ["android", "termux", "notificação"]),
    "sysinfo": ("Saúde do sistema", "RAM, disco, bateria, uptime e relógio — para saber se cabe tarefa pesada.",
                "safe", "sistema", ["ram", "disco", "bateria"]),
    "meta": ("Auto-conhecimento", "Listar as ferramentas, ver os parâmetros de uma e ler o histórico de auditoria.",
             "safe", "núcleo", ["ferramentas", "auditoria"]),
    "doctor": ("Diagnóstico", "Testar se a escrita de arquivo funciona e checar o ambiente inteiro.",
               "write", "núcleo", ["diagnóstico", "debug", "ambiente"]),
}

PLATAFORMAS = '["linux", "windows", "darwin", "android"]'


def inserir(caminho: Path, dados: tuple) -> bool:
    nome, descricao, risco, categoria, tags = dados
    texto = caminho.read_text(encoding="utf-8")
    if "MANIFEST = {" in texto:
        return False  # já tem

    linhas = texto.splitlines(keepends=True)
    # acha o fim do docstring do módulo (segunda ocorrência de """)
    fim = None
    contador = 0
    for i, linha in enumerate(linhas):
        if linha.lstrip().startswith('"""'):
            contador += linha.count('"""')
            if contador >= 2:
                fim = i
                break
    if fim is None:
        return False

    tags_txt = ", ".join(f'"{t}"' for t in tags)
    bloco = (
        "\nMANIFEST = {\n"
        f'    "id": "{caminho.stem}",\n'
        f'    "nome": "{nome}",\n'
        '    "versao": "1.0.0",\n'
        '    "autor": "jaivedpereira",\n'
        f'    "categoria": "{categoria}",\n'
        f'    "descricao": "{descricao}",\n'
        f'    "risco_max": "{risco}",\n'
        f'    "plataformas": {PLATAFORMAS},\n'
        '    "requer": [],\n'
        f'    "tags": [{tags_txt}],\n'
        "}\n"
    )
    linhas.insert(fim + 1, bloco)
    caminho.write_text("".join(linhas), encoding="utf-8")
    return True


def main() -> int:
    pasta = RAIZ / "nh" / "plugins"
    mudou = 0
    for nome, dados in MANIFESTOS.items():
        arq = pasta / f"{nome}.py"
        if not arq.is_file():
            print(f"⚠️  {arq.name} não existe")
            continue
        if inserir(arq, dados):
            print(f"✅ {arq.name}: manifesto adicionado")
            mudou += 1
        else:
            print(f"•  {arq.name}: já tinha")
    print(f"\n{mudou} arquivo(s) alterado(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
