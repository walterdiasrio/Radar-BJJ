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
          <div>
            <h3><a href="/meus-alunos/${a.usuario_id}" style="color: var(--azul); text-decoration: none;">${a.nome || "(sem nome)"}</a></h3>
            <div class="cartao-alerta-federacao">Faixa ${a.faixa}${Number(a.grau) > 0 ? " · " + a.grau + "º grau" : ""}</div>
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

carregarAlunos();
