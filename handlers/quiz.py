import random, logging, asyncio
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import dp, bot
from models.quiz import QuizManager
from models.rating import RatingManager
from models.user import UserManager
from data.loader import save_post
from config import  CFG

logger = logging.getLogger(__name__)

# Dependency container (simple)
quiz_manager: QuizManager | None = None
rating: RatingManager | None = None
users: UserManager | None = None
questions_map: dict[str, list[dict]] = {}
questions_index: dict[str, dict[str, dict]] = {}
topics = {
    "БИОЛОГИЯ":"БИОЛОГИЯ",
    "BIOLOGY":"БИОЛОГИЯ",
    "BIOLOGIYA":"БИОЛОГИЯ",
    "ГЕОГРАФИЯ":"ГЕОГРАФИЯ",
    "GEOGRAPHY":"ГЕОГРАФИЯ",
    "GEOGRAFIYA":"ГЕОГРАФИЯ",
    "ИСТОРИЯ":"ИСТОРИЯ",
    "HISTORY":"ИСТОРИЯ",
    "ТАРИХ":"ИСТОРИЯ",
    "ТАЪРИХ":"ИСТОРИЯ",
    "TARIX":"ИСТОРИЯ",
    "ЛИТЕРАТУРА":"ЛИТЕРАТУРА",
    "АДАБИЁТ":"ЛИТЕРАТУРА",
    "АДАБИЙОТ":"ЛИТЕРАТУРА",
    "АДАБИЕТ":"ЛИТЕРАТУРА",
    "LITERATURE":"ЛИТЕРАТУРА",
    "ADABIYOT":"ЛИТЕРАТУРА",
    "ПРАВО":"ПРАВО",
    "ПРАВА":"ПРАВО",
    "LAW":"ПРАВО",
    "ХУКУК":"ПРАВО",
    "ХУҚУҚ":"ПРАВО",
    "ҲУҚУҚ":"ПРАВО",
    "HUQUQ":"ПРАВО",
    "ЯЗЫК":"ЯЗЫК",
    "ЗАБОН":"ЯЗЫК",
    "LANGUAGE":"ЯЗЫК",
    "TIL":"ЯЗЫК",
    "ДИПЛОМАТИЯ":"ДИПЛОМАТИЯ"
}

def setup(_quiz: QuizManager,
          _rating: RatingManager,
          _users: UserManager,
          _questions: dict):
    global quiz_manager, rating, users, questions_map
    quiz_manager = _quiz
    rating = _rating
    users = _users
    questions_map = _questions
    for sub, questions in questions_map.items():
        questions_index[sub] = {}
        for q in questions:
            questions_index[sub][q["number"]] = q

@dp.message(Command("start_quiz"))
async def start_quiz(msg: types.Message):
    assert quiz_manager and rating and users
    users.ensure(msg.chat.id, is_group=(msg.chat.type != "private"), title=getattr(msg.chat, "title", None),
                 username=getattr(msg.chat, "username", None), is_started=True)

    lang = users.get_lang(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id), "tg")
    # messages dictionary is supposed to be loaded in main and passed via context; for brevity, store in bot['messages']
    messages = (getattr(bot, "context", {}) or {}).get("messages", {}).get(lang, {})

    if not users.started(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id)):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=messages.get("start_bot", "Активировать бота"),
                                                                         url="https://t.me/mmt_quiz_bot?start=command_start")]])
        return await msg.reply(messages.get("bot_inactive", "Бот не активирован"), reply_markup=kb)

    settings = users.get_settings(str(msg.chat.id))
    num_questions = settings["num_questions"]
    quiz_time = settings["quiz_time"]

    if quiz_manager.is_running(msg.chat.id):
        return await msg.reply(messages.get("quiz_alr_started", "Викторина уже идёт"), parse_mode="HTML")

    parts = msg.text.split(maxsplit=1)
    topic = parts[1].upper() if len(parts) > 1 else None
    if topic and topic in topics:
        selected = random.sample(questions_map[topics.get(topic)], num_questions) if len(questions_map[topics.get(topic)]) >= num_questions else questions_map[topic[1]][:]
        quiz_manager.start(msg.chat.id, selected)
        await msg.reply(messages.get("quiz_start", "Старт!").format(num_questions=num_questions, quiz_time=quiz_time), parse_mode="HTML")
        asyncio.create_task(quiz_manager.run_quiz(bot, msg.chat.id, quiz_time, messages))
    else:
        return await msg.reply(messages.get("topic_error", "Неверная тема"), parse_mode="HTML")

@dp.message(Command("stop_quiz"))
async def stop_quiz(msg: types.Message):
    assert quiz_manager and rating and users
    users.ensure(msg.chat.id, is_group=(msg.chat.type != "private"), title=getattr(msg.chat, "title", None),
                 username=getattr(msg.chat, "username", None), is_started=True)
    lang = users.get_lang(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id), "tg")
    messages = (getattr(bot, "context", {}) or {}).get("messages", {}).get(lang, {})
    if (users.get_type(str(msg.chat.id)) != "private"):
        chat_member = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        if chat_member.status not in ["administrator", "creator"]:
            return await msg.reply(messages.get("quiz_stp_not_admin"), parse_mode="HTML")
    if quiz_manager.is_running(msg.chat.id):
        await quiz_manager.send_results(bot, msg.chat.id,messages)
        quiz_manager.stop(msg.chat.id)
        return await msg.reply(messages.get("quiz_stopped"), parse_mode="HTML")
    return await msg.reply(messages.get("not_actv_quiz"), parse_mode="HTML")

@dp.poll_answer()
async def on_poll_answer(ans: types.PollAnswer):
    assert quiz_manager and rating
    info = quiz_manager.polls_info.get(ans.poll_id)
    if not info:
        return
    is_correct = (ans.option_ids and ans.option_ids[0] == info["correct_option_id"])
    chat_id = quiz_manager.handle_answer(
        poll_id=ans.poll_id,
        user_id=str(ans.user.id),
        is_correct=is_correct,
        username=ans.user.username,
        full_name=ans.user.full_name
    )
    if chat_id is not None:
        if is_correct:
            rating.add_point(chat_id, str(ans.user.id), ans.user.username, ans.user.full_name)
        else:
            rating.touch_user(chat_id, str(ans.user.id), ans.user.username, ans.user.full_name)
        rating.save()

@dp.message(Command("set_picture"))
async def set_picture(msg: types.Message):
    assert quiz_manager and rating and users
    users.ensure(msg.chat.id, is_group=(msg.chat.type != "private"), title=getattr(msg.chat, "title", None),
                 username=getattr(msg.chat, "username", None), is_started=True)
    lang = users.get_lang(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id), "tg")
    messages = (getattr(bot, "context", {}) or {}).get("messages", {}).get(lang, {})
    if (str(msg.from_user.id) != CFG.ADMIN_ID):
        return await msg.reply(messages.get("not_admin",  "Эта настройка доступна только Админстратору!"),
                               parse_mode="HTML")
    if (not msg.photo):
        return await msg.reply(messages.get("no_image",  "⚠\uFE0F Прикрепите фото к команде!"),
                               parse_mode="HTML")
    args = msg.caption.split()
    if len(args) != 3:
        return await msg.reply(messages.get("pic_error", "❗ Формат: /set_picture [предмет] [номер]"),
                               parse_mode="HTML")
    command, subject, q_num = args
    q_num = int(q_num)
    subject = subject.upper()
    if (subject not in topics):
        return await msg.reply(
            messages.get("topic_error", "Неправильное название викторины"),
            parse_mode="HTML"
        )
    photo = msg.photo[-1].file_id
    channel_post = await bot.send_photo(
        chat_id=CFG.CHANNEL_ID,
        photo=photo,
        caption=f"📌 Ресурс: <b>{topics.get(subject)} #{q_num}</b>",
        parse_mode="HTML"
    )

    pic_id = channel_post.photo[-1].file_id
    q = questions_index[topics.get(subject)].get(str(q_num))
    if not q:
        await bot.delete_message(CFG.CHANNEL_ID, channel_post.message_id)
        return await msg.reply(messages.get("quiz_not_finde", "Вопрос   {subject} | {q_num}  не найдено!").format(subject=topics.get(subject),q_num=q_num), parse_mode="HTML")
    q["picture_id"] = pic_id
    if (save_post(topics.get(subject), questions_map[topics.get(subject)])):
        return await msg.reply(
            messages.get("picture_is_set", "✅ Картинка сохранена и привязана к вопросу {q_num}").format(q_num=q_num),
            parse_mode="HTML")
    else:
        await msg.reply("Ошибка!", parse_mode="HTML")
        await bot.delete_message(CFG.CHANNEL_ID, channel_post.message_id)

@dp.message(Command("del_picture"))
async def del_picture(msg: types.Message):
    assert quiz_manager and rating and users
    users.ensure(msg.chat.id, is_group=(msg.chat.type != "private"), title=getattr(msg.chat, "title", None),
                 username=getattr(msg.chat, "username", None), is_started=True)
    lang = users.get_lang(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id), "tg")
    messages = (getattr(bot, "context", {}) or {}).get("messages", {}).get(lang, {})
    if (str(msg.from_user.id) != CFG.ADMIN_ID):
        return await msg.reply(messages.get("not_admin", "Эта настройка доступна только Админстратору!"),
                               parse_mode="HTML")
    args = msg.text.split()
    if len(args) != 3:
        return await msg.reply(messages.get("del_pic_error", "❗ Формат: /del_picture [предмет] [номер]"),
                               parse_mode="HTML")
    command, subject, q_num = args
    subject = subject.upper()
    q_num = int(q_num)
    if (subject not in topics):
        return await msg.reply(
            messages.get("topic_error", "Неправильное название викторины"),
            parse_mode="HTML"
        )
    channel_post = await bot.send_message(
        chat_id=CFG.CHANNEL_ID,
        text=f"📌 Удаление ресурса: {topics.get(subject)} #{q_num}",
        parse_mode = "HTML"
    )
    q = questions_index[topics.get(subject)].get(str(q_num))
    if not q:
        await bot.delete_message(CFG.CHANNEL_ID, channel_post.message_id)
        return await msg.reply(messages.get("quiz_not_finde", "Вопрос   {subject} | {q_num}  не найдено!").format(subject=topics.get(subject),q_num=q_num), parse_mode="HTML")
    q["picture_id"] = None
    if (save_post(topics.get(subject), questions_map[topics.get(subject)])):
        return await msg.reply(
            messages.get("pic_is_del", "Картинка вопроса {subject} | {q_num} удалена!").format(q_num=q_num,
                                                                                               subject=topics.get(subject)),
            parse_mode="HTML")
    else:
        await msg.reply("Ошибка!", parse_mode="HTML")
        await bot.delete_message(CFG.CHANNEL_ID, channel_post.message_id)


@dp.message(Command("get_quiz"))
async def get_quiz(msg: types.Message):
    assert quiz_manager and rating and users
    users.ensure(msg.chat.id, is_group=(msg.chat.type != "private"), title=getattr(msg.chat, "title", None),
                 username=getattr(msg.chat, "username", None), is_started=True)
    lang = users.get_lang(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id), "tg")
    messages = (getattr(bot, "context", {}) or {}).get("messages", {}).get(lang, {})
    args = msg.text.split()
    if len(args) != 3:
        return await msg.reply(messages.get("get_quiz_error","❗ Формат: /get_quiz [предмет] [номер]"), parse_mode="HTML")
    command, subject, q_num = args
    q_num = int(q_num)
    subject = subject.upper()
    if (subject not in topics):
        return await msg.reply(
            messages.get("topic_error", "Неправильное название викторины"),
            parse_mode="HTML"
        )
    q = questions_index[topics.get(subject)].get(str(q_num))
    if not q:
        return await msg.reply(messages.get("quiz_not_finde", "Вопрос   {subject} | {q_num}  не найдено!").format(subject=topics.get(subject),q_num=q_num), parse_mode="HTML")
    if not users.started(str(msg.chat.id) if msg.chat.type != "private" else str(msg.from_user.id)):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=messages.get("start_bot", "Активировать бота"),
                                                   url="https://t.me/mmt_quiz_bot?start=command_start")]])
        return await msg.reply(messages.get("bot_inactive", "Бот не активирован"), reply_markup=kb, parse_mode="HTML")

    settings = users.get_settings(str(msg.chat.id))
    num_questions = settings["num_questions"]
    quiz_time = 1

    if quiz_manager.is_running(msg.chat.id):
        return await msg.reply(messages.get("quiz_alr_started", "Викторина уже идёт"), parse_mode="HTML")
    try:
        selected = []
        selected.append(q)
        quiz_manager.start(msg.chat.id, selected)
        await msg.reply(messages.get("quiz_start", "Старт!").format(num_questions=num_questions, quiz_time=quiz_time), parse_mode="HTML")
        asyncio.create_task(quiz_manager.run_quiz(bot, msg.chat.id, quiz_time, messages))
    except Exception as e:
        await bot.send_message(
            CFG.ADMIN_ID,
            "Ошибка при получении вопроса",
             parse_mode = "HTML"
        )