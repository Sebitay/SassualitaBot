import datetime
from collections import defaultdict


#Gets th poll tittles one for each day of the week
def getPreguntas():
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

    hoy = datetime.date.today()
    dias_hasta_lunes = (7 - hoy.weekday()) % 7
    if dias_hasta_lunes == 0:
        dias_hasta_lunes = 7
    proximo_lunes = hoy + datetime.timedelta(days=dias_hasta_lunes)
    fechas = [proximo_lunes + datetime.timedelta(days=i) for i in range(5)]

    preguntas = []
    for i, dia in enumerate(dias):
        fecha = fechas[i]
        pregunta = f"{dia} {fecha.day}/{fecha.month}"
        preguntas.append(pregunta)
    return preguntas


async def sendPoll(chat_id, pregunta, opciones, context):
    bot = context.bot

    mensaje = await bot.send_poll(
        chat_id=chat_id,
        question=pregunta,
        options=opciones,
        is_anonymous=False,
        allows_multiple_answers=True
    )

    print(f"✅ Enviada encuesta: {pregunta} (ID: {mensaje.poll.id})")
    return mensaje