# MyWhoosh → Garmin Connect (via intervals.icu)

Envia automaticamente as suas pedaladas do **MyWhoosh** para o **Garmin Connect**, com potência,
frequência cardíaca e cadência, contando para Training Effect e carga de treino do Garmin.

> **Fork modificado** de [marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin),
> de Marcelo Rodrigo, distribuído sob a mesma licença **GPL-3.0**. Modificado por [m-diniz](https://github.com/m-diniz) a partir de
> 2026-11-20. As mudanças estão listadas em [Diferenças em relação ao original](#diferenças-em-relação-ao-original)
> e no histórico do git.

*English summary: automatic MyWhoosh → Garmin Connect sync for Windows. Rides are fetched from
intervals.icu (MyWhoosh's official integration) instead of the MyWhoosh API, Garmin login is
token-based with MFA support, and no password is stored on disk. Modified fork of
marcelorodrigo/mywhoosh-to-garmin, GPL-3.0.*

## Como funciona

```
MyWhoosh ──(conexão oficial)──► intervals.icu ──(esta ferramenta, a cada 15 min)──► Garmin Connect
```

1. O MyWhoosh envia cada pedalada para o intervals.icu (Connections → intervals.icu).
2. A ferramenta busca no intervals.icu as atividades novas vindas do MyWhoosh e baixa o **arquivo FIT original**.
3. Ajusta só a identificação do dispositivo para **Garmin Edge 840**. Os dados não são alterados.
   É isso que faz o Garmin calcular Training Effect, carga e status de treino.
4. Envia ao Garmin Connect, sem duplicar, e avisa por notificação do Windows.

**Por que não a API do MyWhoosh?** Ela aceita uma sessão por conta e recusa o login
("You are already logged in from another device") enquanto o app estiver logado em algum aparelho,
mesmo depois de sair da conta. Na prática, disputaria a sessão com o seu próprio app.

## Segurança

| Segredo | Onde fica |
|---|---|
| Chave de API do intervals.icu | Gerenciador de Credenciais do Windows (`keyring`). Revogável no intervals.icu. |
| Senha e MFA do Garmin | Não são gravados. São digitados uma vez, e só o token fica em `~/.garminconnect-mywhoosh`. |
| Senha do MyWhoosh | Não é usada. |

O `.env` só tem dados que não são segredo, como o Athlete ID. `.env`, `state.json`, `.alerts.json`
e `sync.log` ficam fora do git.

## Instalação (Windows)

Requisitos: Python 3.11+, uma conta no [intervals.icu](https://intervals.icu) (grátis) e uma conta Garmin Connect.

```powershell
git clone https://github.com/m-diniz/mywhoosh-to-garmin.git
cd mywhoosh-to-garmin
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # preencha INTERVALS_ATHLETE_ID
```

1. **MyWhoosh:** Connections → intervals.icu → *Connect*.
   No intervals.icu, **não** ligue o Garmin, senão a atividade volta duplicada.
2. **Chave do intervals.icu** (Settings → Developer Settings → API Key):
   `venv\Scripts\python.exe main.py --setup`
3. **Login no Garmin** (pede e-mail, senha e o código MFA, se houver):
   `venv\Scripts\python.exe scripts\login_garmin.py`
4. **Teste:**
   `venv\Scripts\python.exe main.py --list` mostra o que há no intervals.icu e não envia nada.
   `venv\Scripts\python.exe main.py` envia as atividades novas dos últimos 14 dias.
5. **Automatize** (a cada 15 min e no logon do Windows):
   `powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1`
   Para remover: o mesmo comando com `-Remover`.

> Os passos 2 e 3 pedem digitação. Rode-os num PowerShell normal, não em ferramentas
> que não oferecem um terminal interativo.

## Uso no dia a dia

Não há nada a fazer: pedale, e a atividade aparece no Garmin em até ~20 minutos.

- **Notificações:** a ferramenta avisa quando uma pedalada é enviada. Avisa também quando algo precisa de você:
  token do Garmin vencido ou chave do intervals.icu recusada. Falhas passageiras, como rede ou serviço fora do ar,
  só geram aviso se durarem mais de 1 hora. Cada problema é avisado uma vez só.
- **Log:** `sync.log`, com rotação automática.
- **Sem duplicatas:** `state.json` guarda o que já foi enviado. A ferramenta também verifica se o Garmin já
  tem uma atividade no mesmo horário.

| Código de saída | Significado |
|---|---|
| 0 | ok |
| 1 | falha ao enviar (tenta de novo na próxima execução) |
| 2 | configuração ou chave do intervals.icu |
| 3 | refazer `scripts\login_garmin.py` |
| 4 | o Garmin limitou as requisições (429); tenta de novo sozinho |

### Configurações opcionais (`.env`)

| Variável | Padrão | Uso |
|---|---|---|
| `INTERVALS_SOURCE` | `MYWHOOSH` | Envia só atividades cuja origem/dispositivo contém este texto (`ALL` = todas) |
| `SYNC_MAX_AGE_DAYS` | `14` | Ignora atividades mais antigas |
| `SYNC_LIMIT` | `20` | Máximo de atividades consideradas por execução |
| `GARMIN_TOKENSTORE` | `~/.garminconnect-mywhoosh` | Pasta do token do Garmin |
| `LOG_LEVEL` | `INFO` | Nível de log |

O dispositivo simulado (Edge 840: fabricante 1, produto 4024, software 20.19) pode ser trocado em
`services/fit_file_service.py`.

## Desenvolvimento

```powershell
venv\Scripts\python.exe -m pytest -q
```

A arquitetura e as regras do projeto estão em [AGENTS.md](AGENTS.md).

## Diferenças em relação ao original

Em relação a [marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin):

- **Origem:** intervals.icu no lugar da API do MyWhoosh, por causa do limite de uma sessão por conta.
  O cliente da API do MyWhoosh e o cliente Zwift, que não era usado, foram removidos.
- **Login do Garmin:** `garminconnect` 0.3.x, só por token, com suporte a MFA. O fluxo antigo
  baseado no `garth` deixou de funcionar.
- **Credenciais:** nenhuma senha no `.env`. A chave fica no keyring do sistema.
- **Sincronização:** envia todas as atividades novas, não só a última. Usa `state.json`, pausa entre
  envios e para quando o Garmin responde 429.
- **Windows:** tarefa agendada, notificações e log com rotação.
- O que foi mantido do original: o ajuste do FIT para Garmin Edge 840 (`fit_file_service.py`) e a
  checagem de duplicatas no Garmin.

## Licença e créditos

**GNU General Public License v3.0**, ver [LICENSE](LICENSE).

- Projeto original: © Marcelo Rodrigo ([marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin)).
- Modificações: © 2026 [m-diniz](https://github.com/m-diniz), sob a mesma licença.
- Documentação comunitária da API: [mywhoosh-community/mywhoosh-api](https://github.com/mywhoosh-community/mywhoosh-api).
- Bibliotecas: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect), [fit-tool](https://pypi.org/project/fit-tool/), [keyring](https://pypi.org/project/keyring/).

Projeto pessoal, sem vínculo com MyWhoosh, Garmin ou intervals.icu. Use por sua conta e risco.
