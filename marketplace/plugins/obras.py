"""Plugin: obras — cálculo de construção civil (Edificações).

Ferramentas de estimativa para estudo e orçamento: concreto, aço CA-50 (tabela
NBR 7480), reboco, rampa (NBR 9050) e conversão de unidades.

Os números seguem valores usuais de obra e tabelas normativas, mas são ESTIMATIVA:
para projeto assinado, use o dimensionamento do responsável técnico.
"""

from __future__ import annotations

import math

MANIFEST = {
    "id": "obras",
    "nome": "Cálculo de Obras",
    "versao": "1.0.0",
    "autor": "jaivedpereira",
    "categoria": "engenharia",
    "descricao": "Concreto, aço CA-50, reboco, rampa e conversão de unidades para construção civil.",
    "risco_max": "safe",
    "plataformas": ["linux", "windows", "darwin", "android"],
    "requer": [],
    "tags": ["construção", "engenharia", "nbr", "edificações"],
}

# massa nominal do aço CA-50 por metro (NBR 7480) — kg/m
ACO_CA50 = {6.3: 0.245, 8.0: 0.395, 10.0: 0.617, 12.5: 0.963,
            16.0: 1.578, 20.0: 2.466, 25.0: 3.853, 32.0: 6.313}

# consumo aproximado de material por m3 de concreto pronto (obra comum)
CONSUMO_CONCRETO = {  # fck -> (cimento kg, areia m3, brita m3, água L)
    20: (300, 0.60, 0.80, 175),
    25: (350, 0.65, 0.85, 180),
    30: (400, 0.70, 0.90, 185),
    35: (430, 0.72, 0.92, 190),
}


def concreto_volume(comprimento: float, largura: float, altura: float, fck: int = 25) -> str:
    """Calcula o volume de concreto de uma peça e o material necessário.

    Args:
        comprimento: comprimento em metros (ex.: 5.0).
        largura: largura ou espessura em metros (ex.: 0.20).
        altura: altura ou espessura em metros (ex.: 0.40).
        fck: resistência do concreto em MPa (20, 25, 30 ou 35).
    """
    vol = float(comprimento) * float(largura) * float(altura)
    chave = min(CONSUMO_CONCRETO, key=lambda k: abs(k - int(fck)))
    cim, are, bri, agua = CONSUMO_CONCRETO[chave]
    sacos = -(-int(round(cim * vol)) // 50)  # arredonda para cima, saco de 50 kg
    return (f"🧱 CONCRETO — {comprimento}m x {largura}m x {altura}m (fck {chave} MPa)\n"
            f"   volume........: {vol:.3f} m³\n"
            f"   cimento.......: {cim * vol:.0f} kg  ({sacos} sacos de 50 kg)\n"
            f"   areia média...: {are * vol:.3f} m³\n"
            f"   brita 1.......: {bri * vol:.3f} m³\n"
            f"   água..........: {agua * vol:.0f} L\n"
            f"   (estimativa de obra — não substitui o traço do responsável técnico)")


def peso_aco(bitola: float, comprimento: float = 12.0, barras: int = 1) -> str:
    """Peso do aço CA-50 pela tabela NBR 7480 (kg por metro de cada bitola).

    Args:
        bitola: diâmetro em mm — use 6.3, 8, 10, 12.5, 16, 20, 25 ou 32.
        comprimento: comprimento de cada barra em metros (padrão da barra: 12 m).
        barras: quantidade de barras.
    """
    b = float(bitola)
    if b not in ACO_CA50:
        proximo = min(ACO_CA50, key=lambda k: abs(k - b))
        return (f"❌ bitola {b} mm não é padrão CA-50.\n"
                f"   Disponíveis: {', '.join(str(k) for k in ACO_CA50)}\n"
                f"   A mais próxima é {proximo} mm ({ACO_CA50[proximo]} kg/m).")
    por_metro = ACO_CA50[b]
    total_m = float(comprimento) * int(barras)
    kg = por_metro * total_m
    return (f"🔩 AÇO CA-50 ø{b:g} mm\n"
            f"   {por_metro} kg/m  ·  {int(barras)} barra(s) de {comprimento} m = {total_m:.1f} m\n"
            f"   peso total: {kg:.2f} kg  ({kg / 1000:.3f} t)\n"
            f"   barras por tonelada: {1000 / (por_metro * float(comprimento)):.1f}")


def reboco_material(area: float, espessura: float = 2.0, traco: str = "1:3") -> str:
    """Material para reboco/argamassa: volume, cimento e areia por área de parede.

    Args:
        area: área a revestir em m² (ex.: 45).
        espessura: espessura da camada em cm (padrão 2 cm).
        traco: traço em volume cimento:areia — "1:3" (parede) ou "1:4" (mais econômico).
    """
    esp_m = float(espessura) / 100
    vol = float(area) * esp_m
    try:
        partes = [float(x) for x in str(traco).replace(",", ":").split(":") if x.strip()]
        cim_p, are_p = (partes[0], partes[1]) if len(partes) >= 2 else (1.0, 3.0)
    except ValueError:
        cim_p, are_p = 1.0, 3.0
    # consumo de cimento por m3 de argamassa conforme o traço (valores usuais de obra)
    k_cimento = {1.0: 600, 2.0: 480, 3.0: 400, 4.0: 340}.get(round(cim_p * (3 / are_p), 2), 400)
    cimento = k_cimento * vol
    areia = vol * (are_p / cim_p) * 0.62
    return (f"🧱 REBOCO — {area} m² com {espessura} cm (traço {cim_p:g}:{are_p:g})\n"
            f"   volume de argamassa: {vol:.3f} m³\n"
            f"   cimento............: {cimento:.0f} kg ({-(-int(cimento) // 50)} sacos de 50 kg)\n"
            f"   areia média........: {areia:.3f} m³\n"
            f"   (+ 8% de perda é comum em obra: cimento {-(-int(cimento * 1.08) // 50)} sacos)")


def rampa_inclinacao(altura: float, comprimento: float) -> str:
    """Inclinação de rampa em % e o limite da NBR 9050 (acessibilidade).

    Args:
        altura: desnível a vencer em cm (ex.: 60).
        comprimento: projeção horizontal disponível em cm (ex.: 900).
    """
    h, c = float(altura), float(comprimento)
    if c <= 0:
        return "❌ o comprimento tem que ser maior que zero."
    pct = h / c * 100
    ang = math.degrees(math.atan2(h, c))
    if pct <= 5:
        classe = "dentro do limite, com folga — rampa confortável"
    elif pct <= 8.33:
        classe = "dentro do limite da NBR 9050 (o máximo é 8,33%)"
    elif pct <= 12.5:
        classe = "acima de 8,33% — aceitável só em rampa existente/reforma"
    else:
        classe = "ACIMA do permitido (máx. 12,5% em reforma) — precisa alongar a rampa"
    # quanto de rampa seria necessário para ficar no limite confortável
    min_c = h / 0.0833
    extra = (f"   comprimento mínimo para 8,33%: {min_c:.0f} cm "
             f"({(min_c - c) / 100:+.2f} m em relação ao atual)"
             if pct > 8.33 else
             f"   desnível máximo nesse comprimento: {c * 0.0833:.0f} cm")
    return (f"♿ RAMPA — desnível {h:g} cm em {c:g} cm\n"
            f"   inclinação: {pct:.2f}%  (1:{c / h:.1f})  ·  ângulo {ang:.1f}°\n"
            f"   NBR 9050: {classe}\n"
            f"{extra}")


def tijolos_parede(area: float, tipo: str = "9x19x39", perda: float = 8.0) -> str:
    """Quantos tijolos e quanto de argamassa para levantar uma parede.

    Args:
        area: área da parede em m² (desconte portas e janelas).
        tipo: bloco "9x19x39" (9 furos, o mais comum), "14x19x39" ou "tijolo maciço".
        perda: percentual de perda (padrão 8%).
    """
    consumos = {"9x19x39": (12.5, 0.012), "14x19x39": (12.5, 0.018), "maciço": (25.0, 0.020)}
    chave = next((k for k in consumos if str(tipo).lower().startswith(k.split("x")[0])), "9x19x39")
    if "maci" in str(tipo).lower():
        chave = "maciço"
    por_m2, vol_junta = consumos[chave]
    qtd = float(area) * por_m2 * (1 + float(perda) / 100)
    arg = float(area) * vol_junta * (1 + float(perda) / 100)
    return (f"🧱 PAREDE — {area} m² com bloco {chave} (perda {perda:g}%)\n"
            f"   blocos.........: {-(-int(qtd) // 1)} unidades\n"
            f"   argamassa......: {arg:.3f} m³ (~{-(-int(arg * 400) // 50)} sacos de cimento 50 kg no traço 1:5)\n"
            f"   dica: parede de 1 m² com bloco 9x19x39 gasta ~12,5 blocos")


def converter_unidade(valor: float, de: str, para: str) -> str:
    """Converte unidades comuns de obra (comprimento, área, volume, massa).

    Args:
        valor: número a converter.
        de: unidade de origem (m, cm, mm, m2, cm2, m3, L, kg, t).
        para: unidade de destino.
    """
    grupos = {
        "comprimento": {"m": 1.0, "cm": 0.01, "mm": 0.001, "km": 1000.0},
        "area": {"m2": 1.0, "cm2": 0.0001, "ha": 10000.0},
        "volume": {"m3": 1.0, "l": 0.001, "cm3": 1e-06},
        "massa": {"kg": 1.0, "t": 1000.0, "g": 0.001},
    }
    d, p = str(de).lower().strip(), str(para).lower().strip()
    for nome, tabela in grupos.items():
        if d in tabela and p in tabela:
            r = float(valor) * tabela[d] / tabela[p]
            return f"🔄 {valor} {d} = {r:g} {p}   ({nome})"
    return (f"❌ conversão '{d}' → '{p}' não suportada.\n"
            "   comprimento: m, cm, mm, km · área: m2, cm2, ha\n"
            "   volume: m3, L, cm3 · massa: kg, t, g")


def register(reg) -> None:
    reg.add(concreto_volume, risk="safe", plugin="obras")
    reg.add(peso_aco, risk="safe", plugin="obras")
    reg.add(reboco_material, risk="safe", plugin="obras")
    reg.add(rampa_inclinacao, risk="safe", plugin="obras")
    reg.add(tijolos_parede, risk="safe", plugin="obras")
    reg.add(converter_unidade, risk="safe", plugin="obras")
