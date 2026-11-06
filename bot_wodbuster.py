from datetime import datetime, timedelta
import os
import requests

# Credenciales y configuración
IDU = os.environ.get("WODBUSTER_IDU", "bf69cdef38d34ae2a1e783ca2fbfd9e9")
BASE_URL = "https://vitalitywellness.wodbuster.com/athlete/handlers"
CONNECTION_ID = "xFATStrQAEREx1Nvyfi-Pw"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def enviar_telegram(mensaje):
  """Envía una notificación a tu chat de Telegram."""
  if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print(f"[Telegram Desactivado] {mensaje}")
    return

  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {
      "chat_id": TELEGRAM_CHAT_ID,
      "text": mensaje,
      "parse_mode": "Markdown",
  }
  try:
    requests.post(url, json=payload)
  except Exception as e:
    print(f"Error al enviar mensaje a Telegram: {e}")


def obtener_proximo_lunes_y_miercoles():
  hoy = datetime.now()
  dias_hasta_lunes = (0 - hoy.weekday()) % 7
  if dias_hasta_lunes == 0:
    dias_hasta_lunes = 7

  proximo_lunes = hoy + timedelta(days=dias_hasta_lunes)
  proximo_miercoles = proximo_lunes + timedelta(days=2)

  proximo_lunes = proximo_lunes.replace(
      hour=0, minute=0, second=0, microsecond=0
  )
  proximo_miercoles = proximo_miercoles.replace(
      hour=0, minute=0, second=0, microsecond=0
  )

  return proximo_lunes, proximo_miercoles


def intentar_reservar_dia(fecha_clase, hora_buscada="16:00:00"):
  ticks = int(fecha_clase.timestamp())
  nombre_dia = (
      "lunes" if fecha_clase.weekday() == 0 else "miércoles"
  ).capitalize()
  fecha_str_esperada = f"{nombre_dia} {fecha_clase.strftime('%d/%m')}"

  url_cargar = f"{BASE_URL}/LoadClass.ashx?ticks={ticks}&idu={IDU}"
  response = requests.get(url_cargar)
  data = response.json()

  clases_del_dia = data.get("Data", [])
  tipo_no_clases = data.get("TipoNoClases", "")

  # CASO 1: El administrador aún no ha abierto la semana de reservas
  if not clases_del_dia:
    if tipo_no_clases == "NoCalendar":
      print(f" -> {fecha_str_esperada}: Las reservas aún no están abiertas.")
    else:
      # Si hay algún estado especial o festivo sin clases
      print(
          f" -> {fecha_str_esperada}: No hay clases configuradas"
          f" (TipoNoClases: {tipo_no_clases})."
      )
    return False

  # CASO 2: Buscar la clase de la hora deseada
  id_clase = None
  clase_encontrada_en_horario = False

  for bloque in clases_del_dia:
    if bloque.get("Hora") == hora_buscada:
      clase_encontrada_en_horario = True
      for val_wrapper in bloque.get("Valores", []):
        valor = val_wrapper.get("Valor", {})
        if valor.get("HoraComienzo") == hora_buscada:
          estado = val_wrapper.get("TipoEstado", "")

          if estado == "Borrable":
            print(f" ¡Ya estás apuntado al {fecha_str_esperada} a las {hora_buscada}!")
            return True  # Ya está reservado, éxito

          id_clase = valor.get("Id")
          break

  # Si el bloque de las 16:00 no existe (ej: festivo o horario reducido de mañana)
  if not clase_encontrada_en_horario:
    msg = (
        f"⚠️ *Aviso WodBuster*\nNo hay clase disponible a las {hora_buscada} el"
        f" {fecha_str_esperada} (¿Festivo o cambio de horario?)"
    )
    print(msg)
    enviar_telegram(msg)
    return True  # Retornamos True para que el script deje de insistir en este día

  if not id_clase:
    print(f" -> No se encontró ID válido para las {hora_buscada}.")
    return False

  # CASO 3: Intentar reservar
  url_inscribir = (
      f"{BASE_URL}/Calendario_Inscribir.ashx?id={id_clase}&ticks={ticks}"
      f"&idu={IDU}&connectionId={CONNECTION_ID}"
  )
  res_inscripcion = requests.get(url_inscribir)
  resultado_json = res_inscripcion.json()

  if resultado_json.get("Res", {}).get("EsCorrecto"):
    msg = (
        f"✅ *¡Reserva Exitosa!*\nTe he apuntado automáticamente para el"
        f" *{fecha_str_esperada} a las {hora_buscada}* en Vitality."
    )
    print(msg)
    enviar_telegram(msg)
    return True
  else:
    msg = (
        f"❌ *Error en reserva*\nNo se pudo reservar el {fecha_str_esperada} a"
        f" las {hora_buscada}. Respuesta: {resultado_json}"
    )
    print(msg)
    enviar_telegram(msg)
    return False


if __name__ == "__main__":
  print("Iniciando verificación de reservas en WodBuster...")
  lunes, miercoles = obtener_proximo_lunes_y_miercoles()

  # Intentar reservar lunes y miércoles a las 16:00
  exito_lunes = intentar_reservar_dia(lunes, "16:00:00")
  exito_miercoles = intentar_reservar_dia(miercoles, "16:00:00")

  # Nota: Si quieres que el script de GitHub Actions pare de ejecutarse en cuanto
  # ambos días estén listos (o avisados por festivo), puedes controlar la salida.
