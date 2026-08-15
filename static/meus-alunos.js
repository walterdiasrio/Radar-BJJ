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
    elLista.innerHTML = alunos.map(a => `
      <div class="cartao-alerta">
        <div class="cartao-alerta-topo">
          <div style="display:flex; align-items:center; gap:12px;">
            ${a.foto_url
              ? `<img src="${a.foto_url}" alt="" style="width:44px; height:44px; border-radius:50%; object-fit:cover; flex-shrink:0;">`
              : `<div style="width:44px; height:44px; border-radius:50%; background:var(--campo-bg); border:1px solid var(--borda); display:flex; align-items:center; justify-content:center; font-size:1.3rem; flex-shrink:0;">🥋</div>`}
            <div>
              <h3><a href="/meus-alunos/${a.usuario_id}" style="color: var(--azul); text-decoration: none;">${a.nome || "(sem nome)"}</a></h3>
              <div class="cartao-alerta-federacao">Faixa ${a.faixa}${Number(a.grau) > 0 ? " · " + a.grau + "º grau" : ""}</div>
            </div>
          </div>
          <button type="button" class="btn-remover" data-id="${a.usuario_id}">Remover</button>
        </div>
      </div>
    `).join("");
    elLista.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => removerAluno(Number(btn.dataset.id)));
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
    mostrarStatus("Aluno adicionado!");
    elInput.value = "";
    carregarAlunos();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

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

carregarAlunos();
