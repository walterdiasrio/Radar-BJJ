const elStatus = document.getElementById("status");
const elLinkLogin = document.getElementById("link-login");
const elTitulo = document.querySelector("h2");
const elBlocoReenviar = document.getElementById("bloco-reenviar");
const elReenviarEmail = document.getElementById("reenviar-email");
const elBtnReenviar = document.getElementById("btn-reenviar");
const elStatusReenviar = document.getElementById("status-reenviar");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

elBtnReenviar.addEventListener("click", async () => {
  const email = elReenviarEmail.value.trim();
  if (!email) {
    elStatusReenviar.textContent = "Digite seu e-mail.";
    elStatusReenviar.className = "erro";
    return;
  }
  elBtnReenviar.disabled = true;
  elBtnReenviar.textContent = "Enviando...";
  try {
    await fetch("/api/reenviar-confirmacao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    elStatusReenviar.textContent = "Se esse e-mail tiver uma conta pendente, um novo link foi enviado.";
    elStatusReenviar.className = "";
  } finally {
    elBtnReenviar.disabled = false;
    elBtnReenviar.textContent = "Reenviar link de confirmação";
  }
});

async function confirmar() {
  const token = new URLSearchParams(window.location.search).get("token");
  if (!token) {
    elTitulo.textContent = "Link inválido";
    mostrarStatus("Faltou o token de confirmação nesse link.", true);
    elBlocoReenviar.style.display = "";
    return;
  }

  try {
    const resp = await fetch("/api/confirmar-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui confirmar");

    elTitulo.textContent = "E-mail confirmado!";
    mostrarStatus("Sua conta está ativa. Já pode entrar.");
    elLinkLogin.style.display = "";
  } catch (err) {
    elTitulo.textContent = "Não foi possível confirmar";
    mostrarStatus(err.message, true);
    elBlocoReenviar.style.display = "";
  }
}

confirmar();
