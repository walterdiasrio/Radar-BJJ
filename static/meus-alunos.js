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
        "Nenhum aluno encontrado ainda. Isso aparece quando outro atleta preenche, em " +
        '"Minha Carreira" → Perfil, a mesma academia que você tem no seu perfil.'
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
        </div>
      </div>
    `).join("");
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarAlunos();
