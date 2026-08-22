const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-alunos");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

async function carregarAlunos() {
  try {
    const resp = await fetchAutenticado("/api/meus-alunos");
    const alunos = await resp.json();
    if (!resp.ok) throw new Error(alunos.erro || "erro ao carregar alunos");

    if (!alunos.length) {
      elLista.innerHTML = "";
      mostrarStatus(
        "Nenhum aluno adicionado ainda. Peça o nome de usuário dele (criado em Minha Carreira → Perfil) e adicione acima."
      );
      return;
    }

    mostrarStatus(`${alunos.length} aluno(s) encontrado(s).`);
    elLista.innerHTML = alunos.map(a => {
      const pendente = a.vinculo_status === "pendente";
      // Pendente porque o ALUNO pediu: a bola é do Mestre (Aceitar/Recusar
      // aqui mesmo). Pendente porque o MESTRE convidou: só falta o aluno
      // aceitar do lado dele — aqui só dá pra cancelar o convite.
      const precisaAceitar = pendente && a.vinculo_criado_por === "aluno";
      return `
      <div class="cartao-alerta">
        <div class="cartao-alerta-topo">
          <div style="display:flex; align-items:center; gap:12px;">
            ${a.foto_url
              ? `<img src="${a.foto_url}" alt="" style="width:44px; height:44px; border-radius:50%; object-fit:cover; flex-shrink:0;">`
              : `<div style="width:44px; height:44px; border-radius:50%; background:var(--campo-bg); border:1px solid var(--borda); display:flex; align-items:center; justify-content:center; font-size:1.3rem; flex-shrink:0;">🥋</div>`}
            <div>
              <h3>${pendente
                ? (a.nome || "(sem nome)")
                : `<a href="/meus-alunos/${a.usuario_id}" style="color: var(--azul); text-decoration: none;">${a.nome || "(sem nome)"}</a>`}</h3>
              <div class="cartao-alerta-federacao">
                ${pendente
                  ? (precisaAceitar ? "Pediu pra ser seu aluno — pendente" : "Convite enviado — aguardando aceite")
                  : `Faixa ${a.faixa}${Number(a.grau) > 0 ? " · " + a.grau + "º grau" : ""}`}
              </div>
            </div>
          </div>
          <div style="display:flex; gap:8px;">
            ${precisaAceitar ? `<button type="button" class="btn-aceitar-vinculo" data-id="${a.usuario_id}">Aceitar</button>` : ""}
            <button type="button" class="btn-remover" data-id="${a.usuario_id}">${pendente ? (precisaAceitar ? "Recusar" : "Cancelar") : "Remover"}</button>
          </div>
        </div>
      </div>
    `;
    }).join("");
    elLista.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => removerAluno(Number(btn.dataset.id)));
    });
    elLista.querySelectorAll(".btn-aceitar-vinculo").forEach(btn => {
      btn.addEventListener("click", () => aceitarAluno(Number(btn.dataset.id)));
    });
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

document.getElementById("form-add-aluno").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const elInput = document.getElementById("aluno_nome_usuario");
  try {
    const resp = await fetchAutenticado("/api/meus-alunos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome_usuario: elInput.value }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui adicionar");
    mostrarStatus("Convite enviado! Fica pendente até o aluno aceitar.");
    elInput.value = "";
    carregarAlunos();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

async function aceitarAluno(alunoId) {
  try {
    const resp = await fetchAutenticado(`/api/meus-alunos/${alunoId}/aceitar`, { method: "POST" });
    if (!resp.ok) throw new Error("não consegui aceitar");
    mostrarStatus("Aluno aceito!");
    carregarAlunos();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerAluno(alunoId) {
  if (!confirm("Remover esse aluno da sua lista?")) return;
  try {
    const resp = await fetchAutenticado(`/api/meus-alunos/${alunoId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    carregarAlunos();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

const elStatusBusca = document.getElementById("status-busca-academia");
const elListaBusca = document.getElementById("lista-busca-academia");

function mostrarStatusBusca(texto, ehErro = false) {
  elStatusBusca.textContent = texto;
  elStatusBusca.className = "status-importacao" + (ehErro ? " erro" : "");
}

document.getElementById("form-buscar-academia").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const academia = document.getElementById("busca_academia").value.trim();
  elListaBusca.innerHTML = "";
  mostrarStatusBusca("Buscando...");
  try {
    const resp = await fetchAutenticado(`/api/meus-alunos/buscar?academia=${encodeURIComponent(academia)}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui buscar");

    if (!dados.atletas.length) {
      mostrarStatusBusca(`Nenhum atleta encontrado com a academia "${dados.academia}".`);
      return;
    }
    mostrarStatusBusca(`${dados.atletas.length} atleta(s) encontrado(s) com a academia "${dados.academia}".`);
    elListaBusca.innerHTML = dados.atletas.map(a => `
      <div class="cartao-alerta">
        <div class="cartao-alerta-topo">
          <div>
            <h3>${a.nome || "(sem nome)"}</h3>
            <div class="cartao-alerta-federacao">Faixa ${a.faixa}${Number(a.grau) > 0 ? " · " + a.grau + "º grau" : ""} · ${a.academia}</div>
          </div>
          <button type="button" class="btn-add-busca" data-id="${a.usuario_id}">Adicionar</button>
        </div>
      </div>
    `).join("");
    elListaBusca.querySelectorAll(".btn-add-busca").forEach(btn => {
      btn.addEventListener("click", () => adicionarAlunoPorId(Number(btn.dataset.id), btn));
    });
  } catch (err) {
    mostrarStatusBusca(`Erro: ${err.message}`, true);
  }
});

async function adicionarAlunoPorId(alunoId, botao) {
  botao.disabled = true;
  try {
    const resp = await fetchAutenticado("/api/meus-alunos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aluno_id: alunoId }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui adicionar");
    botao.closest(".cartao-alerta").remove();
    mostrarStatus("Aluno adicionado!");
    carregarAlunos();
  } catch (err) {
    botao.disabled = false;
    mostrarStatusBusca(`Erro: ${err.message}`, true);
  }
}

const elStatusCompetidores = document.getElementById("status-competidores");
const elListaCompetidores = document.getElementById("lista-competidores");

function mostrarStatusCompetidores(texto, ehErro = false) {
  elStatusCompetidores.textContent = texto;
  elStatusCompetidores.className = "status-importacao" + (ehErro ? " erro" : "");
}

document.getElementById("btn-alunos-competidores").addEventListener("click", async () => {
  elListaCompetidores.innerHTML = "";
  mostrarStatusCompetidores("Buscando em todas as federações... pode demorar um pouco.");
  try {
    const resp = await fetchAutenticado("/api/meus-alunos/competidores");
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui buscar");

    if (!dados.atletas.length) {
      mostrarStatusCompetidores(`Nenhum atleta encontrado com a academia/equipe "${dados.academia}".`);
      return;
    }
    mostrarStatusCompetidores(`${dados.atletas.length} inscrição(ões) encontrada(s) com a academia/equipe "${dados.academia}".`);

    const porFederacao = new Map();
    for (const a of dados.atletas) {
      const chave = a.federacao || "—";
      if (!porFederacao.has(chave)) porFederacao.set(chave, []);
      porFederacao.get(chave).push(a);
    }

    elListaCompetidores.innerHTML = [...porFederacao.entries()].map(([federacao, atletas]) => `
      <div class="card-carreira" style="margin-top: 10px;">
        <h4 style="margin-top:0; color: var(--azul);">${federacao} <span class="contagem">(${atletas.length})</span></h4>
        ${atletas.map(a => `
          <div class="cartao-alerta" style="margin-top:6px; padding:10px 14px;">
            <div class="cartao-alerta-topo">
              <div>
                <strong>${a.nome || ""}</strong>
                <div class="cartao-alerta-federacao">${a.evento || ""}${a.data ? ` · ${a.data}` : ""}</div>
              </div>
            </div>
            <div style="color:#55606b; font-size:0.85rem; margin-top:4px;">
              ${[a.categoria_idade, a.genero, a.faixa, a.peso].filter(Boolean).join(" · ")}
            </div>
          </div>
        `).join("")}
      </div>
    `).join("");
  } catch (err) {
    mostrarStatusCompetidores(`Erro: ${err.message}`, true);
  }
});

carregarAlunos();
