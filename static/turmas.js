const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-turmas");
const elForm = document.getElementById("form-turma");
const elTurmaId = document.getElementById("turma_id");
const elNome = document.getElementById("turma_nome");
const elCategoria = document.getElementById("turma_categoria");
const elInicio = document.getElementById("turma_horario_inicio");
const elFim = document.getElementById("turma_horario_fim");
const elDiasSemana = document.getElementById("turma_dias_semana");
const elBtnSalvar = document.getElementById("btn-salvar-turma");
const elBtnCancelar = document.getElementById("btn-cancelar-edicao");
const elSecaoForm = document.getElementById("secao-form-turma");
const elSecaoLista = document.getElementById("secao-lista-turmas");
const elTituloForm = document.getElementById("titulo-form-turma");

// A página tem dois modos que não se misturam: "criar" (?nova=1 — só o
// formulário, chegou pelo submenu "Nova Turma") e "consultar" (?turma=<id>
// — só aquela turma específica, chegou pelo submenu com o nome dela). Sem
// parâmetro nenhum, mostra a lista completa (sem o formulário).
const parametrosUrl = new URLSearchParams(window.location.search);
const modoNovaTurma = parametrosUrl.get("nova") === "1";
const turmaIdFiltro = parametrosUrl.get("turma");

function aplicarModoPagina() {
  if (modoNovaTurma) {
    elSecaoForm.style.display = "";
    elSecaoLista.style.display = "none";
  } else {
    elSecaoForm.style.display = "none";
    elSecaoLista.style.display = "";
  }
}
aplicarModoPagina();

let meusAlunos = [];
let turmasAtuais = [];
let posicoesPorGrupo = {};
// Qual das 4 abas (futuras/passadas/plano-ia/planner) está aberta em cada
// turma — só uma por vez (turmaId -> nome da aba, ou undefined/null se
// nenhuma estiver aberta). Ver renderizarAbasTurma/alternarAba.
const abaAtivaPorTurma = {};
const futurasPorTurma = {}; // turmaId -> [aula, ...] (data >= hoje, mais próxima primeiro)
const passadasPorTurma = {}; // turmaId -> { mesAno: "YYYY-MM", aulas: [...] } (data < hoje)
const planoEditando = {}; // turmaId -> { id, data, posicoes } da aula em edição, ou undefined
const planoIaEstado = {};
const plannerEstado = {};
const NOMES_DIA_SEMANA = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarHorario(hhmm) {
  return (hhmm || "").slice(0, 5);
}

function formatarDataBr(iso) {
  if (!iso) return "";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

const MESES_PT = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

function rotuloMesAno(iso) {
  if (!iso) return "Data não informada";
  const [ano, mes] = iso.split("-");
  return `${MESES_PT[Number(mes) - 1]} ${ano}`;
}

async function carregarMeusAlunos() {
  try {
    const resp = await fetchAutenticado("/api/meus-alunos");
    meusAlunos = resp.ok ? await resp.json() : [];
  } catch {
    meusAlunos = [];
  }
}

async function carregarPosicoes() {
  if (Object.keys(posicoesPorGrupo).length) return;
  try {
    const resp = await fetchAutenticado("/api/turmas/posicoes");
    posicoesPorGrupo = resp.ok ? await resp.json() : {};
  } catch {
    posicoesPorGrupo = {};
  }
}

function opcoesAlunosDisponiveis(turma) {
  const idsNaTurma = new Set(turma.alunos.map(a => a.usuario_id));
  return meusAlunos.filter(a => !idsNaTurma.has(a.usuario_id));
}

function mesAnoAtual() {
  return new Date().toISOString().slice(0, 7); // "YYYY-MM"
}

// Posições sempre em negrito (pill com texto em negrito) + observação (a
// orientação geral da aula, escrita à mão ou vinda do Plano de Aula IA)
// como texto normal abaixo — mesmo padrão nos cards de Futuras, Passadas
// e nas sugestões do Plano de Aula IA, pra ficar tudo consistente.
function pillsPosicoes(posicoes) {
  return (posicoes || []).map(pos =>
    `<span style="background:#eef2f6; border-radius:20px; padding:3px 10px; font-size:0.8rem; font-weight:700;">${pos}</span>`
  ).join("");
}

function blocoObservacao(observacao) {
  return observacao ? `<div style="color:#55606b; font-size:0.82rem; margin-top:6px;">${observacao}</div>` : "";
}

// Uma aula é "futura" ou "passada" só pela data (>= hoje ou < hoje) — não
// importa se foi escrita à mão ou aceita de uma sugestão do Plano de Aula
// IA, as duas caem na mesma tabela (planos_aula) e migram de lista sozinhas
// conforme o calendário passa. Futuras é onde o Mestre escreve/edita
// conteúdo; Passadas é só arquivo (consulta e remoção, sem editar).
function renderizarAulasFuturas(turma) {
  const aulas = futurasPorTurma[turma.id] || [];
  const edicao = planoEditando[turma.id];

  return `
    <div id="futuras-turma-${turma.id}">
      <form class="form-plano-aula" data-turma-id="${turma.id}" data-editando-id="${edicao ? edicao.id : ""}">
        <div class="campo" style="max-width:220px;">
          <label>Data da aula</label>
          <input type="date" class="plano_data" required value="${edicao ? edicao.data : ""}">
        </div>
        ${Object.entries(posicoesPorGrupo).map(([grupo, posicoes]) => `
          <div class="campo">
            <label>${grupo}</label>
            <div class="opcoes-federacao">
              ${posicoes.map(p => `<label><input type="checkbox" value="${p}" ${edicao && edicao.posicoes.includes(p) ? "checked" : ""}> ${p}</label>`).join("")}
            </div>
          </div>
        `).join("")}
        <div class="campo">
          <label>Observação (opcional)</label>
          <textarea class="plano_observacao" rows="2" maxlength="500"
            placeholder="orientação geral pra essa aula">${edicao ? (edicao.observacao || "") : ""}</textarea>
        </div>
        <button type="submit">${edicao ? "Salvar edição" : "Adicionar aula"}</button>
        ${edicao ? `<button type="button" class="btn-secundario btn-cancelar-edicao-plano" data-turma-id="${turma.id}">Cancelar edição</button>` : ""}
      </form>

      <div style="margin-top:14px;">
        <strong>Aulas futuras${aulas.length ? ` (${aulas.length})` : ""}:</strong>
        ${aulas.length ? "" : " nenhuma ainda — escreva o conteúdo acima, ou aceite uma sugestão do Plano de Aula IA."}
        ${aulas.map(p => `
          <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
            <div class="cartao-alerta-topo">
              <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataDiaSemana(p.data)}</div>
              <div style="display:flex; gap:8px;">
                <button type="button" class="btn-secundario btn-editar-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Editar</button>
                <button type="button" class="btn-remover btn-remover-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Remover</button>
              </div>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
              ${pillsPosicoes(p.posicoes)}
            </div>
            ${blocoObservacao(p.observacao)}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderizarAulasPassadas(turma) {
  const passadas = passadasPorTurma[turma.id] || { mesAno: mesAnoAtual(), aulas: [] };
  const ontem = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  return `
    <div>
      <p style="color:#55606b; font-size:0.85rem; margin-top:0;">
        Esqueceu de registrar uma aula que já aconteceu? Cadastre aqui — ela entra direto no arquivo,
        sem precisar passar por Aulas Futuras.
      </p>
      <form class="form-plano-aula-passada" data-turma-id="${turma.id}">
        <div class="campo" style="max-width:220px;">
          <label>Data da aula</label>
          <input type="date" class="plano_data_passada" required max="${ontem}">
        </div>
        ${Object.entries(posicoesPorGrupo).map(([grupo, posicoes]) => `
          <div class="campo">
            <label>${grupo}</label>
            <div class="opcoes-federacao">
              ${posicoes.map(p => `<label><input type="checkbox" value="${p}"> ${p}</label>`).join("")}
            </div>
          </div>
        `).join("")}
        <div class="campo">
          <label>Observação (opcional)</label>
          <textarea class="plano_observacao" rows="2" maxlength="500" placeholder="orientação geral pra essa aula"></textarea>
        </div>
        <button type="submit">Registrar aula</button>
      </form>

      <div class="campo" style="max-width:220px; margin-top:20px;">
        <label>Consultar mês</label>
        <input type="month" class="passadas_mes_ano" data-turma-id="${turma.id}" value="${passadas.mesAno}">
      </div>

      <div style="margin-top:14px;">
        <strong>Aulas dadas em ${rotuloMesAno(passadas.mesAno)}${passadas.aulas.length ? ` (${passadas.aulas.length})` : ""}:</strong>
        ${passadas.aulas.length ? "" : " nenhuma aula registrada nesse mês."}
        ${passadas.aulas.map(p => `
          <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
            <div class="cartao-alerta-topo">
              <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataBr(p.data)}</div>
              <button type="button" class="btn-remover btn-remover-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Remover</button>
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
              ${pillsPosicoes(p.posicoes)}
            </div>
            ${blocoObservacao(p.observacao)}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderizarPlanoIA(turma) {
  const estado = planoIaEstado[turma.id] || {};
  const grupos = Object.keys(posicoesPorGrupo);

  return `
    <div>
      <p style="color:#55606b; font-size:0.85rem; margin-top:0;">
        A Inteligência Artificial analisa as aulas passadas de sua turma, e com base nos objetivos
        traçados e no foco desejado, sugere as próximas aulas. Aceite as que quiser — elas vão
        direto pra Aulas Futuras, prontas pra editar se precisar.
      </p>
      <div class="campo" style="max-width:420px;">
        <label>Foco (opcional)</label>
        <select class="plano_ia_foco" data-turma-id="${turma.id}">
          <option value="">Sem foco específico</option>
          ${grupos.map(g => `<option value="${g}" ${estado.foco === g ? "selected" : ""}>${g}</option>`).join("")}
        </select>
      </div>
      <div class="campo" style="max-width:420px;">
        <label>O que você quer nesse plano? (opcional, máx. 200 caracteres)</label>
        <textarea class="plano_ia_resumo" data-turma-id="${turma.id}" rows="3"
          placeholder="ex: turma está fraca na defesa, quero reforçar escapes e fundamentos essa semana"
          maxlength="200">${estado.resumo || ""}</textarea>
      </div>
      <button type="button" class="btn-gerar-plano-ia" data-id="${turma.id}" ${estado.carregando ? "disabled" : ""}>
        ${estado.carregando ? "Gerando..." : "Gerar sugestão com IA"}
      </button>
      <div style="color:#55606b; font-size:0.78rem; margin-top:4px;">Limite: 2 gerações com IA por dia, por turma.</div>

      ${estado.erro ? `<div class="status-importacao erro" style="margin-top:8px;">${estado.erro}</div>` : ""}

      ${estado.resultado ? `
        <div style="margin-top:14px;">
          ${estado.resultado.ia === false ? `
            <div class="status-importacao" style="margin-bottom:8px;">
              ${estado.resultado.aviso || "IA indisponível no momento — mostrando sugestão automática (sem IA)."}
            </div>
          ` : ""}
          ${estado.resultado.aulas.map((a, i) => `
            <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
              <div class="cartao-alerta-topo">
                <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataBr(a.data)}</div>
                ${a.salvo
                  ? `<span style="color:#1a7d3a; font-size:0.85rem; font-weight:600;">Salvo ✓</span>`
                  : `<button type="button" class="btn-salvar-sugestao-ia" data-turma-id="${turma.id}" data-indice="${i}">Aceitar</button>`}
              </div>
              <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
                ${pillsPosicoes(a.posicoes)}
              </div>
              ${blocoObservacao(a.observacao)}
            </div>
          `).join("")}
          ${estado.resultado.aulas.some(a => !a.salvo) ? `
            <button type="button" class="btn-salvar-tudo-ia" data-id="${turma.id}" style="margin-top:10px;">Aceitar tudo</button>
          ` : ""}
        </div>
      ` : ""}
    </div>
  `;
}

function proximoMesAno() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 7); // "YYYY-MM"
}

function rotuloBotaoMes(mesAno, mesAtual) {
  return mesAno === mesAtual ? "Planner do mês atual" : "Planner do mês seguinte";
}

function formatarDataDiaSemana(iso) {
  const data = new Date(`${iso}T00:00:00`);
  return `${NOMES_DIA_SEMANA[data.getDay()]}, ${formatarDataBr(iso)}`;
}

// Calendário do mês em PDF com as aulas já cadastradas dessa turma — pro
// mês em andamento, mistura Aulas Passadas (histórico) e Aulas Futuras
// desse mês; pro mês seguinte, é só Aulas Futuras (ver
// turmas.montar_planner_mensal). Não gera nem edita conteúdo de aula —
// só organiza no calendário o que já está cadastrado. Os 3 campos abaixo
// (Objetivo/Competições Previstas/Observações) são opcionais e valem só
// pra esse PDF — não ficam salvos, é só preencher e baixar/enviar.
function renderizarPlanner(turma) {
  const estado = plannerEstado[turma.id] || { mesAno: proximoMesAno() };

  return `
    <div>
      <p style="color:#55606b; font-size:0.85rem; margin-top:0;">
        Baixa (ou manda por e-mail) o calendário do mês em PDF, com as aulas já cadastradas em Aulas
        Futuras e Aulas Passadas — não cria nem edita conteúdo de aula aqui.
      </p>

      <div style="display:flex; flex-wrap:wrap; gap:8px;">
        ${[mesAnoAtual(), proximoMesAno()].map(mesAno => `
          <button type="button" class="btn-secundario btn-escolher-mes-planner ${estado.mesAno === mesAno ? "ativo" : ""}"
            data-turma-id="${turma.id}" data-mes-ano="${mesAno}">
            ${rotuloBotaoMes(mesAno, mesAnoAtual())} (${rotuloMesAno(mesAno)})
          </button>
        `).join("")}
      </div>

      <div class="campo" style="max-width:640px; margin-top:16px;">
        <label>Objetivo (opcional)</label>
        <textarea class="planner_objetivo" data-turma-id="${turma.id}" rows="2"
          maxlength="2000" placeholder="ex: preparar 3 atletas pro campeonato estadual">${estado.objetivo || ""}</textarea>
      </div>
      <div class="campo" style="max-width:640px;">
        <label>Competições previstas (opcional)</label>
        <textarea class="planner_competicoes" data-turma-id="${turma.id}" rows="2"
          maxlength="2000" placeholder="ex: Copa Estadual (dia 20), Aberto da Cidade (dia 27)">${estado.competicoes || ""}</textarea>
      </div>
      <div class="campo" style="max-width:640px;">
        <label>Observações (opcional)</label>
        <textarea class="planner_observacoes_gerais" data-turma-id="${turma.id}" rows="2"
          maxlength="2000" placeholder="observações livres sobre o mês">${estado.observacoes || ""}</textarea>
      </div>

      <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
        <button type="button" class="btn-baixar-planner" data-id="${turma.id}" ${estado.baixando ? "disabled" : ""}>
          ${estado.baixando ? "Gerando PDF..." : "Baixar PDF"}
        </button>
        <button type="button" class="btn-secundario btn-emailar-planner" data-id="${turma.id}" ${estado.enviando ? "disabled" : ""}>
          ${estado.enviando ? "Enviando..." : "Enviar por e-mail"}
        </button>
      </div>

      ${estado.erro ? `<div class="status-importacao erro" style="margin-top:8px;">${estado.erro}</div>` : ""}
      ${estado.mensagem ? `<div class="status-importacao" style="margin-top:8px;">${estado.mensagem}</div>` : ""}
    </div>
  `;
}

// Tabs unificadas (só uma aba aberta por vez) que substituem os quatro
// botões independentes que existiam antes — eram confusos porque cada um
// abria/fechava sozinho, dava pra ter vários abertos ao mesmo tempo, e não
// havia nenhum sinal visual de que eram "visões alternativas da mesma
// turma" em vez de recursos separados.
const ABAS_TURMA = [
  { chave: "futuras", rotulo: "Aulas Futuras" },
  { chave: "passadas", rotulo: "Aulas Passadas" },
  { chave: "plano-ia", rotulo: "Plano de Aula IA" },
  { chave: "planner", rotulo: "Planner de Aulas" },
];

function renderizarAbasTurma(turma) {
  const aba = abaAtivaPorTurma[turma.id];
  const conteudo = {
    "futuras": renderizarAulasFuturas,
    "passadas": renderizarAulasPassadas,
    "plano-ia": renderizarPlanoIA,
    "planner": renderizarPlanner,
  }[aba];

  return `
    <div style="margin-top:16px; border-top:1px solid var(--borda); padding-top:12px;">
      <div class="tabs-carreira">
        ${ABAS_TURMA.map(a => `
          <button type="button" class="tab-carreira-btn btn-aba-turma ${aba === a.chave ? "ativo" : ""}"
            data-id="${turma.id}" data-aba="${a.chave}">${a.rotulo}</button>
        `).join("")}
      </div>
      ${conteudo ? `<div class="tab-carreira-content ativo">${conteudo(turma)}</div>` : ""}
    </div>
  `;
}

function renderizarTurmas(turmas) {
  turmasAtuais = turmas;

  // Modo "consultar uma turma" (?turma=<id>, veio do submenu): mostra só
  // ela, não a lista inteira — não mistura com as outras.
  const turmasParaExibir = turmaIdFiltro
    ? turmas.filter(t => String(t.id) === String(turmaIdFiltro))
    : turmas;

  if (!turmas.length) {
    elLista.innerHTML = "";
    mostrarStatus("Nenhuma turma criada ainda. Clique em \"+ Nova turma\".");
    return;
  }
  if (turmaIdFiltro && !turmasParaExibir.length) {
    elLista.innerHTML = "";
    mostrarStatus("Essa turma não existe mais.", true);
    return;
  }

  mostrarStatus(turmaIdFiltro ? "" : `${turmas.length} turma(s).`);
  const idParaDestacar = turmaIdFiltro;
  elLista.innerHTML = turmasParaExibir.map(t => {
    const disponiveis = opcoesAlunosDisponiveis(t);
    return `
      <div class="cartao-alerta" data-turma-id="${t.id}" id="turma-${t.id}" style="${idParaDestacar == t.id ? 'outline: 2px solid var(--azul-claro);' : ''}">
        <div class="cartao-alerta-topo">
          <div>
            <h3>${t.nome ? t.nome + " — " : ""}${t.categoria}</h3>
            <div class="cartao-alerta-federacao">${formatarHorario(t.horario_inicio)} às ${formatarHorario(t.horario_fim)}</div>
            ${t.dias_semana.length ? `<div class="cartao-alerta-filtros" style="margin-top:2px;">${t.dias_semana.join(", ")}</div>` : ""}
          </div>
          <div style="display:flex; gap:8px;">
            <button type="button" class="btn-secundario btn-editar-turma" data-id="${t.id}">Editar</button>
            <button type="button" class="btn-remover btn-remover-turma" data-id="${t.id}">Remover</button>
          </div>
        </div>

        <div class="cartao-alerta-filtros">
          <strong>Alunos${t.alunos.length ? ` (${t.alunos.length})` : ""}:</strong>
          ${t.alunos.length ? "" : " nenhum ainda."}
        </div>
        ${t.alunos.length ? `
          <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
            ${t.alunos.map(a => `
              <span style="display:inline-flex; align-items:center; gap:6px; background:#eef2f6; border-radius:20px; padding:4px 6px 4px 6px; font-size:0.85rem;">
                ${a.foto_url
                  ? `<img src="${a.foto_url}" alt="" style="width:22px; height:22px; border-radius:50%; object-fit:cover;">`
                  : `<span style="width:22px; height:22px; border-radius:50%; background:#dde5ec; display:inline-flex; align-items:center; justify-content:center; font-size:0.85rem;">🥋</span>`}
                <a href="/meus-alunos/${a.usuario_id}" style="color: var(--azul); text-decoration: none;">${a.nome || "(sem nome)"}</a>
                <button type="button" class="btn-remover-aluno-turma" data-turma-id="${t.id}" data-aluno-id="${a.usuario_id}"
                  style="border:none; background:transparent; color:#b3261e; cursor:pointer; font-size:1rem; line-height:1; padding:2px 4px;">×</button>
              </span>
            `).join("")}
          </div>
        ` : ""}

        <form class="form-add-aluno-turma" data-turma-id="${t.id}" style="display:flex; gap:8px; align-items:flex-end; margin-top:12px;">
          <div class="campo" style="flex:1; margin-bottom:0;">
            <label>Adicionar aluno</label>
            <select ${disponiveis.length ? "" : "disabled"}>
              ${disponiveis.length
                ? disponiveis.map(a => `<option value="${a.usuario_id}">${a.nome || "(sem nome)"}</option>`).join("")
                : `<option value="">${meusAlunos.length ? "Todos os seus alunos já estão nessa turma" : "Você ainda não tem alunos em Meus Alunos"}</option>`}
            </select>
          </div>
          <button type="submit" ${disponiveis.length ? "" : "disabled"}>Adicionar</button>
        </form>

        ${renderizarAbasTurma(t)}
      </div>
    `;
  }).join("");

  elLista.querySelectorAll(".btn-editar-turma").forEach(btn => {
    btn.addEventListener("click", () => iniciarEdicao(Number(btn.dataset.id), turmas));
  });
  elLista.querySelectorAll(".btn-remover-turma").forEach(btn => {
    btn.addEventListener("click", () => removerTurma(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-remover-aluno-turma").forEach(btn => {
    btn.addEventListener("click", () => removerAlunoDaTurma(Number(btn.dataset.turmaId), Number(btn.dataset.alunoId)));
  });
  elLista.querySelectorAll(".form-add-aluno-turma").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const select = form.querySelector("select");
      if (!select.value) return;
      adicionarAlunoNaTurma(Number(form.dataset.turmaId), Number(select.value));
    });
  });
  elLista.querySelectorAll(".btn-aba-turma").forEach(btn => {
    btn.addEventListener("click", () => alternarAba(Number(btn.dataset.id), btn.dataset.aba));
  });
  elLista.querySelectorAll(".form-plano-aula").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      salvarPlanoAula(Number(form.dataset.turmaId), form);
    });
  });
  elLista.querySelectorAll(".form-plano-aula-passada").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      salvarPlanoAulaPassada(Number(form.dataset.turmaId), form);
    });
  });
  elLista.querySelectorAll(".btn-remover-plano").forEach(btn => {
    btn.addEventListener("click", () => removerPlanoAula(Number(btn.dataset.turmaId), Number(btn.dataset.planoId)));
  });
  elLista.querySelectorAll(".btn-editar-plano").forEach(btn => {
    btn.addEventListener("click", () => editarPlano(Number(btn.dataset.turmaId), Number(btn.dataset.planoId)));
  });
  elLista.querySelectorAll(".btn-cancelar-edicao-plano").forEach(btn => {
    btn.addEventListener("click", () => cancelarEdicaoPlano(Number(btn.dataset.turmaId)));
  });
  elLista.querySelectorAll(".passadas_mes_ano").forEach(input => {
    input.addEventListener("change", () => {
      mudarMesPassadas(Number(input.dataset.turmaId), input.value);
    });
  });
  elLista.querySelectorAll(".plano_ia_foco").forEach(select => {
    select.addEventListener("change", () => {
      const turmaId = Number(select.dataset.turmaId);
      planoIaEstado[turmaId] = { ...(planoIaEstado[turmaId] || {}), foco: select.value };
    });
  });
  elLista.querySelectorAll(".plano_ia_resumo").forEach(textarea => {
    textarea.addEventListener("input", () => {
      const turmaId = Number(textarea.dataset.turmaId);
      planoIaEstado[turmaId] = { ...(planoIaEstado[turmaId] || {}), resumo: textarea.value };
    });
  });
  elLista.querySelectorAll(".btn-gerar-plano-ia").forEach(btn => {
    btn.addEventListener("click", () => gerarPlanoIA(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-salvar-sugestao-ia").forEach(btn => {
    btn.addEventListener("click", () => salvarSugestaoIA(Number(btn.dataset.turmaId), Number(btn.dataset.indice)));
  });
  elLista.querySelectorAll(".btn-salvar-tudo-ia").forEach(btn => {
    btn.addEventListener("click", () => salvarTudoIA(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-escolher-mes-planner").forEach(btn => {
    btn.addEventListener("click", () => {
      const turmaId = Number(btn.dataset.turmaId);
      atualizarEstadoPlanner(turmaId, { mesAno: btn.dataset.mesAno, erro: null, mensagem: null });
      renderizarTurmas(turmasAtuais);
    });
  });
  elLista.querySelectorAll(".planner_objetivo").forEach(textarea => {
    textarea.addEventListener("input", () => {
      atualizarEstadoPlanner(Number(textarea.dataset.turmaId), { objetivo: textarea.value });
    });
  });
  elLista.querySelectorAll(".planner_competicoes").forEach(textarea => {
    textarea.addEventListener("input", () => {
      atualizarEstadoPlanner(Number(textarea.dataset.turmaId), { competicoes: textarea.value });
    });
  });
  elLista.querySelectorAll(".planner_observacoes_gerais").forEach(textarea => {
    textarea.addEventListener("input", () => {
      atualizarEstadoPlanner(Number(textarea.dataset.turmaId), { observacoes: textarea.value });
    });
  });
  elLista.querySelectorAll(".btn-baixar-planner").forEach(btn => {
    btn.addEventListener("click", () => baixarPlannerPdf(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-emailar-planner").forEach(btn => {
    btn.addEventListener("click", () => emailarPlanner(Number(btn.dataset.id)));
  });
}

async function carregarTurmas() {
  try {
    await carregarMeusAlunos();
    const resp = await fetchAutenticado("/api/turmas");
    const turmas = await resp.json();
    if (!resp.ok) throw new Error(turmas.erro || "erro ao carregar turmas");
    renderizarTurmas(turmas);
    rolarAteTurmaDestacada();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

function rolarAteTurmaDestacada() {
  const id = new URLSearchParams(window.location.search).get("turma");
  if (!id) return;
  const el = document.getElementById(`turma-${id}`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function carregarFuturas(turmaId) {
  const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/futuras`);
  const aulas = await resp.json();
  if (!resp.ok) throw new Error(aulas.erro || "não consegui carregar as aulas futuras");
  futurasPorTurma[turmaId] = aulas;
}

async function carregarPassadas(turmaId, mesAno) {
  const [ano, mes] = mesAno.split("-").map(Number);
  const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/passadas?mes=${mes}&ano=${ano}`);
  const aulas = await resp.json();
  if (!resp.ok) throw new Error(aulas.erro || "não consegui carregar as aulas passadas");
  passadasPorTurma[turmaId] = { mesAno, aulas };
}

// Recarrega Futuras/Passadas só se a aba correspondente estiver aberta
// (senão limpa o cache pra recarregar na próxima vez que abrir) — chamado
// depois de criar/editar/remover uma aula, ou aceitar uma sugestão do
// Plano de Aula IA, já que qualquer uma dessas ações pode mudar as duas
// listas (uma aula editada pode até trocar de mês, embora não de lista).
async function atualizarListasAulas(turmaId) {
  const aba = abaAtivaPorTurma[turmaId];
  const tarefas = [];
  if (aba === "futuras") {
    tarefas.push(carregarFuturas(turmaId));
  } else {
    delete futurasPorTurma[turmaId];
  }
  if (aba === "passadas") {
    const mesAno = (passadasPorTurma[turmaId] || {}).mesAno || mesAnoAtual();
    tarefas.push(carregarPassadas(turmaId, mesAno));
  } else {
    delete passadasPorTurma[turmaId];
  }
  await Promise.all(tarefas);
}

// Alterna qual das 4 abas está aberta numa turma — clicar na aba já
// aberta fecha (volta pro card compacto); clicar em outra troca, carregando
// os dados dela primeiro se ainda não tiver (o Planner só busca o que já
// foi gerado antes na PRIMEIRA vez que abre, pra não perder edições locais
// não salvas ao trocar de aba e voltar).
async function alternarAba(turmaId, aba) {
  if (abaAtivaPorTurma[turmaId] === aba) {
    delete abaAtivaPorTurma[turmaId];
    renderizarTurmas(turmasAtuais);
    return;
  }
  try {
    if (aba === "futuras") {
      await carregarPosicoes();
      await carregarFuturas(turmaId);
    } else if (aba === "passadas") {
      await carregarPosicoes();
      const mesAno = (passadasPorTurma[turmaId] || {}).mesAno || mesAnoAtual();
      await carregarPassadas(turmaId, mesAno);
    } else if (aba === "plano-ia") {
      await carregarPosicoes();
    } else if (aba === "planner" && !plannerEstado[turmaId]) {
      plannerEstado[turmaId] = { mesAno: proximoMesAno() };
    }
    abaAtivaPorTurma[turmaId] = aba;
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function mudarMesPassadas(turmaId, mesAno) {
  try {
    await carregarPassadas(turmaId, mesAno);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

// Registra direto no arquivo uma aula que já aconteceu (mesmo endpoint de
// Aulas Futuras — o que decide se ela é "futura" ou "passada" é só a
// data). Depois de salvar, já muda o mês consultado pro mês da aula
// registrada, pra confirmar na hora que entrou certo.
async function salvarPlanoAulaPassada(turmaId, form) {
  const data = form.querySelector(".plano_data_passada").value;
  const posicoes = Array.from(form.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
  const observacao = form.querySelector(".plano_observacao").value;
  if (!posicoes.length) {
    mostrarStatus("Selecione pelo menos uma posição.", true);
    return;
  }
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data, posicoes, observacao }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui registrar a aula");

    await carregarPassadas(turmaId, data.slice(0, 7));
    mostrarStatus("Aula registrada!");
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

function editarPlano(turmaId, planoId) {
  const aula = (futurasPorTurma[turmaId] || []).find(p => p.id === planoId);
  if (!aula) return;
  planoEditando[turmaId] = { id: aula.id, data: aula.data, posicoes: aula.posicoes, observacao: aula.observacao };
  renderizarTurmas(turmasAtuais);
}

function cancelarEdicaoPlano(turmaId) {
  delete planoEditando[turmaId];
  renderizarTurmas(turmasAtuais);
}

async function salvarPlanoAula(turmaId, form) {
  const data = form.querySelector(".plano_data").value;
  const posicoes = Array.from(form.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
  const observacao = form.querySelector(".plano_observacao").value;
  const editandoId = form.dataset.editandoId;
  if (!posicoes.length) {
    mostrarStatus("Selecione pelo menos uma posição.", true);
    return;
  }
  try {
    const resp = await fetchAutenticado(
      editandoId ? `/api/turmas/${turmaId}/planos-aula/${editandoId}` : `/api/turmas/${turmaId}/planos-aula`,
      {
        method: editandoId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, posicoes, observacao }),
      },
    );
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar a aula");

    delete planoEditando[turmaId];
    await atualizarListasAulas(turmaId);
    mostrarStatus(editandoId ? "Aula atualizada!" : "Aula adicionada!");
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerPlanoAula(turmaId, planoId) {
  if (!confirm("Remover esse registro de aula?")) return;
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/${planoId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    await atualizarListasAulas(turmaId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function gerarPlanoIA(turmaId) {
  const estado = planoIaEstado[turmaId] || {};
  planoIaEstado[turmaId] = { ...estado, carregando: true, erro: null };
  renderizarTurmas(turmasAtuais);

  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/plano-ia`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ foco: estado.foco || "", resumo: estado.resumo || "" }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui gerar a sugestão");
    planoIaEstado[turmaId] = { ...estado, carregando: false, erro: null, resultado: dados };
  } catch (err) {
    planoIaEstado[turmaId] = { ...estado, carregando: false, erro: err.message };
  }
  renderizarTurmas(turmasAtuais);
}

async function salvarSugestaoIA(turmaId, indice) {
  const estado = planoIaEstado[turmaId];
  if (!estado || !estado.resultado) return;
  const aula = estado.resultado.aulas[indice];
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: aula.data, posicoes: aula.posicoes, observacao: aula.observacao || "" }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar");
    aula.salvo = true;
    await atualizarListasAulas(turmaId);
    mostrarStatus("Aula aceita — foi pra Aulas Futuras!");
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function salvarTudoIA(turmaId) {
  const estado = planoIaEstado[turmaId];
  if (!estado || !estado.resultado) return;
  for (let i = 0; i < estado.resultado.aulas.length; i++) {
    if (!estado.resultado.aulas[i].salvo) await salvarSugestaoIA(turmaId, i);
  }
}

function atualizarEstadoPlanner(turmaId, patch) {
  plannerEstado[turmaId] = { ...(plannerEstado[turmaId] || { mesAno: proximoMesAno() }), ...patch };
}

async function baixarPlannerPdf(turmaId) {
  const estado = plannerEstado[turmaId] || { mesAno: proximoMesAno() };
  const [ano, mes] = estado.mesAno.split("-");
  atualizarEstadoPlanner(turmaId, { baixando: true, erro: null, mensagem: null });
  renderizarTurmas(turmasAtuais);

  try {
    const params = new URLSearchParams({
      mes: String(Number(mes)), ano,
      objetivo: estado.objetivo || "", competicoes: estado.competicoes || "", observacoes: estado.observacoes || "",
    });
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner/pdf?${params}`);
    if (!resp.ok) {
      const dados = await resp.json().catch(() => ({}));
      throw new Error(dados.erro || "não consegui gerar o PDF");
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `planner-${mes}-${ano}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    atualizarEstadoPlanner(turmaId, { baixando: false });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { baixando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

async function emailarPlanner(turmaId) {
  const estado = plannerEstado[turmaId] || { mesAno: proximoMesAno() };
  const [ano, mes] = estado.mesAno.split("-");
  atualizarEstadoPlanner(turmaId, { enviando: true, erro: null, mensagem: null });
  renderizarTurmas(turmasAtuais);

  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner/email?mes=${Number(mes)}&ano=${ano}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objetivo: estado.objetivo || "", competicoes: estado.competicoes || "", observacoes: estado.observacoes || "",
      }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui enviar o e-mail");
    atualizarEstadoPlanner(turmaId, { enviando: false, mensagem: `Planner enviado para ${dados.email}!` });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { enviando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

function iniciarEdicao(turmaId, turmas) {
  const turma = turmas.find(t => t.id === turmaId);
  if (!turma) return;
  elTurmaId.value = turma.id;
  elNome.value = turma.nome || "";
  elCategoria.value = turma.categoria;
  elInicio.value = formatarHorario(turma.horario_inicio);
  elFim.value = formatarHorario(turma.horario_fim);
  elDiasSemana.querySelectorAll('input[type="checkbox"]').forEach(c => {
    c.checked = turma.dias_semana.includes(c.value);
  });
  elTituloForm.textContent = "Editar turma";
  elBtnSalvar.textContent = "Salvar alterações";
  elBtnCancelar.style.display = "";
  // Editar abre o formulário mesmo estando no modo "consultar" — as duas
  // funcionalidades continuam sem se misturar na tela (a lista some
  // enquanto o formulário de edição está aberto).
  elSecaoForm.style.display = "";
  elSecaoLista.style.display = "none";
  elForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicao() {
  elTurmaId.value = "";
  elForm.reset();
  elTituloForm.textContent = "Nova turma";
  elBtnSalvar.textContent = "Criar turma";
  elBtnCancelar.style.display = "none";
  if (!modoNovaTurma) aplicarModoPagina();
}

elBtnCancelar.addEventListener("click", cancelarEdicao);

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: elNome.value,
    categoria: elCategoria.value,
    horario_inicio: elInicio.value,
    horario_fim: elFim.value,
    dias_semana: Array.from(elDiasSemana.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value),
  };
  const editando = elTurmaId.value;
  try {
    const resp = await fetchAutenticado(editando ? `/api/turmas/${editando}` : "/api/turmas", {
      method: editando ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const dadosResp = await resp.json();
    if (!resp.ok) throw new Error(dadosResp.erro || "não consegui salvar a turma");
    if (!editando) {
      // Turma nova: manda direto pra tela de consulta dela, já separada
      // da criação (em vez de ficar preso na tela de "Nova turma").
      window.location.href = `/turmas?turma=${dadosResp.id}`;
      return;
    }
    mostrarStatus("Turma atualizada!");
    cancelarEdicao();
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

async function removerTurma(turmaId) {
  if (!confirm("Remover essa turma? Os alunos continuam em Meus Alunos.")) return;
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    if (elTurmaId.value === String(turmaId)) cancelarEdicao();
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function adicionarAlunoNaTurma(turmaId, alunoId) {
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/alunos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aluno_id: alunoId }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui adicionar o aluno");
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerAlunoDaTurma(turmaId, alunoId) {
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/alunos/${alunoId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover o aluno");
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarTurmas();
