"""Config do Gunicorn pra produção (Render, ver render.yaml).

Com --preload, o processo mestre importa app.py UMA VEZ antes de dar
fork() pros workers de verdade — e uma limitação de sistema operacional
(não é bug do Gunicorn): threads que já estavam rodando no processo pai
não sobrevivem nos processos-filhos depois do fork(). Ficam "vivas" só no
mestre, que nunca atende request nenhum. Foi assim que o placar público
da Home (competições/competidores) ficou travado em 0/0 pra sempre em
produção — e é bem provável que o verificador de alertas de 30 em 30 min
também nunca rodasse de verdade lá.

post_fork roda DEPOIS do fork, já dentro de cada worker de verdade — daí
as threads sobrevivem. Mas com --workers 2 (e --max-requests reciclando
workers periodicamente), sem cuidado os DOIS workers — e cada substituto
depois de uma reciclagem — tentariam rodar a mesma tarefa periódica ao
mesmo tempo, duplicando e-mail de alerta. Uma trava de arquivo (flock) no
disco persistente (DATA_DIR) resolve: só o worker que conseguir a trava
liga as tarefas; os outros desistem NA HORA — LOCK_NB, nunca fica
esperando/travado esperando a trava liberar. Se esse worker for
reciclado, a trava libera sozinha (o SO libera flock quando o processo
morre) e o próximo worker que nascer (post_fork roda a cada nascimento,
inclusive reciclagem) pega a vaga."""
import fcntl
import os
from pathlib import Path

_LOCK_PATH = Path(os.environ.get("DATA_DIR", Path(__file__).parent)) / ".tarefas_de_fundo.lock"

# Referência global só pra o arquivo não ser fechado pelo garbage collector
# (o que liberaria a trava sozinho) enquanto o worker estiver vivo.
_arquivo_trava = None


def post_fork(server, worker):
    global _arquivo_trava
    _arquivo_trava = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(_arquivo_trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        server.log.info(f"worker {worker.pid}: outro worker já cuida das tarefas de fundo")
        return

    import app
    app.iniciar_tarefas_de_fundo()
    server.log.info(f"worker {worker.pid}: assumiu as tarefas de fundo (alertas, placar público)")
