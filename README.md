# Jarvis

Assistente de IA pessoal em Python, com suporte a **Google Gemini** e **Groq**, memória de conversa e sistema de plugins extensível.

## Requisitos

- Python 3.10+
- Uma chave de API do Gemini ou Groq

## Instalação

```bash
git clone https://github.com/maxoutlier7-jpg/jarvis.git
cd jarvis
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuração

Copie `.env.example` para `.env` e configure pelo menos uma chave:

```env
GEMINI_API_KEY=sua_chave
GROQ_API_KEY=sua_chave
DEFAULT_PROVIDER=gemini
```

Chaves:

- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com/keys

O `.env` não deve ser enviado ao GitHub.

## Executar

```bash
python main.py
```

## Comandos

- `/clear` — limpa a memória da conversa
- `/provider gemini` — troca para Gemini
- `/provider groq` — troca para Groq
- `/status` — mostra o estado atual
- `/help` — mostra os comandos
- `/exit` ou `/quit` — encerra o Jarvis

## Estrutura

```text
jarvis/
├── main.py
├── requirements.txt
├── .env.example
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── memory.py
│   └── llm.py
└── plugins/
    └── __init__.py
```

## APIs utilizadas

O Jarvis usa o SDK `google-genai` para o Gemini e o SDK `groq` para o Groq. A integração Gemini foi atualizada para o SDK atual recomendado pelo Google. citeturn0search2turn0search5

A integração Groq usa Chat Completions, conforme a API Python oficial. citeturn0search0turn0search10

## Próximos passos

- Voz (Speech-to-Text e Text-to-Speech)
- Plugins de clima, navegador e automação
- Memória persistente
- Interface web
- Ferramentas e chamadas de função
