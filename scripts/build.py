"""Gera o site estático da base de conhecimento em site/.

Saídas:
  site/index.html                 catálogo com busca e filtros
  site/cursos/<slug>.html         ficha + análise de carreira + guia SDR
  site/cursos/<slug>.md           mesma informação em Markdown (RAG)
  site/carreiras/...              uma página por área profissional
  site/institucional/...          páginas institucionais
  site/agente.html                instruções para conectar o agente de IA
  site/api/cursos.json            todos os dados estruturados
  site/llms.txt, llms-full.txt    padrão llms.txt para agentes de IA
  site/sitemap.xml
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analise import analise, oferta  # noqa: E402
from carreira_base import AREAS, MODALIDADES  # noqa: E402
from sync import BASE, CURSOS_DIR, DATA, INST_DIR, ROOT  # noqa: E402

SITE = ROOT / "site"
CARREIRA_DIR = DATA / "carreira"
e = html.escape
AGORA = dt.datetime.now(dt.timezone.utc)
AGORA_BR = AGORA.astimezone(dt.timezone(dt.timedelta(hours=-3))).strftime("%d/%m/%Y às %H:%M")
SITE_URL = ""  # preenchido pelo workflow (SITE_URL) para sitemap e llms.txt
URL_PADRAO = "https://victorbarbieri1.github.io/siteunicive"  # URLs das skills Hablla em builds locais

GRUPOS_INST = [
    ("Sobre o Unicive", ["conheca-o-unicive", "reitoria", "contatos", "polos", "internacionalizacao"]),
    ("Formas de ingresso e benefícios", ["programas-apoio-estudantil", "empresas-conveniadas", "volte-a-estudar", "amigo-indica-amigo", "taxas_academicas"]),
    ("Modalidades de ensino", ["graduacao-bacharelado", "graduacao-licenciatura", "graduacao-tecnologo", "tecnico-para-tecnologo",
                               "simulador-segunda-graduacao", "2agraduacao-em-licenciatura-semipresencial-unicive", "pos-graduacao-ead",
                               "aperfeicoamento", "graduacao-presencial", "tecnico-para-tecnologo-presencial", "pos-graduacao-presencial",
                               "extensao-ead", "cursos-livres-ao-vivo", "extensao-presencial", "profissionalizantes"]),
    ("Carreira e vida acadêmica", ["central-de-carreiras", "central-estagio-obrigatorio", "biblioteca", "ic", "extensao-universitaria",
                                   "alumni", "enade-ead", "cpa"]),
    ("Estrutura, inovação e comunidade", ["hub-de-inovacao-digital", "smart-space", "espaco-maker", "nac-nap", "responsabilidade-social",
                                          "comissao-de-acessibilidade", "cep-comite-de-etica-em-pesquisa"]),
]

CSS = """
:root{--bg:#f6f8f7;--surface:#fff;--surface-2:#eef3f1;--text:#16211d;--muted:#5b6a64;--line:#dde5e1;
--brand:#127d5d;--brand-strong:#0c5e46;--brand-soft:#e3f2ec;--accent:#b4dc4b;--warn:#8a5a00;--warn-soft:#fff5e0;
--radius:14px;--shadow:0 1px 2px rgba(16,40,30,.06),0 4px 16px rgba(16,40,30,.05)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1513;--surface:#161e1b;--surface-2:#1d2723;
--text:#e6eeea;--muted:#9aaba4;--line:#2a3631;--brand:#3cc596;--brand-strong:#6fdcb5;--brand-soft:#173329;--warn:#f2c46d;--warn-soft:#2e2615;
--shadow:none}}
:root[data-theme=dark]{--bg:#0f1513;--surface:#161e1b;--surface-2:#1d2723;--text:#e6eeea;--muted:#9aaba4;--line:#2a3631;
--brand:#3cc596;--brand-strong:#6fdcb5;--brand-soft:#173329;--warn:#f2c46d;--warn-soft:#2e2615;--shadow:none}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--brand)}a:hover{color:var(--brand-strong)}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
header.top{background:var(--surface);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
header.top .wrap{display:flex;align-items:center;gap:20px;min-height:60px;flex-wrap:wrap}
.logo{font-weight:800;color:var(--text);text-decoration:none;letter-spacing:-.02em;display:flex;align-items:center;gap:8px}
.logo b{color:var(--brand)}.logo small{font-weight:500;color:var(--muted);font-size:13px}
nav.menu{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}
nav.menu a{text-decoration:none;color:var(--muted);padding:6px 10px;border-radius:8px;font-size:15px}
nav.menu a:hover,nav.menu a.on{background:var(--brand-soft);color:var(--brand-strong)}
main{padding:28px 0 56px}
h1{font-size:clamp(26px,4vw,36px);line-height:1.15;letter-spacing:-.02em;margin:0 0 10px}
h2{font-size:21px;margin:34px 0 12px;letter-spacing:-.01em}h3{font-size:17px;margin:20px 0 8px}
.lead{color:var(--muted);font-size:17px;max-width:760px;margin:0 0 18px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.grid{display:grid;gap:16px}.g2{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}.g3{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 14px}
.chip{display:inline-block;padding:3px 10px;border-radius:999px;background:var(--surface-2);color:var(--muted);font-size:13px;border:1px solid var(--line)}
.chip.brand{background:var(--brand-soft);color:var(--brand-strong);border-color:transparent;font-weight:600}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.stat b{display:block;font-size:26px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}.stat span{color:var(--muted);font-size:14px}
.filters{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:10px;margin:18px 0 8px}
@media (max-width:760px){.filters{grid-template-columns:1fr}}
input,select{width:100%;font:inherit;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--text)}
input:focus,select:focus{outline:2px solid var(--brand);outline-offset:1px}
ul.lista{list-style:none;margin:0;padding:0;display:grid;gap:8px}
ul.lista li a{display:flex;gap:10px;justify-content:space-between;align-items:center;flex-wrap:wrap;padding:12px 14px;background:var(--surface);
border:1px solid var(--line);border-radius:12px;text-decoration:none;color:var(--text)}
ul.lista li a:hover{border-color:var(--brand)}
ul.lista .t{font-weight:600}ul.lista .m{color:var(--muted);font-size:13px}
.count{color:var(--muted);font-size:14px;margin:6px 0 12px}
.ficha{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.ficha div{background:var(--surface-2);border-radius:10px;padding:10px 12px}.ficha small{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.preco{font-size:17px;font-weight:700;color:var(--brand-strong)}.de{color:var(--muted);text-decoration:line-through;font-size:14px}
ul.check{padding-left:0;list-style:none}ul.check li{padding-left:24px;position:relative;margin:4px 0}
ul.check li:before{content:"";position:absolute;left:4px;top:.6em;width:8px;height:8px;border-radius:50%;background:var(--brand)}
ol.matriz{padding-left:22px}ol.matriz li{margin:3px 0}
.note{background:var(--warn-soft);color:var(--warn);border-radius:10px;padding:10px 14px;font-size:14px}
.sdr{border-left:4px solid var(--brand)}
details{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:8px 0}
details summary{cursor:pointer;font-weight:600}
.banner{display:none;margin:12px 0}.banner.on{display:block}
.crumb{font-size:14px;color:var(--muted);margin-bottom:10px}.crumb a{color:var(--muted)}
.btn{display:inline-block;background:var(--brand);color:#fff;text-decoration:none;padding:9px 16px;border-radius:10px;font-weight:600}
.btn:hover{background:var(--brand-strong);color:#fff}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:14px;padding:22px 0 40px}
code,pre{font-family:ui-monospace,Consolas,monospace;font-size:14px}pre{background:var(--surface-2);padding:12px;border-radius:10px;overflow:auto}
.cols{columns:2 280px;column-gap:28px}
"""

JS_INDEX = """
(function(){
const q=document.getElementById('q'),fm=document.getElementById('fm'),fa=document.getElementById('fa'),fc=document.getElementById('fc');
const itens=[...document.querySelectorAll('#lista li')],cnt=document.getElementById('cnt');
const norm=s=>s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
itens.forEach(li=>li._t=norm(li.textContent));
function f(){const t=norm(q.value.trim());let n=0;
 itens.forEach(li=>{const ok=(!t||t.split(/\\s+/).every(p=>li._t.includes(p)))&&(!fm.value||li.dataset.m===fm.value)&&(!fa.value||li.dataset.a===fa.value)&&(!fc.value||li.dataset.c===fc.value);
 li.hidden=!ok;if(ok)n++});cnt.textContent=n+' curso'+(n===1?'':'s');
 try{const u=new URLSearchParams();[['q',q],['m',fm],['a',fa],['c',fc]].forEach(([k,el])=>{if(el.value)u.set(k,el.value)});history.replaceState(null,'',u.toString()?'?'+u:location.pathname)}catch(e){}}
const p=new URLSearchParams(location.search);q.value=p.get('q')||'';fm.value=p.get('m')||'';fa.value=p.get('a')||'';fc.value=p.get('c')||'';
[q,fm,fa,fc].forEach(el=>el.addEventListener('input',f));f();
// Verificação ao vivo: cursos publicados/alterados no unicive.com depois da última sincronização.
const b=document.getElementById('aovivo');const desde=b.dataset.desde;const conhecidos=new Set(itens.map(li=>li.dataset.s));
fetch('https://unicive.com/wp-json/wp/v2/courses?per_page=100&_fields=slug,link,title,modified_gmt&orderby=modified&order=desc&modified_after='+encodeURIComponent(desde))
 .then(r=>r.ok?r.json():[]).then(l=>{if(!l.length)return;const novos=l.filter(c=>!conhecidos.has(c.slug));
 b.querySelector('span').textContent=(novos.length?novos.length+' curso(s) novo(s) e ':'')+(l.length-novos.length)+' atualizado(s) no site oficial desde a última sincronização. Eles entram aqui automaticamente na próxima atualização (a cada 3 horas).';
 const ul=b.querySelector('ul');novos.slice(0,10).forEach(c=>{const li=document.createElement('li');const a=document.createElement('a');a.href=c.link;a.textContent=c.title.rendered.replace(/<[^>]+>/g,'').replace(/&#8211;/g,'–');li.appendChild(a);ul.appendChild(li)});
 b.classList.add('on')}).catch(()=>{});
})();
"""


def moeda(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if v else ""


def slugify(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pagina(titulo, corpo, prefixo="", ativo="", descricao="", extra_head=""):
    menu = [("index.html", "Cursos", "cursos"), ("carreiras/index.html", "Carreiras", "carreiras"),
            ("modalidades.html", "Modalidades", "modalidades"), ("institucional/index.html", "Institucional", "inst"),
            ("agente.html", "Para o agente de IA", "agente")]
    nav = "".join(f'<a href="{prefixo}{h}"{" class=on" if k == ativo else ""}>{t}</a>' for h, t, k in menu)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titulo)}</title><meta name="description" content="{e(descricao or titulo)}">
<link rel="stylesheet" href="{prefixo}assets/estilo.css"><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23127d5d'/%3E%3Cpath d='M9 9v8a7 7 0 0 0 14 0V9' stroke='white' stroke-width='3.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
{extra_head}</head><body>
<header class="top"><div class="wrap"><a class="logo" href="{prefixo}index.html"><b>Unicive</b> Base de Conhecimento <small>SDR</small></a><nav class="menu">{nav}</nav></div></header>
<main><div class="wrap">{corpo}</div></main>
<footer><div class="wrap">Conteúdo sincronizado automaticamente com <a href="{BASE}">unicive.com</a> · Última atualização: {AGORA_BR} (Brasília).
Valores e condições podem mudar — confirme sempre no site oficial antes de fechar matrícula. Faixas salariais são estimativas de mercado.</div></footer>
</body></html>"""


def lista_html(itens, cls="check"):
    return f'<ul class="{cls}">' + "".join(f"<li>{e(i)}</li>" for i in itens if i) + "</ul>" if itens else ""


def limpar_paginas_modalidade(blocos, titulos):
    fora = re.compile(r"(?i)^(dura[cç][aã]o m[ií]nima|fale com|saiba mais|inscreva|confira|ver curso|clique)")
    # Pedido do projeto: nada de eventos. Remove seções "…Eventos…" inteiras e parágrafos que descrevem eventos.
    secao_evento = re.compile(r"(?i)eventos?\b|palestras?|feiras?\b|agenda\b")
    texto_evento = re.compile(r"(?i)\b(o|um|este|esse|do|no) evento\b|subs[ií]dio para eventos|inscri[cç][oõ]es abertas")
    saida, pulando = [], False
    for b in blocos:
        if b["tipo"] == "titulo" and len(b["texto"]) < 90:
            pulando = bool(secao_evento.search(b["texto"]))
        if pulando or texto_evento.search(b["texto"]):
            continue
        if b["texto"] in titulos or fora.match(b["texto"]):
            continue
        saida.append(b)
    return saida


def carregar():
    cursos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CURSOS_DIR.glob("*.json"))]
    for c in cursos:
        c["analise"] = analise(c, CARREIRA_DIR)
    cursos.sort(key=lambda c: c["titulo"].lower())
    inst = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in INST_DIR.glob("*.json")}
    titulos = {c["titulo"] for c in cursos}
    for k, v in inst.items():
        v["blocos"] = limpar_paginas_modalidade(v["blocos"], titulos)
    return cursos, inst


def ficha(c):
    cel = [("Modalidade", e(c.get("modalidade") or "—")),
           ("Duração", e(c.get("duracao") or ", ".join(c.get("tags", [])) or "—"))]
    if c.get("carga_horaria_total"):
        cel.append(("Carga horária total", e(c["carga_horaria_total"].lower())))
    if c.get("centro"):
        cel.append(("Centro de ensino", e(", ".join(c["centro"]))))
    o = oferta(c)
    if o.get("por"):
        de = f'<div class="de">de {e(o["de"])}</div>' if o.get("de") else ""
        cel.append(("Investimento", f'{de}<div class="preco">{e(o["por"])}</div>'))
    return '<div class="ficha">' + "".join(f"<div><small>{k}</small>{v}</div>" for k, v in cel) + "</div>"


def pagina_curso(c, relacionados):
    a = c["analise"]
    p = "../"
    corpo = [f'<div class="crumb"><a href="{p}index.html">Cursos</a> › <a href="{p}carreiras/{a["area"]["id"]}.html">{e(a["area"]["nome"])}</a></div>',
             f"<h1>{e(c['titulo'])}</h1>",
             f'<div class="chips"><span class="chip brand">{e(a["modalidade"]["nome"])}</span><span class="chip">{e(a["area"]["nome"])}</span>'
             + "".join(f'<span class="chip">{e(t)}</span>' for t in c.get("tags", [])) + "</div>",
             f'<p class="lead">{e(c.get("seo_descricao") or a["resumo"])}</p>',
             f'<p><a class="btn" href="{e(c["url"])}" rel="noopener">Ver no site oficial</a></p>',
             f'<section class="card"><h2 style="margin-top:0">Ficha do curso</h2>{ficha(c)}</section>']

    corpo.append('<h2>Sobre o curso</h2>')
    for tit, pars in (c.get("descricao") or {}).items():
        if tit.lower() != "informações sobre o curso":
            corpo.append(f"<h3>{e(tit)}</h3>")
        corpo += [f"<p>{e(x)}</p>" for x in pars]
    for tit, itens in (c.get("outras_secoes") or {}).items():
        corpo.append(f"<h3>{e(tit)}</h3>")
        corpo.append("".join(f"<p>{e(x)}</p>" for x in itens) if len(itens) < 3 and all(len(x) > 120 for x in itens) else lista_html(itens))
    if c.get("requisitos"):
        corpo.append("<h3>Requisitos</h3>" + lista_html(c["requisitos"]))
    if c.get("documentos_necessarios"):
        corpo.append("<h3>Documentos necessários</h3>" + lista_html(c["documentos_necessarios"]))
    if c.get("matriz_curricular"):
        corpo.append("<h2>Matriz curricular</h2><ol class=\"matriz\">" + "".join(f"<li>{e(m)}</li>" for m in c["matriz_curricular"]) + "</ol>")
        if c.get("carga_horaria_total"):
            corpo.append(f"<p><b>Carga horária total:</b> {e(c['carga_horaria_total'].lower())}</p>")
    if c.get("coordenacao"):
        corpo.append("<h2>Coordenação</h2>")
        for co in c["coordenacao"]:
            lat = f' · <a href="{e(co["lattes"])}" rel="noopener">Currículo Lattes</a>' if co.get("lattes") else ""
            bio = re.split(r"(?i)curr[ií]culo lattes", co.get("curriculo", ""))[0].strip()
            corpo.append(f'<div class="card"><b>{e(co["nome"])}</b>{lat}<p style="margin-bottom:0">{e(bio)}</p></div>')

    corpo.append(f'<h2>Análise de carreira</h2><p class="lead">{e(a["resumo"])}</p>')
    corpo.append(f'<div class="grid g2"><div class="card"><h3 style="margin-top:0">A profissão</h3><p>{e(a["a_profissao"])}</p></div>'
                 f'<div class="card"><h3 style="margin-top:0">Onde atuar</h3>{lista_html(a["areas_atuacao"])}</div></div>')
    corpo.append(f'<h3>Mercado de trabalho</h3><p>{e(a["mercado_trabalho"])}</p>')
    corpo.append(f'<h3>Tendências</h3>{lista_html(a["tendencias"])}')
    corpo.append(f'<div class="grid g2"><div class="card"><h3 style="margin-top:0">Faixa salarial de referência</h3><p>{e(a["faixa_salarial"])}</p>'
                 f'<p class="note">Estimativa aproximada do mercado brasileiro; varia por região, experiência e empresa. Não é promessa de remuneração.</p></div>'
                 f'<div class="card"><h3 style="margin-top:0">Registro profissional</h3><p>{e(a["registro_profissional"])}</p>'
                 f'<h3>Perfil que combina</h3>{lista_html(a["perfil_ideal"])}</div></div>')
    corpo.append(f'<h3>Valor da modalidade para a carreira</h3><p>{e(a["modalidade"]["valor"])}</p><p><b>Para quem:</b> {e(a["modalidade"]["para_quem"])}</p>')
    if a["diferenciais_do_curso"]:
        corpo.append(f'<h3>Diferenciais deste curso</h3>{lista_html(a["diferenciais_do_curso"])}')

    corpo.append('<h2>Guia para o SDR</h2><div class="card sdr">')
    corpo.append(f'<h3 style="margin-top:0">Argumentos de valor</h3>{lista_html(a["argumentos_sdr"])}')
    corpo.append(f'<h3>Perguntas de qualificação</h3>{lista_html(a["perguntas_qualificacao"])}')
    corpo.append("<h3>Objeções frequentes</h3>" + "".join(
        f"<details><summary>{e(o['objecao'])}</summary><p>{e(o['resposta'])}</p></details>" for o in a["objecoes"]) + "</div>")

    if relacionados:
        corpo.append("<h2>Cursos relacionados na mesma área</h2><ul class=\"lista\">" + "".join(
            f'<li><a href="{r["slug"]}.html"><span class="t">{e(r["titulo"])}</span><span class="m">{e(r.get("modalidade") or "")}</span></a></li>'
            for r in relacionados) + "</ul>")
    fonte = "gerada por IA a partir dos dados do curso" if a["fonte"] == "ia" else "base curada de carreira por área e modalidade"
    corpo.append(f'<p class="count" style="margin-top:28px">Fonte: <a href="{e(c["url"])}">{e(c["url"])}</a> · Alterado no site oficial em {e(c["modificado"][:10])} · '
                 f'Sincronizado em {e(c["sincronizado_em"][:16].replace("T", " "))} UTC · Análise de carreira: {fonte}.</p>')

    ld = {"@context": "https://schema.org", "@type": "Course", "name": c["titulo"], "url": c["url"],
          "description": c.get("seo_descricao") or a["resumo"],
          "provider": {"@type": "CollegeOrUniversity", "name": "Unicive – Centro Universitário Cidade Verde", "url": BASE}}
    head = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    return pagina(f"{c['titulo']} – Unicive", "".join(corpo), p, "cursos", c.get("seo_descricao") or a["resumo"], head)


def markdown_curso(c):
    a = c["analise"]
    L = [f"# {c['titulo']}", "", f"- Instituição: Unicive – Centro Universitário Cidade Verde", f"- Página oficial: {c['url']}",
         f"- Modalidade: {c.get('modalidade') or a['modalidade']['nome']}", f"- Duração: {c.get('duracao') or ', '.join(c.get('tags', []))}",
         f"- Área profissional: {a['area']['nome']}", f"- Centro de ensino: {', '.join(c.get('centro', []))}"]
    if c.get("carga_horaria_total"):
        L.append(f"- Carga horária total: {c['carga_horaria_total'].lower()}")
    o = oferta(c)
    if o.get("por"):
        L.append(f"- Investimento (site oficial em {c['sincronizado_em'][:10]}): {o['por']}" + (f" (de {o['de']})" if o.get("de") else ""))
    if c.get("seo_descricao"):
        L += ["", c["seo_descricao"]]
    for tit, pars in (c.get("descricao") or {}).items():
        L += ["", f"## {tit}", *pars]
    for tit, itens in (c.get("outras_secoes") or {}).items():
        L += ["", f"## {tit}", *[f"- {x}" for x in itens]]
    if c.get("requisitos"):
        L += ["", "## Requisitos", *[f"- {x}" for x in c["requisitos"]]]
    if c.get("documentos_necessarios"):
        L += ["", "## Documentos necessários", *[f"- {x}" for x in c["documentos_necessarios"]]]
    if c.get("matriz_curricular"):
        L += ["", "## Matriz curricular", *[f"{i}. {m}" for i, m in enumerate(c["matriz_curricular"], 1)]]
    for co in c.get("coordenacao", []):
        L += ["", f"## Coordenação: {co['nome']}", re.split(r"(?i)curr[ií]culo lattes", co.get("curriculo", ""))[0].strip()]
    L += ["", "## Análise de carreira", a["resumo"], "", "### A profissão", a["a_profissao"], "", "### Onde atuar",
          *[f"- {x}" for x in a["areas_atuacao"]], "", "### Mercado de trabalho", a["mercado_trabalho"], "", "### Tendências",
          *[f"- {x}" for x in a["tendencias"]], "", "### Faixa salarial de referência (estimativa, não é promessa)", a["faixa_salarial"],
          "", "### Registro profissional", a["registro_profissional"], "", "### Perfil que combina", *[f"- {x}" for x in a["perfil_ideal"]],
          "", f"### Valor da modalidade ({a['modalidade']['nome']})", a["modalidade"]["valor"], f"Para quem: {a['modalidade']['para_quem']}"]
    if a["diferenciais_do_curso"]:
        L += ["", "### Diferenciais deste curso", *[f"- {x}" for x in a["diferenciais_do_curso"]]]
    L += ["", "## Guia para o SDR", "### Argumentos de valor", *[f"- {x}" for x in a["argumentos_sdr"]],
          "", "### Perguntas de qualificação", *[f"- {x}" for x in a["perguntas_qualificacao"]], "", "### Objeções frequentes"]
    for o in a["objecoes"]:
        L += [f"- **{o['objecao']}** {o['resposta']}"]
    L += ["", f"_Fonte: {c['url']} · sincronizado em {c['sincronizado_em'][:10]}_", ""]
    return "\n".join(L)


def markdown_inst(p):
    L = [f"# {p['titulo']}", f"Fonte: {p['url']}", ""]
    for b in p["blocos"]:
        L.append(f"## {b['texto']}" if b["tipo"] == "titulo" and len(b["texto"]) < 90 else b["texto"])
    return "\n".join(L) + "\n"


def md_para_html(md):
    """Markdown simples (o que markdown_curso/markdown_inst geram) para HTML sem links."""
    out, lista = [], None
    negrito = lambda t: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e(t))
    for linha in md.split("\n"):
        m = re.match(r"^(#{1,4}) (.*)", linha)
        item = re.match(r"^(- |\d+\. )(.*)", linha)
        tipo = "ol" if item and item.group(1)[0].isdigit() else "ul" if item else None
        if lista and tipo != lista:
            out.append(f"</{lista}>")
            lista = None
        if m:
            n = min(len(m.group(1)) + 1, 4)  # o <h1> fica para o título do pacote
            out.append(f"<h{n}>{negrito(m.group(2))}</h{n}>")
        elif item:
            if not lista:
                lista = tipo
                out.append(f"<{tipo}>")
            out.append(f"<li>{negrito(item.group(2))}</li>")
        elif linha.strip():
            out.append(f"<p>{negrito(linha.strip().strip('_'))}</p>")
    if lista:
        out.append(f"</{lista}>")
    return "\n".join(out)


def gerar_pacotes_rastreador(blocos_inst, cursos, max_paginas=95):
    """Base inteira em poucas páginas HTML grandes, para rastreadores com limite de páginas (ex.: Hablla).

    site/hablla/index.html só aponta para os pacotes, e os pacotes não têm nenhum link,
    então um rastreador que parte do índice lê exatamente: índice + pacotes.
    """
    pasta = SITE / "hablla"
    pasta.mkdir(exist_ok=True)
    grupos = [("institucional", "Institucional, contatos, ingresso e modalidades", [b for b in blocos_inst if b.strip()])]
    for m in MODALIDADES:
        lista = sorted((c for c in cursos if c["analise"]["modalidade"]["id"] == m["id"]),
                       key=lambda c: (c["analise"]["area"]["nome"], c["titulo"].lower()))
        if lista:
            grupos.append((m["id"], f"Cursos – {m['nome']}", [markdown_curso(c) for c in lista]))

    limite = 200_000
    while True:
        pacotes = []
        for gid, nome, docs in grupos:
            atual, tam, parte = [], 0, 1
            for d in docs:
                t = len(d.encode())
                if atual and tam + t > limite:
                    pacotes.append((f"{gid}-{parte:02d}", f"{nome} (parte {parte})", atual))
                    atual, tam, parte = [], 0, parte + 1
                atual.append(d)
                tam += t
            if atual:
                pacotes.append((f"{gid}-{parte:02d}", f"{nome} (parte {parte})" if parte > 1 else nome, atual))
        if len(pacotes) <= max_paginas:
            break
        limite = int(limite * 1.25)

    css = "body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px;color:#16211d;background:#fff}h2{margin-top:2em;border-top:1px solid #ddd;padding-top:1em}"
    aviso = ("Base de conhecimento do Unicive – Centro Universitário Cidade Verde, sincronizada automaticamente com unicive.com "
             f"em {AGORA_BR}. Preços e condições conforme o site oficial nessa data. Faixas salariais são estimativas.")
    for arq, titulo, docs in pacotes:
        corpo = f"<h1>{e(titulo)} – Unicive</h1><p>{e(aviso)}</p>" + "\n".join(md_para_html(d) for d in docs)
        (pasta / f"{arq}.html").write_text(
            f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="nofollow"><title>{e(titulo)} – Unicive</title><style>{css}</style></head><body>{corpo}</body></html>',
            encoding="utf-8")
    itens = "".join(f'<li><a href="{arq}.html">{e(titulo)}</a></li>' for arq, titulo, _ in pacotes)
    (pasta / "index.html").write_text(
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Base de conhecimento Unicive – índice</title><style>{css}</style></head><body>'
        f"<h1>Base de conhecimento Unicive</h1><p>{e(aviso)}</p><p>{len(cursos)} cursos em {len(pacotes)} páginas.</p><ul>{itens}</ul></body></html>",
        encoding="utf-8")
    return len(pacotes)


LIMITE_URLS_SKILL = 100  # limite de URLs por skill de agente na Hablla
SKILLS_HABLLA = [  # (id da modalidade, nome da skill), na ordem em que aparecem
    ("bacharelado", "Graduação – Bacharelado"), ("licenciatura", "Graduação – Licenciatura"),
    ("tecnologo", "Graduação – Tecnólogo"), ("segunda-graduacao", "Graduação – 2ª Graduação"),
    ("tecnico-tecnologo", "Graduação – Técnico para Tecnólogo"), ("pos", "Pós-Graduação e MBA"),
    ("mestrado", "Mestrado"), ("aperfeicoamento", "Aperfeiçoamento e Extensão"), ("livre", "Cursos Livres"),
    ("profissionalizante", "Cursos Profissionalizantes"), ("preparatorio", "Cursos Preparatórios"),
]


def empacotar(grupos, limite):
    """Junta grupos [(nome, cursos)] em pacotes de até `limite` cursos sem quebrar nenhum grupo (first-fit decrescente)."""
    pacotes = []
    for nome, lista in sorted(grupos, key=lambda g: -len(g[1])):
        alvo = next((p for p in pacotes if len(p[1]) + len(lista) <= limite), None)
        if alvo is None:
            pacotes.append(([], []))
            alvo = pacotes[-1]
        alvo[0].append(nome)
        alvo[1].extend(lista)
    return pacotes


def dividir_skill(lista, limite=LIMITE_URLS_SKILL):
    """Divide os cursos de uma modalidade em skills de até `limite` URLs.

    Até o limite: uma skill só. Acima: por centro (categoria do unicive.com); um centro grande demais
    é dividido por área profissional.
    """
    if len(lista) <= limite:
        return [([], lista)]
    por_centro = defaultdict(list)
    for c in lista:
        por_centro[(c.get("centro") or [""])[0]].append(c)
    grupos = []
    for centro, cs in por_centro.items():
        if len(cs) <= limite:
            grupos.append((centro or "Outros (sem centro)", cs))
            continue
        por_area = defaultdict(list)
        for c in cs:
            por_area[c["analise"]["area"]["nome"]].append(c)
        grupos += [(a, x) for a, x in por_area.items()]
    pacotes = empacotar(grupos, limite)
    for nomes, cs in pacotes:
        nomes.sort()
        cs.sort(key=lambda c: c["titulo"].lower())
    return sorted(pacotes, key=lambda p: (-len(p[1]), p[0]))


def gerar_skills_hablla(cursos, url):
    """Skills da Hablla: cursos agrupados por modalidade, no máximo LIMITE_URLS_SKILL URLs por skill.

    Gera site/hablla-skills/index.html (lista para copiar), um .txt com as URLs de cada skill e skills.json.
    """
    pasta = SITE / "hablla-skills"
    pasta.mkdir(exist_ok=True)
    nomes = dict(SKILLS_HABLLA)
    ordem = [mid for mid, _ in SKILLS_HABLLA] + [m["id"] for m in MODALIDADES if m["id"] not in nomes]
    skills = []
    for mid in ordem:
        lista = [c for c in cursos if c["analise"]["modalidade"]["id"] == mid]
        if not lista:
            continue
        nome = nomes.get(mid) or next(m["nome"] for m in MODALIDADES if m["id"] == mid)
        partes = dividir_skill(lista)
        for i, (cats, cs) in enumerate(partes, 1):
            sid = f"{mid}-{i:02d}" if len(partes) > 1 else mid
            titulo = f"{nome} {i}/{len(partes)}" if len(partes) > 1 else nome
            urls = [f"{url}/cursos/{c['slug']}.html" for c in cs]
            skills.append({"id": sid, "nome": titulo, "modalidade": mid, "categorias": cats, "total_urls": len(urls),
                           "cursos": [{"titulo": c["titulo"], "url": u} for c, u in zip(cs, urls)]})
            (pasta / f"{sid}.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    assert all(s["total_urls"] <= LIMITE_URLS_SKILL for s in skills)
    (pasta / "skills.json").write_text(json.dumps({"gerado_em": AGORA.isoformat(timespec="seconds"), "limite_urls": LIMITE_URLS_SKILL,
                                                   "skills": skills}, ensure_ascii=False, indent=1), encoding="utf-8")

    linhas = "".join(f'<tr><td><a href="#{s["id"]}">{e(s["nome"])}</a></td><td>{s["total_urls"]}</td></tr>' for s in skills)
    blocos = "".join(
        f'<div class="card" id="{s["id"]}" style="margin:16px 0"><h2 style="margin-top:0">{e(s["nome"])} <span class="chip">{s["total_urls"]} URLs</span></h2>'
        + (f'<p class="count">Categorias: {e(" · ".join(s["categorias"]))}</p>' if s["categorias"] else "")
        + f'<p><a href="{s["id"]}.txt">{s["id"]}.txt</a> · <button type="button" data-copiar="u-{s["id"]}">Copiar URLs</button></p>'
        f'<textarea id="u-{s["id"]}" readonly rows="6" style="width:100%;font:13px/1.4 ui-monospace,monospace">'
        + e("\n".join(c["url"] for c in s["cursos"])) + "</textarea></div>" for s in skills)
    js = ("document.querySelectorAll('[data-copiar]').forEach(b=>b.onclick=()=>{const t=document.getElementById(b.dataset.copiar);"
          "t.select();(navigator.clipboard?navigator.clipboard.writeText(t.value):Promise.reject()).catch(()=>document.execCommand('copy'));"
          "b.textContent='Copiado';setTimeout(()=>b.textContent='Copiar URLs',1500)})")
    corpo = (f'<h1>Skills do agente na Hablla</h1><p class="lead">Os {len(cursos)} cursos separados por modalidade em {len(skills)} skills, '
             f'cada uma com no máximo {LIMITE_URLS_SKILL} URLs. Modalidades acima do limite são divididas por centro (categoria do unicive.com) '
             'e, quando preciso, por área profissional.</p>'
             '<p>Em cada skill da Hablla, cole as URLs do bloco correspondente. A lista muda quando o unicive.com cria ou remove cursos: '
             f'confira esta página depois das atualizações. Dados em <a href="skills.json">skills.json</a>.</p>'
             f'<table><thead><tr><th>Skill</th><th>URLs</th></tr></thead><tbody>{linhas}</tbody></table>{blocos}<script>{js}</script>')
    (pasta / "index.html").write_text(pagina("Skills Hablla – Unicive", corpo, "../", "agente"), encoding="utf-8")
    return skills


def build():
    cursos, inst = carregar()
    if SITE.exists():
        shutil.rmtree(SITE)
    for d in ["assets", "cursos", "carreiras", "institucional", "api"]:
        (SITE / d).mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "estilo.css").write_text(CSS, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    por_area = defaultdict(list)
    for c in cursos:
        por_area[c["analise"]["area"]["id"]].append(c)
    nome_area = {a["id"]: a["nome"] for a in AREAS}
    ordem_mod = [m["id"] for m in MODALIDADES]

    # Páginas de curso
    for c in cursos:
        irmaos = [r for r in por_area[c["analise"]["area"]["id"]] if r["slug"] != c["slug"]]
        irmaos.sort(key=lambda r: (r["analise"]["modalidade"]["id"] == c["analise"]["modalidade"]["id"], r["titulo"]))
        (SITE / "cursos" / f"{c['slug']}.html").write_text(pagina_curso(c, irmaos[:8]), encoding="utf-8")
        (SITE / "cursos" / f"{c['slug']}.md").write_text(markdown_curso(c), encoding="utf-8")

    # Catálogo
    mods = sorted({c["analise"]["modalidade"]["nome"] for c in cursos})
    centros = sorted({x for c in cursos for x in c.get("centro", [])})
    opt = lambda vals, label: f'<option value="">{label}</option>' + "".join(f'<option value="{e(v)}">{e(rotulo)}</option>' for v, rotulo in vals)
    itens = "".join(
        f'<li data-s="{e(c["slug"])}" data-m="{e(c["analise"]["modalidade"]["nome"])}" data-a="{e(c["analise"]["area"]["id"])}" data-c="{e((c.get("centro") or [""])[0])}">'
        f'<a href="cursos/{c["slug"]}.html"><span class="t">{e(c["titulo"])}</span>'
        f'<span class="m">{e(c.get("modalidade") or "")} · {e(c["analise"]["area"]["nome"])}'
        + (f' · {e(oferta(c)["por"])}' if oferta(c).get("por") else "")
        + "</span></a></li>" for c in cursos)
    n_mod = defaultdict(int)
    for c in cursos:
        n_mod[c["analise"]["modalidade"]["id"]] += 1
    stats = [(len(cursos), "cursos ativos"), (len(por_area), "áreas profissionais analisadas"),
             (n_mod["pos"], "pós-graduações e MBAs"), (sum(n_mod[k] for k in ("bacharelado", "licenciatura", "tecnologo", "segunda-graduacao", "tecnico-tecnologo")), "graduações")]
    corpo = (f'<h1>Base de conhecimento Unicive</h1><p class="lead">Todos os cursos do <a href="{BASE}">unicive.com</a> com ficha completa, '
             f'análise de carreira, mercado de trabalho e guia de abordagem para o agente SDR. Atualizado automaticamente.</p>'
             '<div class="stats">' + "".join(f"<div class=stat><b>{n}</b><span>{t}</span></div>" for n, t in stats) + "</div>"
             f'<div id="aovivo" class="banner note" data-desde="{AGORA.astimezone(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S")}"><span></span><ul></ul></div>'
             '<div class="filters"><input id="q" type="search" placeholder="Buscar curso, área ou palavra-chave…" aria-label="Buscar">'
             f'<select id="fm" aria-label="Modalidade">{opt([(m, m) for m in mods], "Todas as modalidades")}</select>'
             f'<select id="fa" aria-label="Área">{opt(sorted(((k, nome_area[k]) for k in por_area), key=lambda x: x[1]), "Todas as áreas")}</select>'
             f'<select id="fc" aria-label="Centro">{opt([(x, x) for x in centros], "Todos os centros")}</select></div>'
             f'<div class="count" id="cnt">{len(cursos)} cursos</div><ul class="lista" id="lista">{itens}</ul><script>{JS_INDEX}</script>')
    (SITE / "index.html").write_text(pagina("Base de Conhecimento Unicive", corpo, "", "cursos",
                                            "Cursos, carreiras e informações institucionais do Unicive para agentes de pré-vendas."), encoding="utf-8")

    # Carreiras
    cards = ""
    for a in sorted(AREAS, key=lambda a: a["nome"]):
        lista = por_area.get(a["id"], [])
        if not lista:
            continue
        cards += f'<a class="card" style="text-decoration:none;color:inherit" href="{a["id"]}.html"><b>{e(a["nome"])}</b><div class="count">{len(lista)} cursos</div></a>'
        grupos = defaultdict(list)
        for c in lista:
            grupos[c["analise"]["modalidade"]["id"]].append(c)
        cursos_html = "".join(
            f'<h3>{e(next(m["nome"] for m in MODALIDADES if m["id"] == mid))}</h3><ul class="lista">'
            + "".join(f'<li><a href="../cursos/{c["slug"]}.html"><span class="t">{e(c["titulo"])}</span><span class="m">{e(c.get("duracao") or "")}</span></a></li>' for c in grupos[mid])
            + "</ul>" for mid in ordem_mod if mid in grupos)
        corpo = (f'<div class="crumb"><a href="index.html">Carreiras</a></div><h1>{e(a["nome"])}</h1><p class="lead">{e(a["profissao"])}</p>'
                 f'<div class="grid g2"><div class="card"><h3 style="margin-top:0">Onde atuar</h3>{lista_html(a["atuacao"])}</div>'
                 f'<div class="card"><h3 style="margin-top:0">Tendências</h3>{lista_html(a["tendencias"])}</div></div>'
                 f'<h2>Mercado de trabalho</h2><p>{e(a["mercado"])}</p>'
                 f'<div class="grid g2"><div class="card"><h3 style="margin-top:0">Faixa salarial de referência</h3><p>{e(a["salario"])}</p><p class="note">Estimativa; não é promessa de remuneração.</p></div>'
                 f'<div class="card"><h3 style="margin-top:0">Registro profissional</h3><p>{e(a["registro"])}</p><h3>Perfil</h3>{lista_html(a["perfil"])}</div></div>'
                 f'<h2>Argumentos para o SDR</h2>{lista_html(a["gancho_sdr"])}<h2>Cursos desta área ({len(lista)})</h2>{cursos_html}')
        (SITE / "carreiras" / f"{a['id']}.html").write_text(pagina(f"Carreira em {a['nome']} – Unicive", corpo, "../", "carreiras", a["profissao"]), encoding="utf-8")
    corpo = ('<h1>Carreiras e mercado de trabalho</h1><p class="lead">Análise de cada área profissional atendida pelos cursos do Unicive: '
             f'o que faz o profissional, onde atua, mercado, tendências, salários de referência e registro.</p><div class="grid g3">{cards}</div>')
    (SITE / "carreiras" / "index.html").write_text(pagina("Carreiras – Unicive", corpo, "../", "carreiras"), encoding="utf-8")

    # Modalidades
    corpo = '<h1>Modalidades de curso</h1><p class="lead">Como cada tipo de curso impacta a carreira — use para adaptar a conversa ao momento do lead.</p>'
    for m in MODALIDADES:
        if not n_mod.get(m["id"]):
            continue
        corpo += (f'<div class="card" style="margin:12px 0"><h2 style="margin-top:0">{e(m["nome"])} <span class="chip">{n_mod[m["id"]]} cursos</span></h2>'
                  f'<p>{e(m["valor"])}</p><p><b>Para quem:</b> {e(m["para_quem"])}</p>{lista_html(m["argumentos"])}'
                  f'<a href="index.html?m={e(m["nome"])}">Ver cursos de {e(m["nome"].lower())} →</a></div>')
    (SITE / "modalidades.html").write_text(pagina("Modalidades – Unicive", corpo, "", "modalidades"), encoding="utf-8")

    # Institucional
    links = ""
    usados = set()
    for grupo, slugs in GRUPOS_INST:
        ok = [s for s in slugs if s in inst]
        usados.update(ok)
        if ok:
            links += f"<h2>{e(grupo)}</h2><ul class=\"lista\">" + "".join(
                f'<li><a href="{s}.html"><span class="t">{e(inst[s]["titulo"])}</span></a></li>' for s in ok) + "</ul>"
    for s, p in inst.items():
        corpo = [f'<div class="crumb"><a href="index.html">Institucional</a></div><h1>{e(p["titulo"])}</h1>']
        for b in p["blocos"]:
            t = b["texto"]
            url = re.search(r"https?://\S+", t)
            if url:
                corpo.append(f'<p>{e(t[:url.start()])}<a href="{e(url.group(0))}" rel="noopener">{e(url.group(0)[:70])}</a></p>')
            elif b["tipo"] == "titulo" and len(t) < 90:
                corpo.append(f"<h3>{e(t)}</h3>")
            else:
                corpo.append(f"<p>{e(t)}</p>")
        corpo.append(f'<p class="count">Fonte: <a href="{e(p["url"])}">{e(p["url"])}</a> · Sincronizado em {e(p["sincronizado_em"][:10])}</p>')
        (SITE / "institucional" / f"{s}.html").write_text(pagina(f"{p['titulo']} – Unicive", "".join(corpo), "../", "inst"), encoding="utf-8")
        (SITE / "institucional" / f"{s}.md").write_text(markdown_inst(p), encoding="utf-8")
    corpo = f'<h1>Informações institucionais</h1><p class="lead">Quem é o Unicive, estrutura, formas de ingresso, benefícios e modalidades.</p>{links}'
    (SITE / "institucional" / "index.html").write_text(pagina("Institucional – Unicive", corpo, "../", "inst"), encoding="utf-8")

    # API e arquivos para agentes
    dados = [{k: v for k, v in c.items()} for c in cursos]
    (SITE / "api" / "cursos.json").write_text(json.dumps({"gerado_em": AGORA.isoformat(timespec="seconds"), "total": len(dados), "cursos": dados}, ensure_ascii=False), encoding="utf-8")
    (SITE / "api" / "institucional.json").write_text(json.dumps(list(inst.values()), ensure_ascii=False), encoding="utf-8")
    (SITE / "api" / "carreiras.json").write_text(json.dumps({"areas": AREAS, "modalidades": MODALIDADES}, ensure_ascii=False), encoding="utf-8")
    (SITE / "api" / "status.json").write_text(json.dumps({"atualizado_em": AGORA.isoformat(timespec="seconds"), "cursos": len(cursos),
                                                          "institucional": len(inst), "analises_ia": sum(c["analise"]["fonte"] == "ia" for c in cursos)}), encoding="utf-8")

    url = SITE_URL.rstrip("/")
    llms = [f"# Unicive – Base de Conhecimento para SDR", "",
            "> Cursos, análises de carreira e informações institucionais do Unicive – Centro Universitário Cidade Verde (Maringá/PR), "
            f"sincronizados automaticamente com {BASE}. Atualizado em {AGORA_BR} (Brasília).", "",
            "## Como usar", "- llms-full.txt: todo o conteúdo em um arquivo (ideal para carregar na base do agente)",
            "- api/cursos.json: dados estruturados de todos os cursos, incluindo análise de carreira",
            "- cursos/<slug>.md: um arquivo Markdown por curso", "", "## Institucional"]
    llms += [f"- [{p['titulo']}]({url}/institucional/{s}.md)" for s, p in sorted(inst.items(), key=lambda x: x[1]["titulo"])]
    llms += ["", "## Cursos"] + [f"- [{c['titulo']} ({c.get('modalidade') or ''})]({url}/cursos/{c['slug']}.md)" for c in cursos]
    (SITE / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")
    full = [f"# Unicive – Base de Conhecimento completa (atualizada em {AGORA_BR})", "",
            "Regras para o agente: não há informações sobre eventos nesta base. Preços e condições vêm do site oficial na data indicada; "
            "confirme antes de fechar matrícula. Faixas salariais são estimativas e não devem ser prometidas.", "", "# PARTE 1 — INSTITUCIONAL", ""]
    for _, slugs in GRUPOS_INST:
        full += [markdown_inst(inst[s]) for s in slugs if s in inst]
    full += [markdown_inst(p) for s, p in inst.items() if s not in usados]
    full += ["", "# PARTE 2 — MODALIDADES", ""]
    full += [f"## {m['nome']}\n{m['valor']}\nPara quem: {m['para_quem']}\n" for m in MODALIDADES]
    full += ["", "# PARTE 3 — CURSOS", ""] + [markdown_curso(c) for c in cursos]
    (SITE / "llms-full.txt").write_text("\n".join(full), encoding="utf-8")

    # Mesma base fatiada em arquivos menores (limites de upload das plataformas de agente)
    (SITE / "kb").mkdir(exist_ok=True)
    partes = {"00-institucional.md": "\n".join(full[:full.index("# PARTE 3 — CURSOS")])}
    for m in MODALIDADES:
        doc = [markdown_curso(c) for c in cursos if c["analise"]["modalidade"]["id"] == m["id"]]
        if doc:
            partes[f"cursos-{m['id']}.md"] = f"# Cursos de {m['nome']} – Unicive\n\n{m['valor']}\n\n" + "\n".join(doc)
    for nome, conteudo in partes.items():
        (SITE / "kb" / nome).write_text(conteudo, encoding="utf-8")
    kb_links = "".join(f'<li><a href="kb/{n}">{n}</a> ({len(t.encode()) // 1024} KB)</li>' for n, t in partes.items())
    n_pacotes = gerar_pacotes_rastreador(full[:full.index("# PARTE 3 — CURSOS")], cursos)
    skills = gerar_skills_hablla(cursos, url or URL_PADRAO)

    # Página para o agente
    corpo = f"""<h1>Conectar o agente de IA</h1><p class="lead">Esta base é atualizada automaticamente a partir do unicive.com.
Aponte o agente SDR para uma das fontes abaixo — todas são regeneradas a cada atualização.</p>
<div class="grid g2">
<div class="card"><h3 style="margin-top:0">Arquivo único (recomendado)</h3><p><a href="llms-full.txt">llms-full.txt</a> — todo o conteúdo institucional, modalidades e os {len(cursos)} cursos em Markdown.</p></div>
<div class="card"><h3 style="margin-top:0">Índice para agentes</h3><p><a href="llms.txt">llms.txt</a> — índice no padrão llms.txt com link para o Markdown de cada curso.</p></div>
<div class="card"><h3 style="margin-top:0">API JSON</h3><p><a href="api/cursos.json">api/cursos.json</a>, <a href="api/institucional.json">api/institucional.json</a>,
<a href="api/carreiras.json">api/carreiras.json</a> e <a href="api/status.json">api/status.json</a>.</p></div>
<div class="card"><h3 style="margin-top:0">Páginas HTML</h3><p>Uma página por curso em <code>cursos/&lt;slug&gt;.html</code>, com dados estruturados schema.org/Course.</p></div>
</div>
<h2>Plataformas que leem o site com limite de páginas (ex.: Hablla)</h2>
<p>Cadastre <a href="hablla/index.html">hablla/index.html</a> como página do site, com a busca no site todo ligada e máximo de 100 páginas.
São {n_pacotes} páginas pacote, sem links para o resto do site, com a base inteira.</p>
<p>Para skills por modalidade (até {LIMITE_URLS_SKILL} URLs cada), use <a href="hablla-skills/index.html">as {len(skills)} skills prontas</a>.</p>
<h2>Arquivos fatiados por modalidade</h2><p>Para plataformas que limitam o tamanho de cada arquivo da base:</p><ul class="check">{kb_links}</ul>
<h2>Sugestão de instruções para o agente</h2>
<pre>Você é SDR do Unicive. Use apenas a base de conhecimento fornecida.
- Para cada curso, apresente a análise de carreira: profissão, mercado de trabalho, tendências e faixa salarial (sempre como estimativa).
- Use as perguntas de qualificação antes de recomendar um curso.
- Para objeções, use as respostas sugeridas com tom consultivo, sem pressão.
- Informe valores e parcelamento conforme a base e oriente a confirmar no site oficial.
- Não fale de eventos. Para assuntos fora da base, encaminhe ao atendimento humano.</pre>
<h2>Como a atualização funciona</h2><ul class="check">
<li>A cada 3 horas um robô consulta a API do unicive.com e baixa apenas cursos novos ou alterados; uma vez por dia faz a verificação completa (preços e coordenação).</li>
<li>Cursos removidos do site oficial saem da base; cursos novos ganham ficha e análise de carreira automaticamente.</li>
<li>O catálogo também consulta o unicive.com ao vivo e avisa se algo mudou desde a última sincronização.</li>
<li>Última atualização: {AGORA_BR}. {sum(c["analise"]["fonte"] == "ia" for c in cursos)} análises geradas por IA e {sum(c["analise"]["fonte"] == "base" for c in cursos)} pela base curada.</li></ul>"""
    (SITE / "agente.html").write_text(pagina("Para o agente de IA – Unicive", corpo, "", "agente"), encoding="utf-8")

    if url:
        paginas = ["index.html", "modalidades.html", "agente.html", "carreiras/index.html", "institucional/index.html"]
        paginas += [f"cursos/{c['slug']}.html" for c in cursos] + [f"carreiras/{k}.html" for k in por_area] + [f"institucional/{s}.html" for s in inst]
        sm = "".join(f"<url><loc>{url}/{p}</loc><lastmod>{AGORA.date()}</lastmod></url>" for p in paginas)
        (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
        (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {url}/sitemap.xml\n", encoding="utf-8")
    print(f"Site gerado: {len(cursos)} cursos, {len(por_area)} áreas, {len(inst)} páginas institucionais")


if __name__ == "__main__":
    import os
    SITE_URL = os.environ.get("SITE_URL", "")
    build()
