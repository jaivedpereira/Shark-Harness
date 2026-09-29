"""Monta o PDF do catálogo de ferramentas do Shark Harness.

Pipeline: dados reais do registry (catalogo_tools.json) + gráficos do matplotlib
-> reportlab Platypus. Capa com o emblema, gráficos, uma seção por plugin.
"""

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

RAIZ = Path(__file__).resolve().parent.parent
BUILD = RAIZ / "pdf_build"
SAIDA = RAIZ / "Shark-Harness-Catalogo-de-Ferramentas.pdf"

AZUL = colors.HexColor("#2563eb")
AZUL_ESC = colors.HexColor("#1e3a8a")
TEXTO = colors.HexColor("#0f172a")
CINZA = colors.HexColor("#64748b")
LINHA = colors.HexColor("#e2e8f0")
FUNDO = colors.HexColor("#f8fafc")
RISCO_COR = {
    "safe": ("#dcfce7", "#166534", "Só leitura"),
    "write": ("#fef9c3", "#854d0e", "Escreve"),
    "exec": ("#ffedd5", "#9a3412", "Executa"),
    "danger": ("#fee2e2", "#991b1b", "Apaga"),
}

dados = json.loads((RAIZ / "catalogo_tools.json").read_text(encoding="utf-8"))

# ── limpeza de texto: Helvetica só aceita Latin-1, então emoji tem que sair ──
EMOJI_MAP = {"🟢": "", "🟡": "", "🟠": "", "🔴": "", "✅": "OK ", "❌": "X ", "⚠️": "! ",
             "⏱️": "", "📄": "", "📂": "", "🌐": "", "🔍": "", "📊": "", "🔐": "",
             "🌍": "", "📮": "", "🌡️": "", "🩺": ""}


def limpar(txt: str) -> str:
    if not txt:
        return ""
    for k, v in EMOJI_MAP.items():
        txt = txt.replace(k, v)
    # remove qualquer coisa fora do Latin-1 (emoji restante, símbolos raros)
    txt = "".join(c for c in txt if c == "\n" or _latin1_ok(c))
    return re.sub(r"\s{2,}", " ", txt).strip()


def _latin1_ok(c: str) -> bool:
    try:
        c.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def esc(txt: str) -> str:
    return limpar(txt).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── estilos ──────────────────────────────────────────────────────────────────
ss = getSampleStyleSheet()
S = {
    "capa_titulo": ParagraphStyle("ct", parent=ss["Title"], fontName="Helvetica-Bold",
                                  fontSize=30, leading=34, textColor=AZUL_ESC, alignment=TA_CENTER),
    "capa_sub": ParagraphStyle("cs", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=13, leading=18, textColor=CINZA, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=19, leading=23, textColor=AZUL_ESC, spaceAfter=4),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=13.5, leading=17, textColor=AZUL, spaceBefore=6, spaceAfter=2),
    "body": ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=10, leading=14.5, textColor=TEXTO, alignment=TA_LEFT),
    "small": ParagraphStyle("sm", parent=ss["Normal"], fontName="Helvetica",
                            fontSize=8.6, leading=12, textColor=CINZA),
    "cell": ParagraphStyle("cl", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=9.2, leading=12.6, textColor=TEXTO),
    "cell_par": ParagraphStyle("cp", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=7.8, leading=10.4, textColor=CINZA),
    "code": ParagraphStyle("cd", parent=ss["Normal"], fontName="Courier",
                           fontSize=9.2, leading=12.6, textColor=AZUL_ESC),
    "legenda": ParagraphStyle("lg", parent=ss["Normal"], fontName="Helvetica-Oblique",
                              fontSize=8.4, leading=11, textColor=CINZA, alignment=TA_CENTER),
}


def caixa(titulo: str, texto: str, cor_bg="#eff6ff", cor_borda="#2563eb") -> Table:
    p = Paragraph(f"<b>{esc(titulo)}</b><br/>{esc(texto)}", S["body"])
    t = Table([[p]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(cor_bg)),
        ("BOX", (0, 0), (-1, -1), 0.9, colors.HexColor(cor_borda)),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def imagem(nome: str, largura: float) -> Image:
    caminho = BUILD / nome
    from PIL import Image as PILImage
    w, h = PILImage.open(caminho).size
    return Image(str(caminho), width=largura, height=largura * h / w)


# ── canvas que sabe o TOTAL de páginas (padrão "Página X de Y") ─────────────
class CanvasNumerado(Canvas):
    """Guarda o estado de cada página e redesenha no final, quando o total é conhecido."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            n = self._pageNumber
            if n > 1:  # não numera a capa
                self.setFont("Helvetica", 8)
                self.setFillColor(CINZA)
                self.drawRightString(19 * cm, 1.45 * cm, f"Página {n} de {total}")
            super().showPage()
        super().save()


class Doc(BaseDocTemplate):
    def __init__(self, arquivo, **kw):
        super().__init__(arquivo, **kw)
        capa = Frame(2 * cm, 2 * cm, 17 * cm, 25.5 * cm, id="capa")
        corpo = Frame(2 * cm, 2.1 * cm, 17 * cm, 24 * cm, id="corpo")
        self.addPageTemplates([
            PageTemplate(id="Capa", frames=[capa]),
            PageTemplate(id="Corpo", frames=[corpo], onPage=self.decorar),
        ])

    def decorar(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.6)
        canvas.line(2 * cm, 1.85 * cm, 19 * cm, 1.85 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(CINZA)
        canvas.drawString(2 * cm, 1.45 * cm, "Shark Harness - catálogo de ferramentas")
        canvas.drawCentredString(10.5 * cm, 1.45 * cm, date.today().strftime("%d/%m/%Y"))
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(AZUL)
        canvas.drawRightString(19 * cm, 28.2 * cm, "SHARK HARNESS")
        canvas.restoreState()


def build():
    doc = Doc(str(SAIDA), pagesize=A4, canvasmaker=CanvasNumerado, title="Shark Harness - Catálogo de Ferramentas",
              author="Shark Harness", subject="Catálogo dos plugins e ferramentas")

    E = []
    # ── CAPA ─────────────────────────────────────────────────────────────────
    E.append(Spacer(1, 1.6 * cm))
    # o emblema tem fundo quase preto: colocamos ele dentro de uma faixa escura
    painel = Table([[imagem("logo_capa.png", 6.4 * cm)]], colWidths=[16.4 * cm])
    painel.setStyle(TableStyle([
        # mesma cor de fundo do emblema: assim ele não parece "colado"
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#080b10")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 24),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 24),
        ("BOX", (0, 0), (-1, -1), 1.2, AZUL),
    ]))
    E.append(painel)
    E.append(Spacer(1, 1.3 * cm))
    E.append(Paragraph("SHARK HARNESS", S["capa_titulo"]))
    E.append(Spacer(1, 0.25 * cm))
    E.append(Paragraph("Catálogo de Ferramentas e Plugins", S["capa_sub"]))
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph(
        f"{dados['total_ferramentas']} ferramentas organizadas em {dados['total_plugins']} plugins",
        S["capa_sub"]))
    E.append(Spacer(1, 1.4 * cm))
    E.append(caixa("Um registro, quatro frentes",
                   "As mesmas ferramentas são usadas pela interface web, pelo servidor MCP "
                   "(Claude Code/Cursor), pela linha de comando (nh) e pelo agente de IA."))
    E.append(Spacer(1, 0.6 * cm))
    E.append(Paragraph(f"Versão 0.1.0 · gerado em {date.today().strftime('%d/%m/%Y')}",
                       S["legenda"]))
    E.append(PageBreak())

    doc.handle_nextPageTemplate("Corpo")

    # ── PÁGINA 2: o que é ────────────────────────────────────────────────────
    E.append(Paragraph("Como o Shark Harness funciona", S["h1"]))
    E.append(Paragraph(
        "O Shark Harness é um agente de tarefas com arquitetura \"tudo é plugin\": "
        "um núcleo mínimo que só sabe registrar e chamar ferramentas. Cada capacidade "
        "(terminal, arquivos, rede, agendamento, controle do aparelho) entra como um plugin "
        "separado, e o mesmo conjunto serve às quatro frentes abaixo.", S["body"]))
    E.append(Spacer(1, 0.45 * cm))
    E.append(imagem("diagrama_frentes.png", 15.0 * cm))
    E.append(Spacer(1, 0.35 * cm))

    E.append(Paragraph("Como ler o nível de risco", S["h2"]))
    legenda = [[Paragraph("<b>Nível</b>", S["cell"]), Paragraph("<b>O que significa</b>", S["cell"]),
                Paragraph("<b>Exemplos</b>", S["cell"])]]
    exemplos = {
        "safe": "ler arquivo, listar pasta, consultar CEP",
        "write": "gravar arquivo, agendar tarefa, baixar arquivo",
        "exec": "rodar comando no terminal, executar código",
        "danger": "apagar arquivo/pasta, matar processo",
    }
    for chave in ("safe", "write", "exec", "danger"):
        bg, fg, rotulo = RISCO_COR[chave]
        legenda.append([
            Paragraph(f'<font backColor="{bg}" color="{fg}"><b> {rotulo} </b></font>', S["cell"]),
            Paragraph(limpar({
                "safe": "Nao altera nada no seu computador.",
                "write": "Cria ou modifica arquivos e agendamentos.",
                "exec": "Executa comandos - passa pela guarda de seguranca.",
                "danger": "Pode destruir dados. Vem bloqueado para a IA por padrao.",
            }[chave]), S["cell"]),
            Paragraph(esc(exemplos[chave]), S["cell"]),
        ])
    t = Table(legenda, colWidths=[2.6 * cm, 7.6 * cm, 6.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUNDO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    E.append(t)
    E.append(Spacer(1, 0.35 * cm))
    E.append(KeepTogether([caixa(
        "O que a guarda bloqueia",
        "Comandos destrutivos (rm -rf /, mkfs, dd no disco, curl | sh, fork bomb) e escrita em "
        "caminhos criticos (~/.bashrc, chaves SSH, /etc) sao recusados - e nao existe flag para "
        "desligar. Tudo o que roda fica registrado em log de auditoria.", "#fef2f2", "#ef4444"),
        imagem("diagrama_guarda.png", 14.0 * cm)]))

    # ── PÁGINA 3: gráficos ───────────────────────────────────────────────────
    E.append(PageBreak())
    E.append(Paragraph("Visão geral", S["h1"]))
    E.append(Paragraph(
        "As 46 ferramentas distribuidas por área e por nível de risco. "
        "A maior parte é de leitura, e só duas podem apagar algo - as duas ficam fora do "
        "alcance da IA por padrão.", S["body"]))
    E.append(Spacer(1, 0.5 * cm))
    E.append(imagem("grafico_areas.png", 15.6 * cm))
    E.append(Spacer(1, 0.7 * cm))
    E.append(imagem("grafico_risco.png", 15.6 * cm))

    # ── SEÇÕES POR PLUGIN ────────────────────────────────────────────────────
    plugins = sorted(dados["plugins"], key=lambda p: -p["qtd"])
    por_plugin = {}
    for tool in dados["tools"]:
        por_plugin.setdefault(tool["plugin"], []).append(tool)

    for idx, plug in enumerate(plugins):
        pid = plug["nome"]
        E.append(PageBreak())
        E.append(Paragraph(f"{esc(plug['titulo'])}", S["h1"]))
        qtd_txt = "1 ferramenta" if plug["qtd"] == 1 else f"{plug['qtd']} ferramentas"
        E.append(Paragraph(
            f"<font color='#2563eb'><b>plugin {pid}</b></font> · {qtd_txt}", S["small"]))
        E.append(Spacer(1, 0.28 * cm))
        E.append(Paragraph(esc(plug["proposito"]), S["body"]))
        E.append(Spacer(1, 0.5 * cm))

        linhas = [[Paragraph("<b>Ferramenta</b>", S["cell"]),
                   Paragraph("<b>Risco</b>", S["cell"]),
                   Paragraph("<b>Para que serve</b>", S["cell"])]]
        for tool in sorted(por_plugin[pid], key=lambda x: x["nome"]):
            bg, fg, rotulo = RISCO_COR[tool["risco"]]
            desc = esc(tool["descricao"])
            if tool["params"]:
                partes = []
                for p in tool["params"]:
                    tipo = {"string": "texto", "integer": "numero", "number": "numero",
                            "boolean": "sim/nao", "array": "lista"}.get(p["tipo"], p["tipo"])
                    obrig = "obrigatorio" if p["obrigatorio"] else "opcional"
                    partes.append(f"{p['nome']} ({tipo}, {obrig})")
                desc += f"<br/><font size=7.6 color='#64748b'>parâmetros: {esc(', '.join(partes))}</font>"
            linhas.append([
                # fonte menor: nomes longos (device_clipboard_escrever) precisam caber
                # numa linha só, senão quebram no meio da palavra
                Paragraph(f"<font face='Courier' size=8.2>{esc(tool['nome'])}</font>", S["cell"]),
                Paragraph(f'<font backColor="{bg}" color="{fg}"><b> {rotulo} </b></font>', S["cell"]),
                Paragraph(desc, S["cell"]),
            ])
        tab = Table(linhas, colWidths=[4.9 * cm, 1.9 * cm, 9.6 * cm], repeatRows=1)
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), FUNDO),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, AZUL),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINHA),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        E.append(tab)

        # o plugin doctor tem só 2 ferramentas: aproveitamos o espaço da página
        # com o passo a passo de uso (senão a página fica quase vazia)
        if pid == "doctor":
            E.append(Spacer(1, 0.6 * cm))
            E.append(KeepTogether([caixa(
                "Quando usar o diagnóstico",
                "Sempre que algo \"não funcionar\", rode o diagnóstico ANTES de mexer em "
                "qualquer coisa. Ele tenta criar, ler e apagar um arquivo de verdade em cada "
                "pasta importante, confere a chave da IA, o termux-api, o agendador e o log - "
                "e devolve a dica de correção de cada problema encontrado.\n\n"
                "nh doctor                      -> diagnóstico completo\n"
                "nh do testar_escrita --args '{\"caminho\": \"/sdcard\"}'   -> testa uma pasta "
                "específica", "#f0fdf4", "#22c55e")]))

    # ── ÚLTIMA: comandos ─────────────────────────────────────────────────────
    E.append(PageBreak())
    E.append(Paragraph("Como usar", S["h1"]))
    E.append(Paragraph(
        "O mesmo comando serve no PC, no Linux e no Termux (celular).", S["body"]))
    E.append(Spacer(1, 0.45 * cm))

    comandos = [
        ("nh doctor", "Diagnóstico: testa a escrita de arquivo de verdade e diz o que corrigir."),
        ("nh web", "Abre a interface no navegador (localhost:8787). No celular vira app instalável."),
        ("nh tools", "Lista as 46 ferramentas com o risco de cada uma."),
        ("nh run \"...\"", "Pede algo ao agente: ele escolhe as ferramentas e executa."),
        ("nh do <nome> --args '{...}'", "Chama uma ferramenta direto, sem IA."),
        ("nh cron add ...", "Agenda uma tarefa recorrente."),
        ("nh cron daemon", "Liga o agendador (roda as tarefas sozinho)."),
        ("nh audit", "Mostra o histórico do que foi executado."),
        ("nh serve", "Sobe o servidor MCP para Claude Code / Cursor."),
    ]
    linhas = [[Paragraph("<b>Comando</b>", S["cell"]), Paragraph("<b>Para que serve</b>", S["cell"])]]
    for cmd, desc in comandos:
        linhas.append([Paragraph(f"<font face='Courier'>{esc(cmd)}</font>", S["code"]),
                       Paragraph(esc(desc), S["cell"])])
    t = Table(linhas, colWidths=[5.6 * cm, 10.8 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), FUNDO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, AZUL),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINHA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    E.append(t)
    E.append(Spacer(1, 0.6 * cm))
    E.append(KeepTogether([
        caixa("Exemplos que já funcionam",
              "nh do cep --args '{\"cep_numero\": \"01001000\"}'  ->  Praça da Sé, São Paulo/SP\n"
              "nh do clima --args '{\"cidade\": \"São Paulo\"}'  ->  temperatura e umidade agora\n"
              "nh do port_check --args '{\"porta\": 8787}'  ->  diz se o teu servidor está no ar\n"
              "nh do zipar --args '{\"origem\": \"~/projetos\"}'  ->  cria um backup",
              "#f0fdf4", "#22c55e")]))
    E.append(Spacer(1, 0.5 * cm))
    E.append(Paragraph(
        "Shark Harness é software livre (MIT). Ele executa comandos de verdade e não é uma "
        "sandbox: rode com o mínimo de privilégios e mantenha backup do que for importante.",
        S["legenda"]))

    doc.build(E)
    print(f"✅ PDF gerado: {SAIDA}")


if __name__ == "__main__":
    build()
