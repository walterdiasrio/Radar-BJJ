const elForm = document.getElementById("form-redefinir");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

const token = new URLSearchParams(window.location.search).get("token");
if (!token) {
  elForm.style.display = "none";
  mostrarStatus("Link inválido — peça um novo em \"Esqueci minha senha\".", true);
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const senha = document.getElementById("senha").value;
  const senhaConfirma = document.getElementById("senha_confirma").value;

  if (senha !== senhaConfirma) {
    mostrarStatus("As senhas não são iguais.", true);
    return;
  }

  mostrarStatus("Salvando...");

  try {
    const resp = await fetch("/api/redefinir-senha", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, senha }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao redefinir senha");

    mostrarStatus("Senha alterada! Redirecionando pro login...");
    setTimeout(() => { window.location.href = "/login"; }, 1500);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});
