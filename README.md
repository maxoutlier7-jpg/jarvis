# Jarvis

Assistente de IA pessoal **super inteligente**.

Suporta **Google Gemini** e **Groq** (ambos gratuitos).  
Sistema de plugins extensível + memória de conversa.

## Como usar

### 1. Clone o repositório
```bash
git clone https://github.com/maxoutlier7-jpg/jarvis.git
cd jarvis
```

### 2. Crie o ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure a API Key
Copie o arquivo de exemplo:
```bash
cp .env.example .env
```

Abra o arquivo `.env` e coloque sua chave:

```env
# Escolha uma das duas (ou as duas)
GEMINI_API_KEY=sua_chave_aqui
GROQ_API_KEY=sua_chave_aqui

# Qual provedor usar por padrão: gemini ou groq
DEFAULT_PROVIDER=gemini
```

#### Onde pegar as chaves gratuitas:
- **Gemini (recomendado)**: https://aistudio.google.com/apikey
- **Groq (muito rápido)**: https://console.groq.com/keys

### 5. Rode o Jarvis
```bash
python main.py
```

## Comandos

- Digite normalmente para conversar
- `/clear` — limpa a memória da conversa
- `/provider gemini` ou `/provider groq` — troca o modelo
- `/help` — mostra ajuda
- `/exit` ou `/quit` — sai

## Estrutura do projeto

```
jarvis/
├── main.py              # Ponto de entrada
├── requirements.txt
├── .env.example
├── core/
│   ├── llm.py           # Integração com Gemini e Groq
│   ├── memory.py        # Memória da conversa
│   └── config.py        # Configurações
└── plugins/
    └── __init__.py      # Sistema de plugins (pronto para expansão)
```

## Próximos passos possíveis
- Voz (Speech-to-Text + Text-to-Speech)
- Mais plugins (abrir sites, clima, controle do PC, etc.)
- Interface web
- Memória de longo prazo

Feito com ❤️ para ser o seu Jarvis.
