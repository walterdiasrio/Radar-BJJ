const elForm = document.getElementById("form-contato");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

document.addEventListener("sessao-carregada", (ev) => {
  if (ev.detail.logado && ev.detail.email) {
    document.getElementById("c_email").value = ev.detail.email;
  }
});

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: document.getElementById("c_nome").value,
    email: document.getElementById("c_email").value,
    assunto: document.getElementById("c_assunto").value,
    mensagem: document.getElementById("c_mensagem").value,
  };

  mostrarStatus("Enviando...");

  try {
    const resp = await fetch("/api/contato", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const resultado = await resp.json();
    if (!resp.ok) throw new Error(resultado.erro || "erro ao enviar");

    mostrarStatus("Mensagem enviada! Vamos responder assim que possível. 🥋");
    elForm.reset();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});
