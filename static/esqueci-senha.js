const elForm = document.getElementById("form-esqueci");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = document.getElementById("email").value;

  mostrarStatus("Enviando...");

  try {
    const resp = await fetch("/api/esqueci-senha", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!resp.ok) throw new Error("erro ao enviar");

    mostrarStatus("Se esse e-mail estiver cadastrado, você vai receber um link para redefinir a senha em instantes.");
    elForm.reset();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});
