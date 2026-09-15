const elForm = document.getElementById("form-escolher-usuario");
const elStatus = document.getElementById("status");
const elNomeUsuario = document.getElementById("nome_usuario");
const elPreviewLinkPerfil = document.getElementById("preview-link-perfil");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

elNomeUsuario.addEventListener("input", () => {
  const valor = elNomeUsuario.value.trim().toLowerCase();
  elPreviewLinkPerfil.textContent = `/atleta/${valor || "joao_silva"}`;
});

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  mostrarStatus("Salvando...");
  try {
    const resp = await fetch("/api/conta/nome-usuario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome_usuario: elNomeUsuario.value }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar");
    window.location.href = "/";
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});
