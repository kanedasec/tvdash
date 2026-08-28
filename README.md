# TV Dash

Organização de tarefas de casa e agenda, cadastradas por um bot do Telegram (grupo privado),
com dashboard web na rede local e um screensaver nativo na Roku TV.

## Estrutura

```
backend/   FastAPI + bot do Telegram + SQLite (roda no notebook)
roku/      Canal Roku (BrightScript/SceneGraph) sideloaded como screensaver
deploy/    Unit systemd para o backend rodar no boot
```

## 1. Configurar o backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edite `backend/.env`:
- `USER_NAMES` — nomes fixos dos dois usuários (ex: `Vernon,Luana`).
- `TIMEZONE`, `DB_PATH`, `PORT` — os padrões já funcionam.
- `TELEGRAM_BOT_TOKEN` e `ALLOWED_CHAT_ID` — preencha nos passos 2 e 3 abaixo.

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

## 4. Rodar o backend

```bash
cd backend
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Acesse `http://<ip-do-notebook>:8000` no navegador (celular ou notebook, mesma rede) para ver o dashboard.
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

## 5. Deixar o backend rodando sempre (systemd --user, sem sudo)

Usa um serviço `systemd --user` (não precisa de root) + `loginctl enable-linger` (permite o serviço
rodar mesmo sem estar logado, já a partir do boot):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/tvdash.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tvdash
loginctl enable-linger $USER
systemctl --user status tvdash
```

Reinício automático todo dia à 1h (não afeta o banco de dados — só reinicia o processo), via
crontab do próprio usuário (`crontab -e`, sem sudo):
```
0 1 * * * XDG_RUNTIME_DIR=/run/user/1000 systemctl --user restart tvdash
```
(`/run/user/1000` é o `XDG_RUNTIME_DIR` do usuário — confira o seu com `id -u`; sem essa variável o
`systemctl --user` chamado pelo cron não encontra a sessão e falha com "Failed to connect to bus".)

Se o notebook usa `ufw`, libere a porta na rede local:
```bash
sudo ufw allow from 192.168.18.0/24 to any port 8000
```

**Recomendado:** reserve um IP fixo para o notebook no seu roteador (DHCP reservation) — o canal
Roku aponta para um IP fixo (`192.168.18.4:8000` por padrão, ajustável em
`roku/components/TvDashScreensaver.brs`, função `BaseUrl()`).

## 6. Sideload do canal na Roku (Philco / Roku OS)

1. No controle da Roku, com a tela de Home aberta: **Home ×3, Cima ×2, Direita, Esquerda, Direita, Esquerda, Direita**.
2. Aceite o termo de licença de desenvolvedor.
3. Defina uma senha para o instalador web e anote o **IP da Roku** mostrado na tela.
4. No navegador (mesma rede), acesse `http://<ip-da-roku>`, faça login com usuário `rokudev` e a senha definida.
5. Se mudou o IP do notebook, edite `BaseUrl()` em `roku/components/TvDashScreensaver.brs` antes de gerar o zip.
6. Gere o pacote (já incluso neste repo como `tvdash-roku.zip`, ou regenere):
   ```bash
   cd roku
   zip -r ../tvdash-roku.zip manifest source components images
   ```
7. No instalador web, use "Upload" para enviar `tvdash-roku.zip` e clique em **Install**.

## 7. Ativar como screensaver

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
- O bot usa *long polling* (conexões de saída para a API do Telegram) — o notebook não precisa
  estar acessível pela internet para o bot funcionar.
- O dashboard web (porta 8000) **não tem autenticação** e é liberado só pra rede local
  (`192.168.18.0/24` via `ufw`) — qualquer dispositivo no Wi-Fi de casa consegue ver o painel.
  Aceitável pra um app doméstico, mas não exponha essa porta pra internet (sem port-forward no
  roteador).
- `backend/.env` guarda o token do bot em texto puro — trate como senha (não commite no git, não
  compartilhe o arquivo).
- Ponto único de falha: se o notebook ficar desligado/sem rede, bot e dashboard ficam fora do ar
  (sem redundância).

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
