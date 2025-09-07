import asyncio, logging, json
from bot import bot, dp
from config import CFG, AD
from data.loader import load_questions, load_messages, load_lemma
from models.quiz import QuizManager
from models.rating import RatingManager
from models.user import UserManager
from handlers import quiz as h_quiz, rating as h_rating, settings as h_settings, admin as h_admin
from services.scheduler import schedule_daily_stats, DailyStats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load data
    messages = load_messages(logger)
    lemma = load_lemma(logger)
    questions_map = load_questions(logger)

    # Background tasks
    stats = DailyStats()

    ad = AD()

    # Put shared context onto bot object (simple way)
    bot.context = {"messages": messages, "lemma": lemma}

    # Managers
    quiz_mgr = QuizManager(logger=logger, ad=ad, stats=stats)
    rating = RatingManager()
    users = UserManager()

    # Setup handlers dependencies
    h_quiz.setup(quiz_mgr, rating, users, questions_map)
    h_rating.setup(rating, users, ad)
    h_settings.setup(users)
    h_admin.setup(users, ad, stats)


    asyncio.create_task(schedule_daily_stats(bot, CFG.ADMIN_ID, stats))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
