
import telebot
from telebot import types
import Constants as keys
from pymongo import MongoClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("quiz_bot.log"),
    logging.StreamHandler()
])

client = MongoClient(keys.MONGO_URL)
db = client["quiz"]  
quizzes_collection = db["quizzes"]

(START, QUIZ_TITLE, NUM_QUESTIONS, ADD_QUESTION, QUESTION_TEXT, ADD_ANSWER,
 QUIZ_START, QUIZ_ONGOING, CORRECT_ANSWER, DELETE_QUIZ) = range(10)

quizzes = {}
user_status = {}
current_quiz = {}
current_question = {}

def get_user_step(uid):
    if uid in user_status:
        return user_status[uid]
    else:
        user_status[uid] = START
        return START

def register_handlers(bot):
    """Registra los handlers de los comandos del quiz en la instancia 'bot' pasada."""
    
    @bot.message_handler(commands=['newquiz'])
    def command_newquiz(message):
        cid = message.chat.id
        bot.send_message(cid, "Ingresa el título del quiz:")
        user_status[cid] = QUIZ_TITLE
        current_quiz[cid] = {'title': None, 'num_questions': None, 'questions': []}

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == QUIZ_TITLE)
    def quiz_title(message):
        cid = message.chat.id
        quiz_title = message.text
        current_quiz[cid]['title'] = quiz_title
        bot.send_message(cid, "¿Cuántas preguntas tendrá el quiz?")
        user_status[cid] = NUM_QUESTIONS

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == NUM_QUESTIONS)
    def quiz_num_questions(message):
        cid = message.chat.id
        try:
            num_questions = int(message.text)
            if num_questions <= 0:
                bot.send_message(cid, "El número debe ser mayor que 0. Intenta nuevamente.")
                return
            current_quiz[cid]['num_questions'] = num_questions
            bot.send_message(cid, "Ingresa la primera pregunta:")
            user_status[cid] = ADD_QUESTION
        except ValueError:
            bot.send_message(cid, "Eso no parece ser un número válido. Por favor, ingresa un número.")

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == ADD_QUESTION)
    def question_step(message):
        cid = message.chat.id
        quiz = current_quiz[cid]
        if len(quiz['questions']) < quiz['num_questions']:
            question_text = message.text
            quiz['questions'].append({'text': question_text, 'answers': [], 'correct': None})
            bot.send_message(cid, "Envía las opciones de respuesta una por una y luego escribe 'listo' cuando termines.")
            user_status[cid] = ADD_ANSWER
        else:
            bot.send_message(cid, "Ya has añadido todas las preguntas para este quiz.")

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == ADD_ANSWER)
    def answer_step(message):
        cid = message.chat.id
        quiz = current_quiz[cid]
        question = quiz['questions'][-1]
        if message.text.lower() != 'listo':
            question['answers'].append(message.text)
            bot.send_message(cid, "Opción añadida. Agrega otra o escribe 'listo' si has terminado.")
        else:
            if question['answers']:
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                for answer in question['answers']:
                    markup.add(answer)
                bot.send_message(cid, "¿Cuál es la respuesta correcta?", reply_markup=markup)
                user_status[cid] = CORRECT_ANSWER
            else:
                bot.send_message(cid, "Debes agregar al menos una opción de respuesta antes de continuar.")

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == CORRECT_ANSWER)
    def correct_answer_step(message):
        cid = message.chat.id
        quiz = current_quiz[cid]
        question = quiz['questions'][-1]
        if message.text in question['answers']:
            question['correct'] = question['answers'].index(message.text)
            if len(quiz['questions']) < quiz['num_questions']:
                bot.send_message(cid, "Pregunta añadida. Ingresa la siguiente pregunta:")
                user_status[cid] = ADD_QUESTION
            else:
                bot.send_message(cid, "El quiz ha sido creado con éxito. Guardando en la base de datos...")
                try:
                    quizzes_collection.insert_one(quiz)
                    bot.send_message(cid, "El quiz se ha guardado correctamente en la base de datos.")
                    logging.info(f"Quiz guardado en la base de datos: {quiz}")
                except Exception as e:
                    bot.send_message(cid, "Hubo un error al guardar el quiz en la base de datos.")
                    logging.error(f"Error al guardar el quiz: {e}")
                user_status[cid] = START
        else:
            bot.send_message(cid, "Selecciona la respuesta correcta de las opciones proporcionadas.")

    @bot.message_handler(commands=['quiz'])
    def command_quiz(message):
        cid = message.chat.id
        try:
            available_quizzes = list(quizzes_collection.find({}, {"_id": 0, "title": 1}))
            if available_quizzes:
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                for quiz in available_quizzes:
                    markup.add(quiz["title"])
                bot.send_message(cid, "Selecciona un quiz:", reply_markup=markup)
                user_status[cid] = QUIZ_START
            else:
                bot.send_message(cid, "No hay quizzes disponibles. Crea uno con /newquiz.")
        except Exception as e:
            bot.send_message(cid, "Hubo un error al cargar los quizzes disponibles.")
            logging.error(f"Error al cargar los quizzes: {e}")

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == QUIZ_START)
    def select_quiz(message):
        cid = message.chat.id
        selected_quiz_title = message.text
        try:
            selected_quiz = quizzes_collection.find_one({"title": selected_quiz_title}, {"_id": 0})
            if selected_quiz:
                current_quiz[cid] = selected_quiz
                current_quiz[cid]["current_question"] = 0
                current_quiz[cid]["score"] = 0
                ask_question(cid)
                user_status[cid] = QUIZ_ONGOING
            else:
                bot.send_message(cid, "No se encontró el quiz seleccionado. Intenta de nuevo.")
        except Exception as e:
            bot.send_message(cid, "Hubo un error al cargar el quiz seleccionado.")
            logging.error(f"Error al cargar el quiz seleccionado: {e}")

    def ask_question(cid):
        quiz = current_quiz[cid]
        q_num = quiz["current_question"]
        if q_num < len(quiz["questions"]):
            question = quiz["questions"][q_num]
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
            for answer in question["answers"]:
                markup.add(answer)
            bot.send_message(cid, f"Pregunta {q_num + 1}: {question['text']}", reply_markup=markup)
            user_status[cid] = QUIZ_ONGOING
        else:
            bot.send_message(cid, f"Has terminado el quiz. Tu puntuación fue: {quiz['score']}/{len(quiz['questions'])}")
            user_status[cid] = START

    @bot.message_handler(func=lambda message: get_user_step(message.chat.id) == QUIZ_ONGOING)
    def handle_quiz_answer(message):
        cid = message.chat.id
        quiz = current_quiz[cid]
        if quiz["current_question"] < len(quiz["questions"]):
            question = quiz["questions"][quiz["current_question"]]
            selected_answer = message.text.strip()
            if selected_answer == question["answers"][question["correct"]]:
                quiz["score"] += 1
                response = "¡Correcto!"
            else:
                response = "Incorrecto."
            quiz["current_question"] += 1
            if quiz["current_question"] < len(quiz["questions"]):
                ask_question(cid)
            else:
                response += f" Has terminado el quiz. Tu puntuación fue: {quiz['score']}/{len(quiz['questions'])}"
                user_status[cid] = START
                bot.send_message(cid, response)
        else:
            bot.send_message(cid, "Este cuestionario ya ha sido completado.")
            user_status[cid] = START

    @bot.message_handler(commands=['delete'])
    def command_delete_quiz(message):
        cid = message.chat.id
        try:
            available_quizzes = list(quizzes_collection.find({}, {"_id": 0, "title": 1}))
            if available_quizzes:
                markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                for quiz in available_quizzes:
                    markup.add(quiz["title"])
                bot.send_message(cid, "Selecciona el quiz que deseas eliminar:", reply_markup=markup)
                user_status[cid] = DELETE_QUIZ
            else:
                bot.send_message(cid, "No hay quizzes disponibles para eliminar.")
        except Exception as e:
            bot.send_message(cid, "Hubo un error al cargar los quizzes para eliminar.")
            logging.error(f"Error al cargar los quizzes para eliminar: {e}")

    @bot.message_handler(func=lambda message: user_status.get(message.chat.id) == DELETE_QUIZ)
    def delete_selected_quiz(message):
        cid = message.chat.id
        selected_quiz_title = message.text
        try:
            result = quizzes_collection.delete_one({"title": selected_quiz_title})
            if result.deleted_count > 0:
                bot.send_message(cid, f"El quiz '{selected_quiz_title}' ha sido eliminado correctamente.")
                logging.info(f"Quiz eliminado: {selected_quiz_title}")
            else:
                bot.send_message(cid, f"No se encontró el quiz '{selected_quiz_title}'.")
            user_status[cid] = START
        except Exception as e:
            bot.send_message(cid, "Hubo un error al intentar eliminar el quiz.")
            logging.error(f"Error al eliminar el quiz: {e}")

    @bot.message_handler(commands=['help'])
    def command_help(message):
        cid = message.chat.id
        help_message = (
            "¡Bienvenido al bot tu ayuda en clase!\n"
            "Puedes hablar con el bot y te ayudara en lo que necesites.\n"
            "Puedes interaccionar por texto y voz \n"
            "además de utilizar los siguientes comandos:\n"
            "/newquiz - Iniciar la creación de un nuevo quiz\n"
            "/quiz - Selecciona un quiz existente para jugar\n"
            "/delete - Selecciona un quiz para borrar\n"
            "/help - Mostrar este mensaje de ayuda"
        )
        bot.send_message(cid, help_message)

    @bot.message_handler(commands=['start'])
    def command_start(message):
        cid = message.chat.id
        start_message = (
            "¡Bienvenido al bot tu ayuda en clase!\n"
            "Puedes hablar con el bot y te ayudara en lo que necesites.\n"
            "Puedes interaccionar por texto y voz \n"
            "además de utilizar los siguientes comandos:\n"
            "/newquiz - Iniciar la creación de un nuevo quiz\n"
            "/quiz - Selecciona un quiz existente para jugar\n"
            "/delete - Selecciona un quiz para borrar\n"
            "/help - Mostrar este mensaje de ayuda"
        )
        bot.send_message(cid, start_message)