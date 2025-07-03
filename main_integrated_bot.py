import openai
import telebot
import Constants as keys
from telebot import types
from pymongo import MongoClient
import logging
import quiz_educativo  

from gtts import gTTS  
import os
import tempfile

bot = telebot.TeleBot(keys.KEY_TELEGRAM)
openai.api_key = keys.KEY_OPENAI


client = MongoClient(keys.MONGO_URL)
db = client["quiz"]
quizzes_collection = db["quizzes"]


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("quiz_bot.log"),
    logging.StreamHandler()
])


quiz_educativo.register_handlers(bot)


@bot.message_handler(func=lambda message: not message.text.startswith("/"), content_types=['text'])
def handle_message(message):
    user_message = message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=150,
            temperature=0.7
        )
        bot.send_message(message.chat.id, response["choices"][0]["message"]["content"].strip())
    except Exception as e:
        logging.error(f"Error al procesar mensaje con OpenAI: {e}")
        bot.send_message(message.chat.id, "Hubo un error al procesar tu mensaje. Inténtalo de nuevo más tarde.")


@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    chat_id = message.chat.id
    try:

        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            temp_audio.write(downloaded_file)
            temp_audio_path = temp_audio.name

        with open(temp_audio_path, "rb") as audio_file:
            transcription = openai.Audio.transcribe("whisper-1", audio_file)
        
        transcribed_text = transcription.get("text", "")
        if not transcribed_text:
            bot.send_message(chat_id, "No se pudo transcribir el audio.")
            return

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": transcribed_text}],
            max_tokens=150,
            temperature=0.7
        )
        answer_text = response["choices"][0]["message"]["content"].strip()

        tts = gTTS(answer_text, lang='es')
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_response:
            tts.save(temp_response.name)
            response_audio_path = temp_response.name

        with open(response_audio_path, "rb") as voice:
            bot.send_voice(chat_id, voice)

        os.remove(temp_audio_path)
        os.remove(response_audio_path)

    except Exception as e:
        logging.error(f"Error al procesar mensaje de voz: {e}")
        bot.send_message(chat_id, "Hubo un error al procesar tu mensaje de voz. Inténtalo de nuevo más tarde.")


if __name__ == "__main__":
    logging.info("Bot en ejecución...")
    bot.polling(none_stop=True)