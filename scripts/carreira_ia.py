"""Gera análise de carreira específica por curso com o Claude (opcional).

Roda só quando ANTHROPIC_API_KEY está definida. Usa a Message Batches API
(50% mais barata) e só processa cursos novos ou cujo conteúdo mudou — o hash
do conteúdo fica salvo em data/carreira/<slug>.json.

Sem chave, o build usa a base curada (carreira_base.py), então todo curso
sempre tem análise de carreira.

Uso:  python scripts/carreira_ia.py            # envia e aguarda o lote
      python scripts/carreira_ia.py --limite 20
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from carreira_base import area_do_curso, modalidade_do_curso  # noqa: E402
from sync import DATA, CURSOS_DIR  # noqa: E402

CARREIRA_DIR = DATA / "carreira"
MODELO = "claude-opus-5-5"
VERSAO_PROMPT = "v1"

SCHEMA = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string", "description": "2-3 frases: o que a formação proporciona para a carreira"},
        "a_profissao": {"type": "string", "description": "O que faz o profissional formado/especializado, no dia a dia"},
        "areas_atuacao": {"type": "array", "items": {"type": "string"}},
        "mercado_trabalho": {"type": "string", "description": "Cenário atual do mercado no Brasil e no Paraná, demanda, setores que contratam"},
        "tendencias": {"type": "array", "items": {"type": "string"}},
        "faixa_salarial": {"type": "string", "description": "Faixas aproximadas por nível, deixando claro que são estimativas"},
        "registro_profissional": {"type": "string"},
        "perfil_ideal": {"type": "array", "items": {"type": "string"}},
        "diferenciais_do_curso": {"type": "array", "items": {"type": "string"}, "description": "Baseados SOMENTE nos dados do curso fornecidos"},
        "argumentos_sdr": {"type": "array", "items": {"type": "string"}},
        "objecoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"objecao": {"type": "string"}, "resposta": {"type": "string"}},
                "required": ["objecao", "resposta"],
                "additionalProperties": False,
            },
        },
        "perguntas_qualificacao": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "a_profissao", "areas_atuacao", "mercado_trabalho", "tendencias", "faixa_salarial",
                 "registro_profissional", "perfil_ideal", "diferenciais_do_curso", "argumentos_sdr", "objecoes",
                 "perguntas_qualificacao"],
    "additionalProperties": False,
}

SISTEMA = """Você é especialista em orientação de carreira e mercado de trabalho no Brasil e escreve a base de conhecimento usada por um agente de IA de pré-vendas (SDR) do Unicive – Centro Universitário Cidade Verde (Maringá/PR, cursos EAD, semipresenciais e presenciais).

Para o curso informado, escreva uma análise de carreira em português do Brasil, clara e honesta:
- Fale da profissão, do mercado de trabalho (Brasil e, quando fizer sentido, Paraná/região de Maringá), tendências e faixas salariais.
- Faixas salariais são estimativas aproximadas; diga isso e nunca prometa emprego ou salário.
- Considere a modalidade (graduação, 2ª graduação, tecnólogo, pós/MBA, curso livre, profissionalizante...) — o valor para a carreira muda conforme o tipo de curso.
- Seja preciso sobre registro em conselho: se um curso livre ou pós não habilita para uma profissão regulamentada, diga claramente.
- Diferenciais do curso: use apenas os dados fornecidos (matriz, metodologia, público-alvo). Não invente.
- Argumentos e respostas a objeções devem ser éticos, sem pressão e sem gatilhos enganosos.
- Não mencione eventos."""


def conteudo_curso(c):
    partes = [f"Curso: {c['titulo']}", f"Modalidade: {c.get('modalidade') or 'não informada'}",
              f"Duração: {c.get('duracao') or ', '.join(c.get('tags', []))}", f"Centro: {', '.join(c.get('centro', []))}"]
    for titulo, pars in (c.get("descricao") or {}).items():
        partes.append(f"\n{titulo}:\n" + "\n".join(pars))
    for titulo, itens in (c.get("outras_secoes") or {}).items():
        partes.append(f"\n{titulo}:\n" + "\n".join(itens))
    if c.get("matriz_curricular"):
        partes.append("\nMatriz curricular:\n- " + "\n- ".join(c["matriz_curricular"]))
    if c.get("requisitos"):
        partes.append("\nRequisitos: " + "; ".join(c["requisitos"]))
    return "\n".join(partes)


def hash_curso(c):
    return hashlib.sha256((VERSAO_PROMPT + conteudo_curso(c)).encode()).hexdigest()[:16]


def prompt(c):
    area = area_do_curso(c["titulo"], c.get("categorias", []), c.get("centro", []))
    mod = modalidade_do_curso(c.get("modalidade"), c["titulo"], c.get("categorias", []))
    contexto = (f"Área profissional de referência: {area['nome']}\n{area['mercado']}\n"
                f"Registro: {area['registro']}\nModalidade: {mod['nome']} — {mod['valor']}")
    return f"<contexto_area>\n{contexto}\n</contexto_area>\n\n<dados_do_curso>\n{conteudo_curso(c)}\n</dados_do_curso>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY não definida — usando apenas a base curada de carreira.")
        return

    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    CARREIRA_DIR.mkdir(parents=True, exist_ok=True)
    pendentes = {}
    for arq in sorted(CURSOS_DIR.glob("*.json")):
        c = json.loads(arq.read_text(encoding="utf-8"))
        h = hash_curso(c)
        dest = CARREIRA_DIR / arq.name
        if dest.exists() and json.loads(dest.read_text(encoding="utf-8")).get("hash") == h:
            continue
        pendentes[c["id"]] = (c, h)
        if a.limite and len(pendentes) >= a.limite:
            break
    if not pendentes:
        print("Análises de carreira em dia.")
        return

    client = anthropic.Anthropic()
    reqs = [Request(custom_id=str(cid), params=MessageCreateParamsNonStreaming(
        model=MODELO, max_tokens=16000, system=SISTEMA,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt(c)}],
    )) for cid, (c, _) in pendentes.items()]
    lote = client.messages.batches.create(requests=reqs)
    print(f"Lote {lote.id} enviado com {len(reqs)} cursos")

    while (lote := client.messages.batches.retrieve(lote.id)).processing_status != "ended":
        time.sleep(60)

    ok = 0
    for r in client.messages.batches.results(lote.id):
        c, h = pendentes[int(r.custom_id)]
        if r.result.type != "succeeded":
            print(f"  ! {c['slug']}: {r.result.type}")
            continue
        msg = r.result.message
        if msg.stop_reason != "end_turn":  # refusal / max_tokens: fica a base curada
            print(f"  ! {c['slug']}: stop_reason={msg.stop_reason}")
            continue
        texto = next(b.text for b in msg.content if b.type == "text")
        dado = {"slug": c["slug"], "hash": h, "modelo": MODELO, "analise": json.loads(texto)}
        (CARREIRA_DIR / f"{c['slug']}.json").write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")
        ok += 1
    print(f"Análises de carreira geradas: {ok}/{len(pendentes)}")


if __name__ == "__main__":
    main()
