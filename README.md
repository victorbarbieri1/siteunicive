# Base de Conhecimento Unicive para agente SDR

Site estático que espelha os cursos e as informações institucionais do
[unicive.com](https://unicive.com) e acrescenta, para cada curso, uma análise de
carreira (profissão, mercado de trabalho, tendências, faixa salarial, registro
profissional) e um guia de abordagem para o agente de IA de pré-vendas.
Eventos não entram na base.

## Como a integração funciona

1. `scripts/sync.py` lê a API pública do WordPress do unicive.com
   (`/wp-json/wp/v2/courses`) e baixa a página de cada curso **novo ou alterado**
   (modalidade, duração, descrição, matriz, coordenação, investimento, requisitos,
   documentos). Cursos removidos do site saem da base. Também coleta as páginas
   institucionais e os contatos oficiais.
2. `scripts/carreira_ia.py` (opcional) gera com o Claude uma análise de carreira
   específica para cada curso novo/alterado. Sem chave de API, a base curada
   `scripts/carreira_base.py` (53 áreas profissionais × 11 modalidades) garante
   que todo curso — inclusive um que acabou de ser criado — já tenha análise.
3. `scripts/build.py` gera o site em `site/`.
4. `.github/workflows/atualizar.yml` roda tudo **a cada 3 horas** (incremental) e
   **uma vez por dia** faz a varredura completa (preços e coordenação podem mudar
   sem alterar a data do curso), e publica no GitHub Pages.
5. O catálogo também consulta o unicive.com ao vivo e avisa quando há cursos
   publicados depois da última sincronização.

## Publicar (uma vez)

1. Crie um repositório no GitHub e envie esta pasta.
2. Em **Settings → Pages**, escolha **Source: GitHub Actions**.
3. (Opcional) Em **Settings → Secrets and variables → Actions**, crie o segredo
   `ANTHROPIC_API_KEY` para ativar as análises por IA. A primeira execução gera
   ~1.160 análises via Batch API (custo único estimado de US$ 20–30 com
   `claude-opus-5-5`); depois, só cursos novos ou alterados são processados.
4. Em **Actions → Atualizar base de conhecimento → Run workflow**, rode a primeira vez.

O site fica em `https://<usuario>.github.io/<repositorio>/`.

## O que entregar ao agente de IA

| Fonte | Uso |
|---|---|
| `llms-full.txt` | Toda a base em um arquivo Markdown |
| `kb/*.md` | A mesma base fatiada por modalidade (para limites de upload) |
| `llms.txt` | Índice no padrão llms.txt, com um `.md` por curso |
| `api/cursos.json` | Dados estruturados, incluindo a análise de carreira |
| `cursos/<slug>.html` | Páginas para agentes que navegam por URL |

Se a plataforma do agente aceita URL como fonte (recrawl periódico), aponte para
`llms-full.txt` ou para os arquivos de `kb/`: eles mudam sozinhos a cada sincronização.

## Rodar localmente

```bash
pip install -r requirements.txt
python scripts/sync.py          # --full para baixar tudo
python scripts/carreira_ia.py   # opcional, requer ANTHROPIC_API_KEY
python scripts/build.py
python -m http.server 8765 --directory site
```

## Ajustes comuns

- **Áreas de carreira, faixas salariais, argumentos de venda:** `scripts/carreira_base.py`.
- **Respostas a objeções e perguntas de qualificação:** `scripts/analise.py`.
- **Páginas institucionais coletadas:** dicionário `INSTITUCIONAL` em `scripts/sync.py`.
- **Frequência de atualização:** `cron` em `.github/workflows/atualizar.yml`.
