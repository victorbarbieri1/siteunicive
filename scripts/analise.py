"""Monta a análise de carreira de um curso.

Prioridade: análise gerada pelo Claude (data/carreira/<slug>.json) quando
existir e estiver atualizada; senão, composição da base curada (área +
modalidade) com os dados reais do curso. Os dois caminhos devolvem o mesmo
formato, então o site e o agente consomem uma estrutura única.
"""
import json
import re

from carreira_base import area_do_curso, modalidade_do_curso

REGULAMENTADAS = r"CRC|OAB|COREN|CRF|CRN|CREFITO|CREF\b|CRO\b|CRP|CRBM|CRESS|CRMV|CREA|CAU|CRECI|CRQ|CRBio"

OBJECOES = {
    "comum": [
        ("Não tenho tempo para estudar.", "A modalidade {fmt} foi pensada para quem trabalha: você organiza o estudo na sua rotina. Vale entender quantas horas por semana a pessoa tem e mostrar como a carga do curso se encaixa."),
        ("Está caro / não cabe no orçamento agora.", "{preco}Vale apresentar o parcelamento, as bolsas e os convênios disponíveis (página Bolsas e Benefícios) e comparar o investimento com o retorno na carreira."),
        ("Curso EAD tem o mesmo valor?", "Sim. O Unicive é credenciado pelo MEC e o certificado/diploma de cursos regulares EAD tem a mesma validade que o presencial."),
        ("Vou pensar / depois eu vejo.", "Entenda o que falta para decidir (preço, tempo, dúvida sobre a carreira) e combine um próximo passo concreto. Não pressione."),
    ],
    "pos": [("Já tenho graduação, pós faz diferença?", "Em planos de carreira, concursos e processos seletivos a especialização costuma pontuar e diferencia o currículo num mercado concorrido.")],
    "segunda-graduacao": [("Começar outra faculdade do zero é demorado.", "Na 2ª graduação há aproveitamento de estudos da primeira formação, o que reduz o tempo até o novo diploma.")],
    "tecnologo": [("Tecnólogo é curso superior mesmo?", "Sim, é graduação de nível superior reconhecida pelo MEC; permite pós-graduação e concursos de nível superior.")],
    "tecnico-tecnologo": [("Já tenho o técnico, por que fazer tecnólogo?", "Você aproveita o técnico e conquista um diploma de nível superior em menos tempo, o que abre promoções, concursos e pós.")],
    "livre": [("Curso livre vale alguma coisa?", "É uma forma rápida de aprender uma competência aplicável já no trabalho e comprovar com certificado; não substitui graduação nem habilita profissões regulamentadas.")],
    "aperfeicoamento": [("Qual a diferença para uma pós?", "O aperfeiçoamento é mais curto e focado; a pós (especialização) é mais completa. Pode ser um bom primeiro passo.")],
    "profissionalizante": [("Isso me ajuda a conseguir emprego?", "O foco é ensinar uma ocupação de forma prática para o mercado; vale entender qual vaga a pessoa busca para mostrar a aderência.")],
    "preparatorio": [("Já estudo sozinho.", "O preparatório organiza o conteúdo do edital e economiza tempo de estudo.")],
    "licenciatura": [("Professor ganha pouco.", "Há piso nacional do magistério com progressões por titulação, estabilidade via concurso e falta de professores em várias disciplinas.")],
}

PERGUNTAS = {
    "comum": ["Você já trabalha na área ou quer migrar para ela?", "O que te motivou a buscar este curso agora?", "Quanto tempo por semana você consegue dedicar aos estudos?"],
    "pos": ["Qual é a sua graduação e há quanto tempo se formou?", "Você busca promoção, mudança de área ou pontos em concurso/plano de carreira?"],
    "segunda-graduacao": ["Qual é a sua primeira graduação?", "Você quer mudar de carreira ou complementar a atual?"],
    "tecnico-tecnologo": ["Qual curso técnico você concluiu e quando?"],
    "tecnologo": ["Você já concluiu o ensino médio? Já iniciou outra graduação?"],
    "bacharelado": ["Você já concluiu o ensino médio? Já iniciou outra graduação?"],
    "licenciatura": ["Você já atua em sala de aula ou quer começar a lecionar?"],
    "livre": ["Que resultado prático você espera alcançar com o curso?"],
    "aperfeicoamento": ["Que resultado prático você espera alcançar com o curso?"],
    "profissionalizante": ["Você está buscando o primeiro emprego, recolocação ou renda extra?"],
    "preparatorio": ["Para qual concurso ou exame você está se preparando e quando é a prova?"],
}


def _br(m):
    inteiro, dec = m.group(1), m.group(2)
    return "R$ " + f"{int(inteiro):,}".replace(",", ".") + "," + dec


def oferta(c):
    """Oferta como publicada no site: {'de': 'R$ 543,94 a mensalidade', 'por': '1+36x R$ 180,45'}."""
    texto = re.sub(r"\s+", " ", ((c.get("investimento") or {}).get("texto") or "")).strip()
    if not texto:
        return {}
    texto = re.sub(r"R\$\s*(\d+)\.(\d{2})(?!\d)", _br, texto)  # 543.94 -> 543,94
    m = re.match(r"(?i)de:\s*(.*?)\s*(por|at[eé]):\s*(.*)$", texto)
    if m:
        por = m.group(3)
        if m.group(2).lower().startswith("at"):
            por = "até " + por
        return {"de": m.group(1), "por": por}
    return {"por": re.sub(r"(?i)^valor:\s*", "", texto)}


def ficha_preco(c):
    o = oferta(c)
    if not o.get("por"):
        return ""
    if re.search(r"(?i)consulta", o["por"]):
        return "O valor deste curso é sob consulta: confirme com o atendimento. "
    if re.search(r"(?i)gratuito", o["por"]):
        return "Este curso é gratuito. "
    return f"Condição publicada no site: {o['por']}" + (f" (antes {o['de']})" if o.get("de") else "") + ". "


def diferenciais(c, mod):
    d = []
    if c.get("modalidade"):
        d.append(f"Modalidade {c['modalidade']}" + (" — estudo flexível, no seu ritmo" if "EAD" in c["modalidade"].upper() else ""))
    carga = c.get("carga_horaria_total") or c.get("duracao")
    if carga:
        d.append(f"Duração/carga horária: {carga.lower()}")
    matriz = [re.sub(r"\s*[–-]\s*\d+\s*H\b.*$", "", m, flags=re.I) for m in c.get("matriz_curricular", [])
              if not re.search(r"(?i)optativa|tcc|trabalho de conclus", m)]
    if matriz:
        d.append("Disciplinas como " + ", ".join(matriz[:4]) + (" e outras" if len(matriz) > 4 else ""))
    for co in c.get("coordenacao", [])[:1]:
        tit = re.search(r"(?i)(p[oó]s-?doutor|doutor|mestre|mestrado|doutorado)", co.get("curriculo", ""))
        d.append(f"Coordenação de {co['nome']}" + (f" ({tit.group(1).lower()})" if tit else ""))
    for k, v in (c.get("outras_secoes") or {}).items():
        if "diferencia" in k.lower():
            d += [re.sub(r"^[–\-•\s]+", "", x) for x in v[:3]]
    o = oferta(c)
    if o.get("por") and not re.search(r"(?i)consulta", o["por"]):
        d.append(f"Investimento: {o['por']}" + (f" (antes {o['de']})" if o.get("de") else ""))
    return d


def analise_base(c):
    area = area_do_curso(c["titulo"], c.get("categorias", []), c.get("centro", []))
    mod = modalidade_do_curso(c.get("modalidade"), c["titulo"], c.get("categorias", []))
    registro = area["registro"]
    if mod["id"] in ("pos", "aperfeicoamento", "livre", "profissionalizante", "preparatorio") and re.search(REGULAMENTADAS, registro):
        registro += " Atenção: este curso complementa a formação, mas não substitui a graduação exigida para o registro profissional."
    salario = area["salario"]
    if mod["id"] in ("livre", "aperfeicoamento", "preparatorio"):
        salario = "Este tipo de curso não define salário por si só; ele fortalece o currículo e a atuação. Referência da área: " + salario
    fmt = c.get("modalidade") or mod["nome"]
    objecoes = [{"objecao": o, "resposta": r.format(fmt=fmt, preco=ficha_preco(c))}
                for o, r in OBJECOES["comum"] + OBJECOES.get(mod["id"], [])]
    return {
        "fonte": "base",
        "area": {"id": area["id"], "nome": area["nome"]},
        "modalidade": {"id": mod["id"], "nome": mod["nome"], "valor": mod["valor"], "para_quem": mod["para_quem"]},
        "resumo": f"{c['titulo']} ({c.get('modalidade') or mod['nome']}) prepara para a área de {area['nome']}. {mod['valor'].split('. ')[0].rstrip('.')}.",
        "a_profissao": area["profissao"],
        "areas_atuacao": area["atuacao"],
        "mercado_trabalho": area["mercado"],
        "tendencias": area["tendencias"],
        "faixa_salarial": salario,
        "registro_profissional": registro,
        "perfil_ideal": area["perfil"],
        "diferenciais_do_curso": diferenciais(c, mod),
        "argumentos_sdr": mod["argumentos"] + area["gancho_sdr"],
        "objecoes": objecoes,
        "perguntas_qualificacao": PERGUNTAS["comum"] + PERGUNTAS.get(mod["id"], []),
    }


def analise(c, carreira_dir=None):
    base = analise_base(c)
    if carreira_dir:
        arq = carreira_dir / f"{c['slug']}.json"
        if arq.exists():
            from carreira_ia import hash_curso
            dado = json.loads(arq.read_text(encoding="utf-8"))
            if dado.get("hash") == hash_curso(c):
                ia = dado["analise"]
                return {**base, **{k: v for k, v in ia.items() if v}, "fonte": "ia"}
    return base
