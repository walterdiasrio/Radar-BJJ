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

let meusAlunos = [];
let turmasAtuais = [];
let posicoesPorGrupo = {};
const planosExpandidos = new Set();
const planosPorTurma = {};

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

function renderizarPlanoAula(turma) {
  const expandido = planosExpandidos.has(turma.id);
  const planos = planosPorTurma[turma.id] || [];

  return `
    <div style="margin-top:12px; border-top:1px solid var(--borda); padding-top:12px;">
      <button type="button" class="btn-secundario btn-plano-aula" data-id="${turma.id}">
        ${expandido ? "Esconder Plano de Aula" : "Plano de Aula"}
      </button>

      ${expandido ? `
        <div style="margin-top:12px;">
          <form class="form-plano-aula" data-turma-id="${turma.id}">
            <div class="campo" style="max-width:220px;">
              <label>Data da aula</label>
              <input type="date" class="plano_data" required>
            </div>
            ${Object.entries(posicoesPorGrupo).map(([grupo, posicoes]) => `
              <div class="campo">
                <label>${grupo}</label>
                <div class="opcoes-federacao">
                  ${posicoes.map(p => `<label><input type="checkbox" value="${p}"> ${p}</label>`).join("")}
                </div>
              </div>
            `).join("")}
            <button type="submit">Salvar plano de aula</button>
          </form>

          <div style="margin-top:14px;">
            <strong>Aulas registradas${planos.length ? ` (${planos.length})` : ""}:</strong>
            ${planos.length ? "" : " nenhuma ainda."}
            ${planos.map(p => `
              <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
                <div class="cartao-alerta-topo">
                  <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataBr(p.data)}</div>
                  <button type="button" class="btn-remover btn-remover-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Remover</button>
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
                  ${p.posicoes.map(pos => `<span style="background:#eef2f6; border-radius:20px; padding:3px 10px; font-size:0.8rem;">${pos}</span>`).join("")}
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}
    </div>
  `;
}

function renderizarTurmas(turmas) {
  turmasAtuais = turmas;
  if (!turmas.length) {
    elLista.innerHTML = "";
    mostrarStatus("Nenhuma turma criada ainda. Use o formulário acima.");
    return;
  }

  mostrarStatus(`${turmas.length} turma(s).`);
  elLista.innerHTML = turmas.map(t => {
    const disponiveis = opcoesAlunosDisponiveis(t);
    return `
      <div class="cartao-alerta" data-turma-id="${t.id}">
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
              <span style="display:inline-flex; align-items:center; gap:6px; background:#eef2f6; border-radius:20px; padding:4px 6px 4px 12px; font-size:0.85rem;">
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

        ${renderizarPlanoAula(t)}
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
  elLista.querySelectorAll(".btn-plano-aula").forEach(btn => {
    btn.addEventListener("click", () => alternarPlanoAula(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".form-plano-aula").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      salvarPlanoAula(Number(form.dataset.turmaId), form);
    });
  });
  elLista.querySelectorAll(".btn-remover-plano").forEach(btn => {
    btn.addEventListener("click", () => removerPlanoAula(Number(btn.dataset.turmaId), Number(btn.dataset.planoId)));
  });
}

async function carregarTurmas() {
  try {
    await carregarMeusAlunos();
    const resp = await fetchAutenticado("/api/turmas");
    const turmas = await resp.json();
    if (!resp.ok) throw new Error(turmas.erro || "erro ao carregar turmas");
    renderizarTurmas(turmas);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function alternarPlanoAula(turmaId) {
  if (planosExpandidos.has(turmaId)) {
    planosExpandidos.delete(turmaId);
    renderizarTurmas(turmasAtuais);
    return;
  }
  await carregarPosicoes();
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`);
    const planos = await resp.json();
    if (!resp.ok) throw new Error(planos.erro || "não consegui carregar o plano de aula");
    planosPorTurma[turmaId] = planos;
    planosExpandidos.add(turmaId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function salvarPlanoAula(turmaId, form) {
  const data = form.querySelector(".plano_data").value;
  const posicoes = Array.from(form.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
  if (!posicoes.length) {
    mostrarStatus("Selecione pelo menos uma posição.", true);
    return;
  }
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data, posicoes }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar o plano de aula");

    const respLista = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`);
    planosPorTurma[turmaId] = await respLista.json();
    mostrarStatus("Plano de aula salvo!");
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
    planosPorTurma[turmaId] = (planosPorTurma[turmaId] || []).filter(p => p.id !== planoId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
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
  elBtnSalvar.textContent = "Salvar alterações";
  elBtnCancelar.style.display = "";
  elForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicao() {
  elTurmaId.value = "";
  elForm.reset();
  elBtnSalvar.textContent = "Criar turma";
  elBtnCancelar.style.display = "none";
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
    mostrarStatus(editando ? "Turma atualizada!" : "Turma criada!");
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
