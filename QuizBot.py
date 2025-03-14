import json
import random
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import PollType
from aiogram.types import PollAnswer
from aiogram.utils.keyboard import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "7482401970:AAEBqXFwrKfh0hP7C0sT8ZswmW5ZCUFn9rA"
CHANNEL_ID = "-1001770161076"
RATING_FILE = "rating.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настроим логирование
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# Загружаем базу вопросов
with open("biology_new.json", "r", encoding="utf-8") as f:
    questions = [q for q in json.load(f) if not q["pictures"]]

# Храним текущие викторины
active_quizzes = {}
# Словарь для замены русских букв на латинские
russian_to_latin_map = {
    'А':'A','В':'B','С':'C','D':'D'
}

# Функция для преобразования русских букв в латинские
def normalize_answer(answer):
    return ''.join([russian_to_latin_map.get(c, c) for c in answer])

# Подсчет баллов
user_scores = {}
polls_info = {}
global_scores ={}


# Функция для загрузки рейтинга из файла
def load_global_scores():
    if os.path.exists(RATING_FILE):
        with open(RATING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Функция для сохранения рейтинга в файл
def save_global_scores():
    with open(RATING_FILE, "w", encoding="utf-8") as f:
        json.dump(global_scores, f, ensure_ascii=False, indent=2)

# Загружаем рейтинг при запуске бота
global_scores = load_global_scores()

async def send_quiz(chat_id, quiz_id, questions, quiz_time):
    for i, q in enumerate(questions):
        options = list(q["Answers"].keys())  # Получаем список вариантов ответов
        correct_answer = q["CorrectAnswers"].upper()  # Приводим правильный ответ к верхнему регистру

        # Преобразуем правильный ответ и все варианты в латинский алфавит
        correct_answer = normalize_answer(correct_answer)
        options = [normalize_answer(opt).upper() for opt in options]

        if correct_answer not in options:
            logger.error(f"Ошибка! Правильный ответ '{correct_answer}' не найден в вариантах {options} для вопроса: {q['question']}")
            continue  # Пропустить этот вопрос

        correct_index = options.index(correct_answer)  # Индекс правильного ответа



        poll_msg = await bot.send_poll(
            chat_id, f"[{i+1}/{len(questions)}] "+q["question"], list(q["Answers"].values()), type=PollType.QUIZ,
            correct_option_id=correct_index, is_anonymous=False, open_period=quiz_time
        )

        # Сохраняем информацию о викторине по ID
        polls_info[poll_msg.poll.id] = {
            'question': q['question'],
            'options': options,
            'correct_option_id': poll_msg.poll.correct_option_id
        }
        # Логируем отправку вопроса
        logger.info(f"Отправлен вопрос: '{q['question']}' с вариантами: {options}", f"и правильным ответом: {correct_answer} id: {poll_msg.poll.id}")

        # Ждем 30 секунд
        await asyncio.sleep(quiz_time)

        if quiz_id not in active_quizzes:
            return  # Остановлено админом

    # Отправляем результат
    result_text = "\U0001F3C6 Итоги викторины:\n\n"
    sorted_user_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
    for user, score in sorted_user_scores:
        result_text += f"{user}: {score} баллов\n"
    await bot.send_message(chat_id, result_text)
    del active_quizzes[quiz_id]
    user_scores.clear()
    save_global_scores()

# Обработчик ответов на вопросы
@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    logger.info(json.dumps(poll_answer.model_dump(), ensure_ascii=False, indent=2))

    user_name = ''
    if poll_answer.user.username != None:
        user_name = "@"+poll_answer.user.username
    else:
        user_name = poll_answer.user.full_name
    answer = poll_answer.option_ids[0]  # Получаем выбранный вариант
    print(user_name)

    # Получаем quiz_id через poll_id
    poll_id = poll_answer.poll_id
    #question = active_quizzes.get(poll_id)  # Используем poll_id для поиска вопроса
    #if not question:
    #    return

    if poll_id in polls_info:
        if answer == polls_info[poll_id]['correct_option_id']:
            user_scores[user_name] = user_scores.get(user_name, 0) + 1
            global_scores[user_name] = global_scores.get(user_name, 0) + 1
            logger.info(f"Пользователю {poll_answer.user.full_name} начислен балл за правильный ответ")
        else:
            logger.info(f"Пользователь {poll_answer.user.full_name} выбрал неправильный ответ '{answer}'")


    # Извлекаем правильный ответ и вариант пользователя
    #correct_answer = question["CorrectAnswers"]
    #selected_answer = list(question["Answers"].keys())[answer]

    # Логируем выбор пользователя
    #logger.info(f"Пользователь {poll_answer.user.full_name} (ID: {user_id}) выбрал вариант '{selected_answer}' для вопроса: '{question['question']}'")

    # Проверка правильности ответа
    #if normalize_answer(selected_answer.upper()) == normalize_answer(correct_answer.upper()):
    #    user_scores[user_id] = user_scores.get(user_id, 0) + 1
    #    logger.info(f"Пользователю {poll_answer.user.full_name} начислен балл за правильный ответ")
    #else:
    #    logger.info(f"Пользователь {poll_answer.user.full_name} выбрал неправильный ответ '{selected_answer}'")

@dp.message(Command("rating"))
async def rating(msg: types.Message):
    result_text = "\U0001F3C6 Топ игроков:\n\n"
    sorted_user_scores = sorted(global_scores.items(), key=lambda x: x[1], reverse=True)
    i = 1
    for user, score in sorted_user_scores:
        result_text += f"{i}) {user}: {score} баллов\n"
        i += 1
        if i>10:
            break
    result_text += f"\nВсего игроков: {len(global_scores)}\n"
    i = 1
    current_user = ''
    if msg.from_user.username != None:
        current_user = "@"+msg.from_user.username
    else:
        current_user = msg.from_user.full_name
    for user, score in sorted_user_scores:
        if user == current_user:
            result_text += f"\nВаш счет: {score} баллов, место в рейтинге: {i}\n"
            break
    await bot.send_message(msg.chat.id, result_text)

# Старт викторины
@dp.message(Command("start_quiz"))
async def start_quiz(msg: types.Message):
    if msg.chat.type == "private":
        #chat_member = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        #if chat_member.status not in ["administrator", "creator"]:
            return await msg.reply("Только админ может запустить викторину!")

    quiz_id = msg.chat.id
    if quiz_id in active_quizzes:
        return await msg.reply("⚠ Уже идет викторина!")

    num_questions = 10
    quiz_time = 30
    command_parts = msg.text.split()  # Разделяем текст по пробелам
    try:
        # Проверяем, если вторая часть существует и является числом
        if len(command_parts) > 1:
            if (command_parts[1].isdigit()):
                if (int(command_parts[1]) >= 1 and int(command_parts[1]) <= 30):
                    num_questions = int(command_parts[1])
        if len(command_parts) > 2:
            if (command_parts[2].isdigit()):
                if (int(command_parts[2]) >= 5 and int(command_parts[2]) <= 60):
                    quiz_time = int(command_parts[2])

    except ValueError:
        pass

    selected_questions = random.sample(questions, num_questions)
    results = {}
    active_quizzes[quiz_id] = selected_questions  # Сохраняем вопросы викторины для этого чата

    # Логируем старт викторины
    logger.info(f"Викторина стартована в чате {msg.chat.title} ({msg.chat.id})")

    # Используем asyncio.create_task вместо threading
    asyncio.create_task(send_quiz(quiz_id, quiz_id, selected_questions, quiz_time))

    await msg.reply(f"\U0001F3AF Викторина началась! Готовьтесь! [{num_questions} вопросов, {quiz_time} секунд на ответ]")

# Остановка викторины
@dp.message(Command("stop_quiz"))
async def stop_quiz(msg: types.Message):
    if msg.chat.type == "private":
        #chat_member = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        #if chat_member.status not in ["administrator", "creator"]:
            return await msg.reply("Только админ может остановить викторину!")

    quiz_id = msg.chat.id
    if quiz_id not in active_quizzes:
        return await msg.reply("❌ Нет активной викторины!")

    await msg.reply("⛔ Викторина остановлена!")
    result_text = "\U0001F3C6 Итоги викторины:\n"
    sorted_user_scores = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)
    for user, score in sorted_user_scores:
        result_text += f"{user}: {score} баллов\n"
    await bot.send_message(msg.chat.id, result_text)
    del active_quizzes[quiz_id]
    user_scores.clear()
    save_global_scores()

@dp.message(Command("help"))
async def help(msg: types.Message):
    await msg.reply("Доступные команды:\n"
                    "/start_quiz [количество вопросов] [время на ответ в секундах] - начать викторину\n"
                    "/stop_quiz - остановить викторину\n"
                    "/rating - показать рейтинг игроков\n"
                    "/help - показать это сообщение")

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.reply("Привет! Я бот-викторина. Присоединяйтесь к нам в группу @mmt_taj и начнем викторину!")

# Основная функция для запуска бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
