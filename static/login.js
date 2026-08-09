const elForm = document.getElementById("form-login");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = document.getElementById("email").value;
  const senha = document.getElementById("senha").value;

  mostrarStatus("Entrando...");

  try {
    const resp = await fetch("/api/entrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao entrar");

    window.location.href = "/";
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});
