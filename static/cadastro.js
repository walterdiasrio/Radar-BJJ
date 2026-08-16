const elForm = document.getElementById("form-cadastro");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = document.getElementById("email").value;
  const senha = document.getElementById("senha").value;
  const tipo_perfil = document.querySelector('input[name="tipo_perfil"]:checked').value;

  mostrarStatus("Cadastrando...");

  try {
    const resp = await fetch("/api/cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha, tipo_perfil }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao cadastrar");

    elForm.style.display = "none";
    elStatus.className = "aviso-sucesso";
    elStatus.innerHTML = `
      <span style="font-size:1.4rem; line-height:1;">📩</span>
      <span>
        <strong>Falta pouco!</strong>
        Enviamos um link de confirmação para <strong>${escapeHtml(dados.email)}</strong>. Clique nele pra ativar sua conta.
      </span>
    `;
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});
