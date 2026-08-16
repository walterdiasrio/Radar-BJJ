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
    if (!resp.ok) {
      if (dados.email_nao_confirmado) {
        mostrarStatus("Confirme seu e-mail antes de entrar. ", true);
        const btnReenviar = document.createElement("button");
        btnReenviar.type = "button";
        btnReenviar.className = "btn-secundario";
        btnReenviar.textContent = "Reenviar confirmação";
        btnReenviar.style.marginLeft = "8px";
        btnReenviar.addEventListener("click", async () => {
          btnReenviar.disabled = true;
          await fetch("/api/reenviar-confirmacao", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email }),
          });
          mostrarStatus("Se esse e-mail estiver cadastrado, reenviamos o link de confirmação.");
        });
        elStatus.appendChild(btnReenviar);
        return;
      }
      throw new Error(dados.erro || "erro ao entrar");
    }

    window.location.href = "/";
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});
