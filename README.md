# Jarvis

Assistente pessoal em Python com interface de terminal e opcionalmente web (Gradio), provedores Google Gemini e Groq, memória limitada, cache, orçamento diário de tokens e ferramentas seguras.

## Requisitos e instalação

- Python 3.10 ou superior
- Uma chave de API do Gemini ou Groq

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuração de API

Copie `.env.example` para `.env`, preencha somente a chave do provedor que pretende usar e deixe a outra vazia:

```env
GEMINI_API_KEY=
GROQ_API_KEY=
DEFAULT_PROVIDER=gemini
```

- Gemini: [Google AI Studio](https://aistudio.google.com/apikey)
- Groq: [Groq Console](https://console.groq.com/keys)

As chaves são lidas do `.env` via `python-dotenv`, nunca são embutidas no código. Não compartilhe nem versiona o `.env`.

## Modelos e fallback

Defaults validados na documentação oficial em 05/10/2026:

| Provider | Modelo principal | Fallback do mesmo provider |
|---|---|---|
| Gemini | `gemini-3.8-flash` | `gemini-2.5-flash` |
| Groq | `openai/gpt-oss-20b` | `openai/gpt-oss-120b` |

Fontes: [modelos Gemini](https://ai.google.dev/gemini-api/docs/models), [depreciações Gemini](https://ai.google.dev/gemini-api/docs/deprecations), [modelos Groq](https://console.groq.com/docs/models), [GPT-OSS 20B na Groq](https://console.groq.com/docs/model/openai/gpt-oss-20b) e [GPT-OSS 120B na Groq](https://console.groq.com/docs/model/openai/gpt-oss-120b). Configure `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `GROQ_MODEL` e `GROQ_FALLBACK_MODELS` no `.env` se precisar ajustar a disponibilidade da sua conta.

**Isolamento obrigatório:** `/provider gemini` chama somente Gemini; `/provider groq` chama somente Groq. Se o provider selecionado falhar, o erro daquele provider é mostrado, a seleção permanece inalterada e não se chama o outro provider. O fallback automático, quando aplicável, tenta somente outro modelo do mesmo provider. Erros de autenticação e quota diária não fazem retries ou fallback inúteis. O usuário escolhe uma troca manualmente.

## Executar

```bash
python main.py       # terminal
python web.py        # Gradio em http://127.0.0.1:7860
```

## Comandos do terminal

- `/help` — ajuda e ferramentas
- `/status` — provider e modelo atuais, providers disponíveis, mensagens, ferramentas e uso/cota
- `/usage` — contadores de sessão e do dia
- `/provider gemini` / `/provider groq` — troca explícita (o provider precisa ter chave/cliente disponível)
- `/clear` — limpa memória
- `/cache` — limpa cache
- `/exit` ou `/quit` — encerra

## Ferramentas

O catálogo `plugins` registra ferramentas com nomes normalizados, JSON Schema validado e despacho somente para funções registradas. O ciclo de chamada é modelo → tool call → execução → resultado → modelo → resposta final, com limite configurável (`MAX_TOOL_ROUNDS`). Erros de uma ferramenta são devolvidos como resultados de erro sem derrubar o Jarvis.

- `calculator`: aritmética por AST com operações explicitamente permitidas; não usa `eval` nem `exec`.
- `web_search`: pesquisa textual pela biblioteca `ddgs` (API oficial do pacote `DDGS.text`); limita resultados e tamanho de trechos, tratando conteúdo de páginas como **dados não confiáveis**, jamais como instruções.

Se a pesquisa falhar por rede/bloqueio do mecanismo, a ferramenta retorna um erro controlado e o restante do app continua funcionando.

## Memória, cache e tokens

| Variável | Padrão | Uso |
|---|---:|---|
| `MEMORY_MAX_MESSAGES` | `30` | Limite de mensagens; ajustado para preservar pares user/assistant |
| `TOKENS_PER_DAY` | `200000` | Orçamento diário; `0` = ilimitado |
| `USAGE_FILE` | `data/usage.json` | Persistência diária (UTC) |
| `MAX_OUTPUT_TOKENS` | `1024` | Limite de saída por resposta |
| `CONTEXT_TOKEN_BUDGET` | `2000` | Orçamento estimado do histórico, mantendo turnos completos |
| `CACHE_TTL_HOURS` | `24` | TTL; `0` desativa |
| `CACHE_MAX_ENTRIES` | `256` | Máximo de itens; `0` desativa |
| `MAX_RETRIES` | `2` | Repetições após a primeira tentativa em falhas transitórias |
| `RETRY_BASE_SECONDS` | `1.0` | Base do backoff exponencial com jitter |
| `MAX_TOOL_ROUNDS` | `4` | Limite para ciclos de tools por resposta |

Uso confirmado pela API é registrado uma vez quando a resposta final tem sucesso; falhas não entram como resposta de IA na memória nem no cache. O cache diferencia provider, modelo, pergunta, histórico (incluindo papel user/assistant) e prompt de sistema.

## Testes

No diretório do projeto:

```bash
python -m pytest -v
python -m compileall .
```

A suíte usa clientes falsos/mocks, sem chamadas pagas ou dependência de chaves reais. Ela cobre os dois sentidos do isolamento, seleção CLI de provider, fallback entre modelos do mesmo provider, retries/quota, cache, memória, tokens e execução de ferramentas.

## Estrutura

```text
jarvis/
├── main.py
├── web.py
├── requirements.txt
├── .env.example
├── core/ (configuração, LLM, cache, memória e tokens)
├── plugins/ (registro de ferramentas seguras)
└── tests/
```
