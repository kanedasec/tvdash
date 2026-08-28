const CORES = ["#5eb1ff", "#ffb75e", "#7ee787", "#f78ca0", "#c792ea"];
const NOMES_DIA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

let abaAtual = "casa";
let periodoAtual = "semana";
const graficos = {};

async function buscarJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Falha ao buscar ${url}: ${resp.status}`);
  return resp.json();
}

function graficoBarra(idCanvas, labels, dados, opcoes = {}) {
  const canvas = document.getElementById(idCanvas);
  if (graficos[idCanvas]) {
    graficos[idCanvas].data.labels = labels;
    graficos[idCanvas].data.datasets[0].data = dados;
    graficos[idCanvas].update();
    return;
  }
  graficos[idCanvas] = new Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ data: dados, backgroundColor: opcoes.cores || CORES }] },
    options: {
      indexAxis: opcoes.horizontal ? "y" : "x",
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#e8eaed" }, grid: { color: "#2a2e37" }, beginAtZero: true },
        y: { ticks: { color: "#e8eaed" }, grid: { color: "#2a2e37" }, beginAtZero: true },
      },
    },
  });
}

function redimensionarGraficosDoPainel(painelId) {
  document.getElementById(painelId).querySelectorAll("canvas").forEach((c) => {
    if (graficos[c.id]) graficos[c.id].resize();
  });
}

function formatarHojeDDMM() {
  const hoje = new Date();
  return `${String(hoje.getDate()).padStart(2, "0")}/${String(hoje.getMonth() + 1).padStart(2, "0")}`;
}

function itensDoDia(dia, tipoPainel) {
  if (tipoPainel === "casa") {
    const itens = [];
    for (const t of dia.tarefas) {
      itens.push({
        texto: (t.status === "feita" ? "✓ " : "○ ") + t.nome,
        classe: t.status === "feita" ? "item-feita" : "item-pendente",
      });
    }
    for (const c of dia.compromissos) {
      itens.push({ texto: `${c.hora} ${c.titulo}`, classe: "item-compromisso" });
    }
    return itens;
  }
  return dia.checkins.map((c) => ({
    texto: `${c.pessoa}: ${c.tipo} (${c.duracao_min}min)`,
    classe: "item-checkin",
  }));
}

function renderizarCalendario(container, dias, periodo, tipoPainel) {
  container.innerHTML = "";
  if (periodo === "semana") return renderizarCalendarioSemana(container, dias, tipoPainel);
  if (periodo === "mes") return renderizarCalendarioMes(container, dias, tipoPainel);
  return renderizarCalendarioAno(container, dias, tipoPainel);
}

function renderizarCalendarioSemana(container, dias, tipoPainel) {
  container.className = "calendario-semana";
  const hojeStr = formatarHojeDDMM();
  for (const dia of dias) {
    const col = document.createElement("div");
    col.className = "dia-coluna" + (dia.data === hojeStr ? " dia-hoje" : "");

    const cab = document.createElement("div");
    cab.className = "dia-cabecalho";
    cab.textContent = `${dia.dia_semana} ${dia.data}`;
    col.appendChild(cab);

    const itens = itensDoDia(dia, tipoPainel);
    if (itens.length === 0) {
      const vazio = document.createElement("div");
      vazio.className = "dia-vazio";
      vazio.textContent = "—";
      col.appendChild(vazio);
    }
    for (const item of itens) {
      const el = document.createElement("div");
      el.className = "dia-item " + item.classe;
      el.textContent = item.texto;
      col.appendChild(el);
    }
    container.appendChild(col);
  }
}

function renderizarCalendarioMes(container, dias, tipoPainel) {
  container.className = "calendario-mes";
  const hojeStr = formatarHojeDDMM();
  const primeiroIdx = NOMES_DIA.indexOf(dias[0].dia_semana);
  for (let i = 0; i < primeiroIdx; i++) {
    const vazia = document.createElement("div");
    vazia.className = "cel-mes cel-vazia";
    container.appendChild(vazia);
  }
  for (const dia of dias) {
    const itens = itensDoDia(dia, tipoPainel);
    const cel = document.createElement("div");
    cel.className = "cel-mes" + (dia.data === hojeStr ? " dia-hoje" : "");
    cel.title = itens.length ? itens.map((i) => i.texto).join("\n") : "Sem atividade";

    const numero = document.createElement("span");
    numero.className = "cel-mes-numero";
    numero.textContent = dia.data.split("/")[0];
    cel.appendChild(numero);

    if (itens.length > 0) {
      const contagem = document.createElement("span");
      contagem.className = "cel-mes-contagem";
      contagem.textContent = String(itens.length);
      cel.appendChild(contagem);
    }
    container.appendChild(cel);
  }
}

function intensidadeClasse(n) {
  if (n === 0) return "i0";
  if (n === 1) return "i1";
  if (n <= 3) return "i2";
  if (n <= 5) return "i3";
  return "i4";
}

function renderizarCalendarioAno(container, dias, tipoPainel) {
  const wrap = document.createElement("div");
  wrap.className = "calendario-ano-wrap";
  const grid = document.createElement("div");
  grid.className = "calendario-ano";

  const primeiroIdx = NOMES_DIA.indexOf(dias[0].dia_semana);
  for (let i = 0; i < primeiroIdx; i++) {
    const vazia = document.createElement("div");
    vazia.className = "cel-ano cel-vazia";
    grid.appendChild(vazia);
  }
  for (const dia of dias) {
    const itens = itensDoDia(dia, tipoPainel);
    const cel = document.createElement("div");
    cel.className = `cel-ano ${intensidadeClasse(itens.length)}`;
    cel.title = `${dia.data}: ${itens.length ? itens.length + " atividade(s)" : "sem atividade"}`;
    grid.appendChild(cel);
  }
  wrap.appendChild(grid);
  container.appendChild(wrap);
}

function renderizarAgenda(compromissos) {
  const lista = document.getElementById("lista-agenda");
  lista.innerHTML = "";
  if (compromissos.length === 0) {
    lista.innerHTML = '<li class="vazio">Nenhum compromisso futuro.</li>';
    return;
  }
  for (const c of compromissos) {
    const data = new Date(c.data_hora);
    const sufixo = c.recorrente ? " (recorrente)" : "";
    const li = document.createElement("li");
    li.innerHTML = `<span>${c.titulo}${sufixo}</span><span>${data.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</span>`;
    lista.appendChild(li);
  }
}

function renderizarListaSimples(idLista, itens, vazio) {
  const lista = document.getElementById(idLista);
  lista.innerHTML = "";
  if (itens.length === 0) {
    lista.innerHTML = `<li class="vazio">${vazio}</li>`;
    return;
  }
  for (const html of itens) {
    const li = document.createElement("li");
    li.innerHTML = html;
    lista.appendChild(li);
  }
}

async function atualizarCasa() {
  const [ranking, tempoPessoa, tempoAtividade, pesoAtividade, calendario, agenda, tarefas] = await Promise.all([
    buscarJson(`/api/ranking?periodo=${periodoAtual}`),
    buscarJson(`/api/tempo/pessoa?periodo=${periodoAtual}`),
    buscarJson(`/api/tempo?periodo=${periodoAtual}`),
    buscarJson(`/api/peso?periodo=${periodoAtual}`),
    buscarJson(`/api/tarefas/calendario?periodo=${periodoAtual}`),
    buscarJson("/api/agenda"),
    buscarJson("/api/tarefas"),
  ]);

  graficoBarra("grafico-ranking", ranking.map((r) => r.nome), ranking.map((r) => r.pontos));
  graficoBarra("grafico-tempo-pessoa", tempoPessoa.map((r) => r.nome), tempoPessoa.map((r) => r.minutos_totais));
  graficoBarra(
    "grafico-tempo",
    tempoAtividade.map((r) => r.nome),
    tempoAtividade.map((r) => r.minutos_totais),
    { horizontal: true }
  );
  graficoBarra(
    "grafico-peso",
    pesoAtividade.map((r) => r.nome),
    pesoAtividade.map((r) => r.peso_total),
    { horizontal: true }
  );

  renderizarCalendario(document.getElementById("calendario-casa"), calendario, periodoAtual, "casa");
  renderizarAgenda(agenda);
  renderizarListaSimples(
    "lista-tarefas",
    tarefas.map((t) => `<span>${t.nome}</span><span>peso ${t.peso} · ${t.duracao_min} min</span>`),
    "Nenhuma tarefa cadastrada."
  );
}

async function atualizarExercicio() {
  const [ranking, tempoPorTipo, calendario, tipos] = await Promise.all([
    buscarJson(`/api/exercicios/ranking?periodo=${periodoAtual}`),
    buscarJson(`/api/exercicios/tempo-por-tipo?periodo=${periodoAtual}`),
    buscarJson(`/api/exercicios/calendario?periodo=${periodoAtual}`),
    buscarJson("/api/exercicios/tipos"),
  ]);

  graficoBarra("grafico-exercicio-tempo", ranking.map((r) => r.nome), ranking.map((r) => r.minutos_totais));

  const porCheckins = [...ranking].sort((a, b) => b.checkins - a.checkins);
  graficoBarra("grafico-exercicio-checkins", porCheckins.map((r) => r.nome), porCheckins.map((r) => r.checkins));

  graficoBarra(
    "grafico-exercicio-tipo",
    tempoPorTipo.map((r) => r.nome),
    tempoPorTipo.map((r) => r.minutos_totais),
    { horizontal: true }
  );

  renderizarCalendario(document.getElementById("calendario-exercicio"), calendario, periodoAtual, "exercicio");
  renderizarListaSimples(
    "lista-exercicios",
    tipos.map((t) => `<span>${t.nome}</span>`),
    "Nenhum exercício cadastrado."
  );
}

async function atualizarPainelAtivo() {
  if (abaAtual === "casa") {
    await atualizarCasa();
  } else {
    await atualizarExercicio();
  }
}

document.querySelectorAll(".aba-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".aba-btn").forEach((b) => b.classList.remove("ativo"));
    btn.classList.add("ativo");
    abaAtual = btn.dataset.aba;

    document.getElementById("painel-casa").hidden = abaAtual !== "casa";
    document.getElementById("painel-exercicio").hidden = abaAtual !== "exercicio";
    document.getElementById("titulo-painel").textContent =
      abaAtual === "casa" ? "🏠 Tarefas de Casa" : "🏃 Atividade Física";

    atualizarPainelAtivo().then(() => {
      redimensionarGraficosDoPainel(abaAtual === "casa" ? "painel-casa" : "painel-exercicio");
    });
  });
});

document.querySelectorAll("#periodo-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#periodo-toggle button").forEach((b) => b.classList.remove("ativo"));
    btn.classList.add("ativo");
    periodoAtual = btn.dataset.periodo;
    atualizarPainelAtivo();
  });
});

atualizarPainelAtivo();
setInterval(atualizarPainelAtivo, 60_000);
