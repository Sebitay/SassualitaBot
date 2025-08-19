import datetime
import pytz
from collections import defaultdict
from telegram.ext import Application, PollAnswerHandler, ContextTypes
from telegram import Update
from utils import getPreguntas, sendPoll
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === CONFIG ===
TOKEN = os.getenv("TOKEN")
CHAT_IDs=[-4949002055, -4946652588]
ID_RESULTADOS=6196411266
CHAT_TYPES={-4949002055: "masc", -4946652588: "mixto"}


# chat_id -> poll_id -> opcion -> {"votos": int, "usuarios": [user_ids]}
results = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"votos": 0, "usuarios": []})))
# user_id -> nombre completo
users = {}
# poll_id -> {chat_id, day, options}
polls = {}

# =====================
# Función para enviar encuestas
# =====================
async def enviar_encuesta(context: ContextTypes.DEFAULT_TYPE):
    global polls
    polls.clear()

    preguntas = getPreguntas()
    for chat_id in CHAT_IDs:
        for pregunta in preguntas:
            options = ["11:00","12:00","13:00","14:00","15:00"] if pregunta.startswith("Viernes") else \
                      ["11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00","20:00"]

            mensaje = await sendPoll(chat_id, pregunta, options, context)
            polls[mensaje.poll.id] = {
                "chat_id": chat_id,
                "day": pregunta,
                "options": options
            }

# =====================
# Función para manejar votos
# =====================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    nombre = f"{answer.user.first_name} {answer.user.last_name or ''}".strip()
    marked_options = answer.option_ids

    if poll_id not in polls:
        print(f"❌ Poll ID {poll_id} no encontrado en polls.")
        return

    chat_id = polls[poll_id]["chat_id"]
    options = polls[poll_id]["options"]

    users[user_id] = nombre

    for idx, opcion in enumerate(options):
        if idx in marked_options:
            if user_id not in results[chat_id][poll_id][opcion]["usuarios"]:
                results[chat_id][poll_id][opcion]["usuarios"].append(user_id)
                results[chat_id][poll_id][opcion]["votos"] += 1
        else:
            if user_id in results[chat_id][poll_id][opcion]["usuarios"]:
                results[chat_id][poll_id][opcion]["usuarios"].remove(user_id)
                results[chat_id][poll_id][opcion]["votos"] -= 1

    print(f"🗳️ {nombre} votó en {poll_id} ({CHAT_TYPES[chat_id]}) -> opciones {marked_options}")
    print("Resultados parciales:", {k: v for k, v in results[chat_id][poll_id].items()})

# =====================
# Función para enviar resultados populares
# =====================
async def enviar_resultados_populares(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in CHAT_IDs:
        tipo = CHAT_TYPES[chat_id]
        filtered_results = defaultdict(lambda: defaultdict(list))  # day -> hora -> usuarios

        for poll_id, opciones_dict in results[chat_id].items():
            day = polls[poll_id]["day"]
            for hora, data in opciones_dict.items():
                if data["votos"] >= 6:
                    filtered_results[day][hora] = data["usuarios"]

        if not filtered_results:
            await context.bot.send_message(
                chat_id=ID_RESULTADOS,
                text=f"No hay horarios para la proxima semana {tipo}."
            )
            continue

        mensaje = f"Disponibilidad proxima semana {tipo}:\n\n"
        for day, horas_dict in filtered_results.items():
            mensaje += f"{day}\n"
            for hora, uids in horas_dict.items():
                jugadores = [users[uid] for uid in uids]
                mensaje += f"- {hora} | {', '.join(jugadores)}\n"
            mensaje += "\n"

        await context.bot.send_message(chat_id=ID_RESULTADOS, text=mensaje)

# =====================
# Main
# =====================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(PollAnswerHandler(handle_poll_answer))

    job_queue = app.job_queue
    tz_chile = pytz.timezone("America/Santiago")
    hora_encuesta = datetime.time(hour=12, minute=0, tzinfo=tz_chile)
    hora_resultados = datetime.time(hour=18, minute=0, tzinfo=tz_chile)

    job_queue.run_daily(enviar_encuesta, time=hora_encuesta, days=(2,))
    job_queue.run_daily(enviar_resultados_populares, time=hora_resultados, days=(2,3,4,5))

    print("✅ Bot corriendo y escuchando votos en tiempo real...")
    app.run_polling()

if __name__ == "__main__":
    main()
