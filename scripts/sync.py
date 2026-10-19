"""Sincroniza cursos e páginas institucionais de https://unicive.com.

Fonte da lista de cursos: API REST do WordPress (/wp-json/wp/v2/courses).
Detalhes de cada curso (modalidade, matriz, investimento, coordenação...):
página pública do curso, raspada com BeautifulSoup.

Modo incremental (padrão): só baixa de novo os cursos cujo `modified` mudou.
`--full` baixa todos (preço e coordenação podem mudar sem alterar `modified`).
Eventos e notícias não são coletados.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://unicive.com"
API = f"{BASE}/wp-json/wp/v2"
ROOT = Path(__file__).absolute().parent.parent
if os.name == "nt" and not str(ROOT).startswith(LONGO := r"\\?" + "\\"):
    ROOT = Path(LONGO + str(ROOT))  # caminhos longos no Windows (>260 caracteres)
DATA = ROOT / "data"
CURSOS_DIR = DATA / "cursos"
INST_DIR = DATA / "institucional"
UA = "UniciveKB-Sync/1.0 (+base de conhecimento SDR)"

S = requests.Session()
S.headers["User-Agent"] = UA

# Páginas institucionais (sem eventos, calendário, notícias ou rádio).
INSTITUCIONAL = {
    "conheca-o-unicive": "Conheça o Unicive",
    "reitoria": "Reitoria",
    "polos": "Nossos Polos",
    "programas-apoio-estudantil": "Bolsas e Benefícios",
    "empresas-conveniadas": "Empresas Conveniadas",
    "internacionalizacao": "Internacionalização",
    "central-de-carreiras": "Central de Carreiras",
    "central-estagio-obrigatorio": "Central de Estágio Obrigatório",
    "biblioteca": "Biblioteca",
    "ic": "Iniciação Científica",
    "extensao-universitaria": "Extensão Universitária",
    "responsabilidade-social": "Responsabilidade Social",
    "cpa": "CPA – Comissão Própria de Avaliação",
    "cep-comite-de-etica-em-pesquisa": "CEP – Comitê de Ética em Pesquisa",
    "comissao-de-acessibilidade": "CAES – Comitê de Acessibilidade",
    "nac-nap": "NAC – Núcleo de Atendimento à Comunidade",
    "hub-de-inovacao-digital": "HUB de Inovação Digital",
    "smart-space": "Smart Space",
    "espaco-maker": "Espaço Maker",
    "alumni": "Alumni Egressos",
    "volte-a-estudar": "Volte a Estudar",
    "amigo-indica-amigo": "Amigo Indica Amigo",
    "taxas_academicas": "Taxas Acadêmicas",
    "enade-ead": "Enade",
    # Páginas de modalidade: explicam formatos, ingresso e diferenciais.
    "graduacao-bacharelado": "Graduação Bacharelado EAD/Semipresencial",
    "graduacao-licenciatura": "Graduação Licenciatura Semipresencial",
    "graduacao-tecnologo": "Graduação Tecnólogo EAD",
    "tecnico-para-tecnologo": "Técnico para Tecnólogo",
    "simulador-segunda-graduacao": "2ª Graduação",
    "2agraduacao-em-licenciatura-semipresencial-unicive": "2ª Graduação em Licenciatura",
    "pos-graduacao-ead": "Pós-Graduação EAD",
    "aperfeicoamento": "Aperfeiçoamento",
    "graduacao-presencial": "Graduação Presencial",
    "tecnico-para-tecnologo-presencial": "Técnico para Tecnólogo Presencial",
    "pos-graduacao-presencial": "Pós-Graduação Presencial",
    "extensao-ead": "Cursos Livres EaD",
    "cursos-livres-ao-vivo": "Cursos Livres Ao Vivo EaD",
    "extensao-presencial": "Cursos Livres Presencial",
    "profissionalizantes": "Profissionalizantes",
}

# Categorias que representam eventos/visitas, não cursos (pedido: não trazer eventos).
CATEGORIAS_EXCLUIDAS = {"visita-tecnica", "eventos"}


def get(url, **kw):
    for tentativa in range(4):
        try:
            r = S.get(url, timeout=40, **kw)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r
            if r.status_code in (404, 410):
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (tentativa + 1))
    return None


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def limpa(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def taxonomia(nome):
    termos, page = {}, 1
    while True:
        r = get(f"{API}/{nome}", params={"per_page": 100, "page": page, "_fields": "id,name,slug"})
        if not r or not r.json():
            break
        for t in r.json():
            termos[t["id"]] = {"nome": limpa(t["name"]), "slug": t["slug"]}
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return termos


def lista_cursos():
    cursos, page = [], 1
    campos = "id,slug,link,title,modified,date,course-category,course-tag,centro-de-ensino,featured_media,yoast_head_json"
    while True:
        r = get(f"{API}/courses", params={"per_page": 100, "page": page, "_fields": campos})
        if not r:
            break
        cursos += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return cursos


def lista_itens(bloco):
    return [txt(li) for li in bloco.select("li") if txt(li)] if bloco else []


def preco(s):
    m = re.search(r"([\d.]+,\d{2}|\d+\.\d{2})", s or "")
    if not m:
        return None
    v = m.group(1)
    v = v.replace(".", "").replace(",", ".") if "," in v else v
    try:
        return float(v)
    except ValueError:
        return None


def parse_curso(html_txt):
    soup = BeautifulSoup(html_txt, "html.parser")
    wrap = soup.select_one(".tutor-wrap") or soup
    out = {}

    # Descrição principal: blocos em negrito MAIÚSCULO viram seções.
    resumo = wrap.select_one(".tutor-course-summery") or wrap.select_one(".tutor-course-content-content")
    secoes, atual = {}, "Informações sobre o curso"
    if resumo:
        for el in resumo.find_all(["p", "li", "h2", "h3", "h4", "h5"]):
            t = txt(el)
            if not t:
                continue
            forte = el.find("strong")
            if forte and txt(forte) == t and t.upper() == t and len(t) < 80:
                atual = t.capitalize()
                continue
            secoes.setdefault(atual, []).append(t)
    out["descricao"] = secoes

    # Acordeões: Público-alvo, Metodologia, Matriz curricular, etc.
    acordeoes = {}
    for item in wrap.select(".tutor-accordion-item"):
        titulo = txt(item.select_one(".tutor-accordion-item-header"))
        itens = [txt(p) for p in item.select(".tutor-course-content-list-item-title") if txt(p)]
        if titulo and itens:
            acordeoes[re.sub(r"\b(ead|tcc|ead/semi)\b", lambda m: m.group(1).upper(), titulo.strip().capitalize())] = itens
    matriz_key = next((k for k in acordeoes if "matriz" in k.lower() or "grade" in k.lower()), None)
    matriz = acordeoes.pop(matriz_key, []) if matriz_key else []
    out["matriz_curricular"] = [re.sub(r"^[–\-•\s]+", "", m) for m in matriz if not re.match(r"(?i)total da carga", m)]
    total = next((m for m in matriz if re.match(r"(?i)total da carga", m)), "")
    out["carga_horaria_total"] = re.sub(r"(?i)total da carga hor[aá]ria:?", "", total).strip() or None
    out["outras_secoes"] = acordeoes

    # Coordenação
    coord = []
    for w in wrap.select(".single-instructor-wrap"):
        nome = txt(w.select_one(".instructor-name, .tutor-instructor-name, h3, h4")) or (w.find("img") or {}).get("alt", "")
        bio = ""
        for el in w.find_all(["p", "div"]):
            t = txt(el)
            if len(t) > len(bio) and "Lattes" not in t[:20]:
                bio = t
        lattes = next((a["href"] for a in w.select("a[href]") if "lattes" in a["href"].lower()), None)
        nome = limpa(nome)
        if nome:
            coord.append({"nome": nome, "curriculo": bio.replace("CURRÍCULO", "").strip(), "lattes": lattes})
    out["coordenacao"] = coord

    # Investimento
    card = wrap.select_one(".course-loop-price")
    if card:
        de = card.select_one(".price[style*=line-through]")
        por = card.select_one(".por .price")
        parcelas = [txt(p) for p in card.select(".price") if "x de" in txt(p)]
        out["investimento"] = {
            "de": preco(txt(de)),
            "por": preco(txt(por)),
            "parcelamento": parcelas[0] if parcelas else None,
            "texto": txt(card).replace("INVESTIMENTO", "").strip(),
        }
    else:
        out["investimento"] = None

    # Meta lateral: Modalidade, Duração...
    meta = {}
    for it in wrap.select(".course-single-meta .meta-item"):
        k = txt(it.find("strong")).rstrip(":")
        v = txt(it.select_one(".value"))
        if k:
            meta[k] = v
    out["modalidade"] = meta.pop("Modalidade", None)
    out["duracao"] = meta.pop("Duração mínima do curso", None)
    out["meta_extra"] = meta

    out["documentos_necessarios"] = []
    out["requisitos"] = []
    for seg in wrap.select(".tutor-single-course-segment"):
        titulo = txt(seg.select_one(".tutor-segment-title")).lower()
        if "documento" in titulo:
            out["documentos_necessarios"] = lista_itens(seg)
        elif "requisito" in titulo:
            out["requisitos"] = lista_itens(seg)

    img = wrap.select_one(".tutor-course-thumbnail img")
    out["imagem"] = img["src"] if img and img.get("src") else None
    return out


def sync_cursos(full=False):
    CURSOS_DIR.mkdir(parents=True, exist_ok=True)
    cats, tags, centros = taxonomia("course-category"), taxonomia("course-tag"), taxonomia("centro-de-ensino")
    remotos = lista_cursos()
    if not remotos:
        sys.exit("Falha ao listar cursos na API do unicive.com — abortando sem apagar nada.")

    ativos, pendentes = set(), []
    for c in remotos:
        categorias = [cats[i] for i in c.get("course-category", []) if i in cats]
        if any(k["slug"] in CATEGORIAS_EXCLUIDAS for k in categorias) or re.match(r"(?i)visita t[eé]cnica", limpa(c["title"]["rendered"])):
            continue
        ativos.add(c["slug"])
        arq = CURSOS_DIR / f"{c['slug']}.json"
        antigo = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None
        if full or not antigo or antigo.get("modificado") != c["modified"]:
            pendentes.append((c, categorias, antigo))

    print(f"{len(remotos)} cursos na API, {len(ativos)} válidos, {len(pendentes)} para baixar")

    def processa(item):
        c, categorias, antigo = item
        r = get(c["link"])
        if not r:
            return c["slug"], None
        det = parse_curso(r.text)
        seo = c.get("yoast_head_json") or {}
        curso = {
            "id": c["id"],
            "slug": c["slug"],
            "url": c["link"],
            "titulo": limpa(c["title"]["rendered"]),
            "publicado": c["date"],
            "modificado": c["modified"],
            "centro": [centros[i]["nome"] for i in c.get("centro-de-ensino", []) if i in centros],
            "categorias": [k["nome"] for k in categorias if not k["nome"].startswith("Centro de")],
            "tags": [tags[i]["nome"] for i in c.get("course-tag", []) if i in tags],
            "seo_descricao": limpa(seo.get("description") or seo.get("og_description")),
            **det,
            "sincronizado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "primeira_vez_visto": (antigo or {}).get("primeira_vez_visto")
            or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        (CURSOS_DIR / f"{c['slug']}.json").write_text(json.dumps(curso, ensure_ascii=False, indent=1), encoding="utf-8")
        return c["slug"], curso

    falhas = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for n, (slug, ok) in enumerate(ex.map(processa, pendentes), 1):
            falhas += ok is None
            if n % 50 == 0:
                print(f"  {n}/{len(pendentes)}")

    removidos = 0
    for arq in CURSOS_DIR.glob("*.json"):
        if arq.stem not in ativos:
            arq.unlink()
            removidos += 1
    print(f"Cursos: {len(pendentes) - falhas} atualizados, {falhas} falhas, {removidos} removidos")


def parse_pagina(html_txt):
    soup = BeautifulSoup(html_txt, "html.parser")
    for sel in ["header", "footer", "#wp-footer", "nav", "script", "style", "noscript", "form", "svg",
                ".tutor-modal", ".gva-offcanvas-content", "[style*='display: none']", "[style*='display:none']",
                "iframe", ".elementor-location-header", ".elementor-location-footer"]:
        for el in soup.select(sel):
            el.decompose()
    corpo = soup.select_one("[data-elementor-type='wp-page']") or soup.select_one("main") or soup.body
    blocos, vistos = [], set()
    for el in corpo.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "td"]):
        if el.find(["p", "li", "h1", "h2", "h3", "h4"]):
            continue
        t = txt(el)
        if len(t) < 3 or t in vistos:
            continue
        vistos.add(t)
        tipo = "titulo" if el.name in ("h1", "h2", "h3", "h4", "h5") else "texto"
        blocos.append({"tipo": tipo, "texto": t})
    return blocos


def sync_institucional():
    INST_DIR.mkdir(parents=True, exist_ok=True)
    for slug, nome in INSTITUCIONAL.items():
        url = f"{BASE}/{slug}/"
        r = get(url)
        if not r:
            print(f"  ! {slug}: indisponível")
            continue
        blocos = parse_pagina(r.text)
        if not blocos:
            continue
        pag = {"slug": slug, "titulo": nome, "url": url, "blocos": blocos,
               "sincronizado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        (INST_DIR / f"{slug}.json").write_text(json.dumps(pag, ensure_ascii=False, indent=1), encoding="utf-8")
    sync_contatos()
    print(f"Institucional: {len(list(INST_DIR.glob('*.json')))} páginas")


def sync_contatos():
    """Endereços, CNPJ, e-MEC e redes sociais, a partir do rodapé da home."""
    r = get(f"{BASE}/")
    if not r:
        return
    rodape = BeautifulSoup(r.text, "html.parser").select_one("#wp-footer, footer")
    if not rodape:
        return
    linhas = [t for t in rodape.stripped_strings]
    blocos, i = [], 0
    while i < len(linhas):
        t = re.sub(r"\s+", " ", linhas[i]).strip()
        if re.match(r"(Campus|Sede|N[uú]cleo)", t) and i + 1 < len(linhas):
            blocos.append({"tipo": "titulo", "texto": t})
            blocos.append({"tipo": "texto", "texto": re.sub(r"\s+", " ", linhas[i + 1]).strip() + " – Maringá/PR"})
            i += 2
            continue
        if re.match(r"(CNPJ|©)", t):
            blocos.append({"tipo": "texto", "texto": t})
        i += 1
    redes = sorted({a["href"] for a in rodape.select("a[href]")
                    if re.search(r"instagram|linkedin|facebook|youtube|tiktok", a["href"])})
    emec = next((a["href"] for a in rodape.select("a[href]") if "emec" in a["href"].lower()), None)
    if emec:
        blocos.append({"tipo": "texto", "texto": f"Cadastro da instituição no e-MEC: {emec}"})
    for u in redes:
        blocos.append({"tipo": "texto", "texto": f"Rede social oficial: {u}"})
    pag = {"slug": "contatos", "titulo": "Endereços e Contatos", "url": f"{BASE}/", "blocos": blocos,
           "sincronizado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (INST_DIR / "contatos.json").write_text(json.dumps(pag, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="baixa todos os cursos, não só os alterados")
    ap.add_argument("--so-cursos", action="store_true")
    ap.add_argument("--so-institucional", action="store_true")
    a = ap.parse_args()
    if not a.so_institucional:
        sync_cursos(full=a.full)
    if not a.so_cursos:
        sync_institucional()
