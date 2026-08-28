const elForm = document.getElementById("form-login");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

// Muita gente cadastrada nunca confirma o e-mail e fica sem conseguir
// entrar (o login é bloqueado até confirmar) — esse aviso precisa chamar
// mais atenção do que o texto de erro padrão, senão passa despercebido e a
// pessoa desiste sem entender por quê.
function mostrarAvisoEmailNaoConfirmado(email) {
  elStatus.className = "";
  elStatus.innerHTML = "";

  const caixa = document.createElement("div");
  caixa.className = "aviso-alerta";
  caixa.innerHTML = `
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0; margin-top:1px;"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>
    <div>
      <strong>Confirme seu e-mail antes de entrar</strong>
      Enviamos um link de confirmação pra ${email} quando você se cadastrou. Não achou? Confira o spam ou clique abaixo pra reenviar.
    </div>
  `;

  const btnReenviar = document.createElement("button");
  btnReenviar.type = "button";
  btnReenviar.textContent = "Reenviar e-mail de confirmação";
  btnReenviar.style.marginTop = "12px";
  btnReenviar.addEventListener("click", async () => {
    btnReenviar.disabled = true;
    btnReenviar.textContent = "Enviando...";
    await fetch("/api/reenviar-confirmacao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    btnReenviar.textContent = "E-mail reenviado ✓";
  });
  caixa.querySelector("div").appendChild(document.createElement("br"));
  caixa.querySelector("div").appendChild(btnReenviar);

  elStatus.appendChild(caixa);
}

(function mostrarErroGoogle() {
  const erro = new URLSearchParams(window.location.search).get("erro");
  if (erro === "google_nao_configurado") {
    mostrarStatus("Login com Google ainda não está disponível.", true);
  } else if (erro === "google") {
    mostrarStatus("Não conseguimos entrar com o Google. Tente de novo.", true);
  }
})();

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
        mostrarAvisoEmailNaoConfirmado(email);
        return;
      }
      throw new Error(dados.erro || "erro ao entrar");
    }

    const pendente = sessionStorage.getItem("radarbjj_checkout_pendente");
    if (pendente) {
      sessionStorage.removeItem("radarbjj_checkout_pendente");
      try {
        const { plano, periodicidade } = JSON.parse(pendente);
        if (plano && periodicidade) {
          window.location.href = `/assinatura?plano=${plano}&periodicidade=${periodicidade}&auto=1`;
          return;
        }
      } catch (err) {
        // pendente inválido, segue fluxo normal
      }
    }
    window.location.href = "/";
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});
