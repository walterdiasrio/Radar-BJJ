const elForm = document.getElementById("form-cadastro");
const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

(function preSelecionarPlano() {
  const params = new URLSearchParams(window.location.search);
  const plano = params.get("plano");
  const periodicidade = params.get("periodicidade");
  if (plano !== "atleta" && plano !== "mestre") return;

  const radio = document.querySelector(`input[name="tipo_perfil"][value="${plano}"]`);
  if (radio) radio.checked = true;

  sessionStorage.setItem("radarbjj_checkout_pendente", JSON.stringify({ plano, periodicidade }));

  const nomes = { atleta: "Atleta PRO", mestre: "Mestre PRO" };
  const aviso = document.createElement("p");
  aviso.className = "aviso-alerta";
  aviso.textContent = `Cadastre-se e, depois de confirmar o e-mail e entrar, vamos te levar direto pro checkout do plano ${nomes[plano]}.`;
  elForm.parentNode.insertBefore(aviso, elForm);
})();

function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const nome = document.getElementById("nome").value;
  const email = document.getElementById("email").value;
  const confirmarEmail = document.getElementById("confirmar_email").value;
  const senha = document.getElementById("senha").value;
  const nome_usuario = document.getElementById("nome_usuario").value.trim().toLowerCase();
  const tipo_perfil = document.querySelector('input[name="tipo_perfil"]:checked').value;

  if (email.trim().toLowerCase() !== confirmarEmail.trim().toLowerCase()) {
    mostrarStatus("Os e-mails digitados são diferentes — confere e tenta de novo.", true);
    return;
  }

  mostrarStatus("Cadastrando...");

  try {
    const resp = await fetch("/api/cadastro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome, email, senha, nome_usuario, tipo_perfil }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao cadastrar");

    if (typeof fbq === "function") fbq("track", "Lead");

    elForm.style.display = "none";
    if (dados.email_enviado === false) {
      elStatus.className = "aviso-alerta";
      elStatus.innerHTML = `
        <span style="font-size:1.4rem; line-height:1;">⚠️</span>
        <span>
          <strong>Sua conta foi criada, mas não conseguimos enviar o e-mail de confirmação agora.</strong>
          Tente entrar com <strong>${escapeHtml(dados.email)}</strong> em alguns minutos — a tela de login
          oferece reenviar o link de confirmação.
        </span>
      `;
      return;
    }
    elStatus.className = "aviso-sucesso";
    elStatus.innerHTML = `
      <span style="font-size:1.4rem; line-height:1;">📩</span>
      <span>
        <strong>Falta pouco!</strong>
        Enviamos um link de confirmação para <strong>${escapeHtml(dados.email)}</strong>. Clique nele pra ativar sua conta.
      </span>
    `;
  } catch (err) {
    mostrarStatus(err.message, true);
  }
});

document.getElementById("btn-google").addEventListener("click", () => {
  const elAceite = document.getElementById("aceite_termos");
  if (!elAceite.checked) {
    mostrarStatus("Precisa marcar que concorda com os Termos de Uso antes de continuar.", true);
    elAceite.focus();
    return;
  }
  const tipo_perfil = document.querySelector('input[name="tipo_perfil"]:checked').value;
  window.location.href = `/login/google?tipo_perfil=${tipo_perfil}`;
});
