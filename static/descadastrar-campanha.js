const elStatus = document.getElementById("status");
const elTitulo = document.querySelector("h2");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

async function descadastrar() {
  const token = new URLSearchParams(window.location.search).get("token");
  if (!token) {
    elTitulo.textContent = "Link inválido";
    mostrarStatus("Faltou o token desse link.", true);
    return;
  }

  try {
    const resp = await fetch("/api/descadastrar-campanha", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui descadastrar");

    elTitulo.textContent = "Descadastrado";
    mostrarStatus("Você não vai mais receber esse tipo de e-mail do Radar BJJ.");
  } catch (err) {
    elTitulo.textContent = "Não foi possível descadastrar";
    mostrarStatus(err.message, true);
  }
}

descadastrar();
