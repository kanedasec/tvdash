# TV Dash

Organização de tarefas de casa e agenda, cadastradas por um bot do Telegram (grupo privado),
com dashboard web hospedado em VPS e um screensaver nativo na Roku TV.

## Fluxo de contribuição e entrega

O código segue `feature/* -> Pull Request -> main`. Pull requests executam os
testes do backend e as verificações diferenciais de SAST, segredos e SCA. Após
um merge protegido, a pipeline publica uma imagem imutável no GHCR com a tag
`sha-<commit>` e a entrega ao VPS por Tailscale e SSH restrito. O VPS apenas
executa a imagem; ele não compila o código-fonte.

As instruções e os limites de confiança da automação estão em
[`AGENTS.md`](AGENTS.md).

## Estrutura

```
backend/   FastAPI + bot do Telegram + SQLite
roku/      Canal Roku (BrightScript/SceneGraph) sideloaded como screensaver
```

## 1. Configurar o ambiente

O backend nativo e o `compose.yml` público usam o mesmo arquivo privado `backend/.env`. Ele é
ignorado pelo Git e nunca deve ser commitado.

```bash
[ -e backend/.env ] || cp backend/.env.example backend/.env
```

Edite `backend/.env`:
- `USER_NAMES` — nomes fixos dos dois usuários (ex: `Pessoa1,Pessoa2`).
- `TIMEZONE`, `DB_PATH`, `PORT` — os padrões já funcionam.
- `TELEGRAM_BOT_TOKEN` e `ALLOWED_CHAT_ID` — preencha nos passos 2 e 3 abaixo.
- `AUTH_ENABLED`, `WEB_USERNAME`, `WEB_PASSWORD` e `ROKU_API_KEY` — protegem o deploy no VPS.

Por padrão, o Compose carrega esse arquivo com:

```yaml
env_file:
  - ./backend/.env
```

Para manter as credenciais em outro diretório, informe um caminho absoluto ou relativo sem editar
o Compose:

```bash
TVDASH_ENV_FILE=/caminho/privado/tvdash.env docker compose up -d --build
```

O arquivo escolhido precisa conter, no mínimo, `TELEGRAM_BOT_TOKEN`, `ALLOWED_CHAT_ID` e
`USER_NAMES` para o bot funcionar. `TIMEZONE` e `REMINDER_HOUR` são opcionais e possuem valores
padrão.

## 2. Criar o bot no Telegram

1. Abra uma conversa com **@BotFather** no Telegram.
2. Envie `/newbot`, escolha um nome e um username (precisa terminar em `bot`).
3. O BotFather devolve um token — cole em `TELEGRAM_BOT_TOKEN` no `.env`.

## 3. Criar o grupo privado e descobrir o chat_id

1. Crie um grupo no Telegram com você e sua esposa.
2. Adicione o bot criado no passo anterior a esse grupo.
3. Mande qualquer mensagem no grupo (ex: "oi").
4. Rode:
   ```bash
   cd backend
   ./.venv/bin/python get_chat_id.py
   ```
5. Copie o `chat_id` impresso (número negativo) para `ALLOWED_CHAT_ID` no `.env`.

O bot só responde a mensagens desse `chat_id` — em qualquer outro chat, ele ignora silenciosamente.

## 4. Rodar localmente (opcional)

Com Docker Compose:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f tvdash
```

Por padrão, o serviço fica disponível somente em `127.0.0.1:8000` e o SQLite é persistido no
volume nomeado `tvdash-data`. Configure autenticação em `backend/.env` se outras pessoas ou
dispositivos puderem acessar essa porta.

- `AUTH_ENABLED=false`: não solicita login; indicado apenas para desenvolvimento local restrito a
  `127.0.0.1`.
- `AUTH_ENABLED=true`: o dashboard solicita `WEB_USERNAME` e `WEB_PASSWORD`; a API também aceita a
  `ROKU_API_KEY` nas rotas `/api/*`.

Para parar sem apagar o banco persistido:

```bash
docker compose down
```

Sem Docker:

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acesse `http://127.0.0.1:8000` no navegador para desenvolvimento local.
Tem duas abas — **Tarefas de Casa** e **Atividade Física** — e um seletor de período (semana/mês/ano)
que controla o calendário e os gráficos de ranking de ambas. No calendário, a visão de mês é uma
grade (com contagem de atividades por dia) e a de ano é um heatmap estilo GitHub (mais escuro =
mais atividade naquele dia) — passe o mouse numa célula pra ver o detalhe.

Na primeira execução, os dois usuários de `USER_NAMES` são criados automaticamente no banco.

### Comandos do bot (dentro do grupo autorizado)

| Comando | Uso |
|---|---|
| `/eusou Nome` | **Rode uma vez cada um**, com o nome exatamente como está em `USER_NAMES`, pra vincular sua conta do Telegram ao seu nome. Sem isso, `/feito` não sabe quem é quem. |
| `/novatarefa Nome \| peso \| duracao_min` | Cadastra um tipo de tarefa. Ex: `/novatarefa Lavar louça \| 3 \| 15` |
| `/editartarefa Nome \| novo peso \| nova duracao_min` | Edita peso/duração de uma tarefa já cadastrada. Ex: `/editartarefa Lavar louça \| 5 \| 20` |
| `/tarefas` | Lista as tarefas cadastradas |
| `/feito Nome da tarefa \| duracao_min \| DD/MM` | Registra que você concluiu a tarefa. Duração e data são opcionais, em qualquer ordem — sem duração usa o padrão cadastrado na tarefa; sem data marca agora. Ex: `/feito Levar lixo`, `/feito Levar lixo \| 25` ou `/feito Levar lixo \| 12/08` |
| `/planejar Nome da tarefa \| DD/MM \| recorrencia` | Agenda a tarefa pra um dia — aparece como pendente no calendário até alguém rodar `/feito`. Recorrência é opcional. Ex: `/planejar Levar lixo \| 12/08` ou `/planejar Levar lixo \| 12/08 \| semanal` |
| `/cancelartarefa Nome da tarefa \| DD/MM` | Cancela planejamento(s). Sem data, cancela tudo (inclusive recorrência). Ex: `/cancelartarefa Levar lixo` |
| `/compromisso DD/MM HH:MM Descrição \| recorrencia` | Cadastra um compromisso. Recorrência é opcional. Ex: `/compromisso 25/12 19:00 Ceia de Natal` ou `/compromisso 10/08 08:00 Regar plantas \| diaria` |
| `/cancelarcompromisso Descrição \| DD/MM` | Cancela compromisso(s) pelo título. Sem data, cancela tudo (inclusive recorrência). Ex: `/cancelarcompromisso Reuniao semanal` |
| `/agenda` | Lista os próximos compromissos (marca `(recorrente)` quando aplicável) |
| `/novoexercicio Nome \| duracao_min padrão` | Cadastra um tipo de exercício. Ex: `/novoexercicio Corrida \| 30` |
| `/exercicios` | Lista os exercícios cadastrados (com o padrão de duração) |
| `/exercicio Nome \| duracao_min \| DD/MM` | Registra um checkin. Duração e data são opcionais, em qualquer ordem — sem duração usa o padrão cadastrado no exercício. Ex: `/exercicio Corrida`, `/exercicio Corrida \| 45` ou `/exercicio Corrida \| 10/08` |
| `/start` ou `/ajuda` | Mostra a lista de comandos |

**Recorrência aceita:** `diaria`, `semanal`, `mensal`, ou `cada N dias/semanas/meses` (ex: `cada 3
dias`). Vale tanto pra `/planejar` quanto pra `/compromisso`. A recorrência mensal preserva o dia
do mês corretamente (ex: dia 31 recorrendo em fevereiro cai no dia 28, e volta pro dia 31 em
meses que têm esse dia).

## 5. Sideload do canal na Roku (Philco / Roku OS)

1. No controle da Roku, com a tela de Home aberta: **Home ×3, Cima ×2, Direita, Esquerda, Direita, Esquerda, Direita**.
2. Aceite o termo de licença de desenvolvedor.
3. Defina uma senha para o instalador web e anote o **IP da Roku** mostrado na tela.
4. No navegador (mesma rede), acesse `http://<ip-da-roku>`, faça login com usuário `rokudev` e a senha definida.
5. Defina `TVDASH_BASE_URL` e `TVDASH_ROKU_API_KEY` ao gerar o pacote, ou copie
   `roku/source/config.example.brs` para o arquivo ignorado `roku/source/config.brs`.
6. Gere o pacote:
   ```bash
   ./roku/build.sh
   ```
7. No instalador web, use "Upload" para enviar `tvdash-roku.zip` e clique em **Install**.

## 6. Ativar como screensaver

Na Roku: **Configurações → Tela → Protetor de tela → Tipo de protetor de tela** → selecione
**"TV Dash - Painel de Tarefas"**. Ajuste o tempo de inatividade em "Iniciar após" como preferir.

O painel alterna entre dois menus a cada 20s — **Casa** (calendário da semana com pendente `[ ]`/feita
`[x]`, pontos por pessoa, tempo por pessoa, tempo por atividade) e **Exercícios** (calendário da
semana com os checkins, tempo por pessoa, checkins por pessoa, tempo por tipo) — atualizando os
dados a cada 30s. Diferente do dashboard web, a Roku só mostra o período "semana" (é um protetor de
tela, não dá pra navegar com o controle pra trocar de período; mês/ano ficam só no dashboard web).
Se o backend cair ou a rede oscilar, ele mostra "sem conexão" e volta a atualizar sozinho quando a
conexão voltar.

## Segurança

- O bot só processa mensagens do `chat_id` configurado em `ALLOWED_CHAT_ID` — qualquer outro chat
  é ignorado.
- O bot usa *long polling* (conexões de saída para a API do Telegram) — não precisa receber webhook
  nem ter uma porta pública exclusiva.
- No VPS, o dashboard usa HTTP Basic Auth e a API aceita uma chave separada para a Roku. As duas
  credenciais trafegam apenas por HTTPS.
- O container de produção não deve publicar a porta 8000 diretamente; use um proxy HTTPS.
- Os arquivos de ambiente guardam o token do bot em texto puro — trate-os como senha (não commite
  nem compartilhe esses arquivos).
- `roku/source/config.brs` e o ZIP gerado contêm a chave da Roku e também não devem ser publicados.

## Limitações conhecidas / avisos

- O código do canal Roku (BrightScript) foi escrito, testado e ajustado em cima do Roku real da
  Philco durante o desenvolvimento — mas esse firmware (Roku OS 15.2 nesse modelo) tem uma
  particularidade encontrada na prática: criar um `Font` node manualmente
  (`CreateObject("roSGNode","Font")`) e atribuí-lo a um Label não renderiza texto nenhum. A solução
  usada em todo o código é atribuir a string da fonte de sistema direto no campo `.font` do Label
  (ex: `lbl.font = "font:MediumSystemFont"`) — funciona nesse aparelho. Se notar textos invisíveis
  de novo após alguma alteração futura, essa é a primeira coisa a checar.
- "Semana" = segunda a domingo; "mês" = mês calendário; fuso `America/Sao_Paulo`. Ajustável em
  `backend/app/crud.py` (`period_bounds`).
- Todo dia, no horário definido em `REMINDER_HOUR` (padrão 20h, ajustável no `.env`), o bot manda
  no grupo a lista de compromissos do dia seguinte (`backend/app/reminders.py`). Não avisa se não
  houver nenhum compromisso marcado.
