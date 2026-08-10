const elStatus = document.getElementById("status");
const elLinkLogin = document.getElementById("link-login");
const elTitulo = document.querySelector("h2");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

async function confirmar() {
  const token = new URLSearchParams(window.location.search).get("token");
  if (!token) {
    elTitulo.textContent = "Link inválido";
    mostrarStatus("Faltou o token de confirmação nesse link.", true);
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
  }
}

confirmar();
