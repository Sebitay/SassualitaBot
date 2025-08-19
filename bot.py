import datetime
import pytz
import csv
from collections import defaultdict
from telegram.ext import Application, PollAnswerHandler, ContextTypes
from telegram.ext import JobQueue
from telegram import Update

# === CONFIG ===
TOKEN = "8260767013:AAE0NOekWpy-GnP0GTcaouJIhBpLOoBHKJw"
ID_MASC = -4934344340  # ID del grupo
ID_MISC = -4778677223
ID_RESULTADOS = 6196411266

# Guardamos resultados en memoria
resultados = defaultdict(lambda: defaultdict(lambda: {"votos": 0, "usuarios": []}))
usuarios = defaultdict(dict)
poll_options = {}  # mapear poll_id -> lista de opciones (horas)

# =====================
# Función para enviar encuestas
# =====================
async def enviar_encuesta(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    hoy = datetime.date.today()
    dias_hasta_lunes = (7 - hoy.weekday()) % 7
    if dias_hasta_lunes == 0:
        dias_hasta_lunes = 7
    proximo_lunes = hoy + datetime.timedelta(days=dias_hasta_lunes)
    fechas = [proximo_lunes + datetime.timedelta(days=i) for i in range(5)]

    with open("latest_polls.txt", "w", encoding="utf-8") as f:
        for i, dia in enumerate(dias):
            fecha = fechas[i]
            pregunta = f"{dia} {fecha.day}/{fecha.month}"
            if dia == "Viernes":
                opciones = ["11:00","12:00","13:00","14:00","15:00"]
            else:
                opciones = ["11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00","20:00"]

            mensaje = await bot.send_poll(
                chat_id=ID_MASC,
                question=pregunta,
                options=opciones,
                is_anonymous=False,
                allows_multiple_answers=True
            )

            f.write(f"{mensaje.poll.id} | {pregunta}\n")
            print(f"✅ Enviada encuesta: {pregunta} (ID: {mensaje.poll.id})")

            # Guardamos opciones para resultados
            poll_options[mensaje.poll.id] = opciones

# =====================
# Función para manejar votos
# =====================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    opciones_votadas = answer.option_ids


    # Solo procesar polls que estén en latest_polls.txt
    try:
        with open("latest_polls.txt", "r", encoding="utf-8") as f:
            latest_polls_ids = {line.split(" | ")[0] for line in f.read().splitlines()}
    except FileNotFoundError:
        latest_polls_ids = set()

    if poll_id not in latest_polls_ids:
        return

    if poll_id not in poll_options:
        return

    # Evitamos duplicados
    if user_id in usuarios[poll_id]:
        prev_opciones = usuarios[poll_id][user_id]
        for op in prev_opciones:
            # restamos 1 del contador de votos
            resultados[poll_id][poll_options[poll_id][op]]["votos"] -= 1
            # removemos al usuario de la lista de nombres
            nombre = answer.user.first_name
            if nombre in resultados[poll_id][poll_options[poll_id][op]]["usuarios"]:
                resultados[poll_id][poll_options[poll_id][op]]["usuarios"].remove(nombre)

    usuarios[poll_id][user_id] = opciones_votadas

    for op in opciones_votadas:
        resultados[poll_id][poll_options[poll_id][op]]["votos"] += 1
        resultados[poll_id][poll_options[poll_id][op]]["usuarios"].append(answer.user.first_name)

    # Guardar en CSV
    with open("resultados.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["poll_id", "opcion", "votos", "usuarios"])
        for pid, opciones_dict in resultados.items():
            for opcion, data in opciones_dict.items():
                usuarios_str = ", ".join(data["usuarios"])
                writer.writerow([pid, opcion, data["votos"], usuarios_str])

    print(f"🗳️ {answer.user.first_name} votó en {poll_id} -> opciones {opciones_votadas}")
    print("Resultados parciales:", dict(resultados[poll_id]))


async def enviar_resultados_populares(context):
    bot = context.bot

    # 1️⃣ Leer latest polls
    poll_dias = {}  # poll_id -> dia
    with open("latest_polls.txt", "r", encoding="utf-8") as f:
        for line in f:
            poll_id, pregunta = line.strip().split("|")
            poll_id = poll_id.strip()
            dia = pregunta.strip().split()[0]  # "Lunes 21/8" -> "Lunes"
            poll_dias[poll_id] = dia

    # 2️⃣ Leer resultados.csv
    resumen = defaultdict(lambda: defaultdict(list))  # dia -> hora -> lista jugadores

    with open("resultados.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            poll_id = row["poll_id"]
            if poll_id not in poll_dias:
                continue  # solo latest polls

            hora = row["opcion"]
            votos = int(row["votos"])
            usuarios = row["usuarios"].split(",")  # separar por coma si hay varios
            if votos >= 6:
                resumen[poll_dias[poll_id]][hora].extend(usuarios)

    # 3️⃣ Armar mensaje en formato solicitado
    if not resumen:
        await bot.send_message(chat_id=ID_RESULTADOS, text="No hay resultados con 6 o más jugadores 😕")
        return

    mensaje = ""
    for dia in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]:
        if dia not in resumen:
            continue
        mensaje += f"{dia}\n"
        for hora, jugadores in resumen[dia].items():
            # quitar duplicados
            jugadores_unicos = sorted(set(jugadores))
            mensaje += f"- {hora} | {', '.join(jugadores_unicos)}\n"
        mensaje += "\n"

    # 4️⃣ Enviar mensaje
    await bot.send_message(chat_id=ID_RESULTADOS, text=mensaje)

# =====================
# Main
# =====================
def main():
    app = Application.builder().token(TOKEN).build()

    # Handler para escuchar votos
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    # JobQueue: enviar encuestas todos los lunes a las 19:36    
    job_queue = app.job_queue

    # JobQueue: enviar encuestas todos los lunes a las 19:36 hora Chile
    tz_chile = pytz.timezone("America/Santiago")
    hora_encuesta = datetime.time(hour=20, minute=5, tzinfo=tz_chile)  # tzinfo aquí

    job_queue.run_once(enviar_resultados_populares, when=datetime.timedelta(seconds=3))
    job_queue.run_daily(enviar_encuesta, time=hora_encuesta, days=(1,))
    print("✅ Bot corriendo y escuchando votos en tiempo real...")
    # Corremos el bot directamente (PTB maneja asyncio internamente)
    app.run_polling()

# =====================
# Ejecutar
# =====================
if __name__ == "__main__":
    main()