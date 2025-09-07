from dataclasses import dataclass, field
from typing import Dict, List, Any
from aiogram.enums import PollType
from aiogram import Bot
from utils.helpers import escape
import asyncio, logging, re
from config import CFG, AD
from services.scheduler import DailyStats

russian_to_latin_map = {'А':'A','В':'B','С':'C','D':'D'}

def normalize_answer(answer: str) -> str:
    return ''.join([russian_to_latin_map.get(c, c) for c in answer])

@dataclass
class QuizState:
    questions: List[dict]
    user_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)

@dataclass
class QuizManager:
    logger: logging.Logger
    ad: AD
    stats: DailyStats
    active: Dict[int, QuizState] = field(default_factory=dict)     # chat_id -> QuizState
    polls_info: Dict[str, dict] = field(default_factory=dict)      # poll_id -> {chat_id, correct_option_id}

    def is_running(self, chat_id: int) -> bool:
        return chat_id in self.active

    def start(self, chat_id: int, questions: List[dict]):
        self.active[chat_id] = QuizState(questions=questions)

    def stop(self, chat_id: int):
        if chat_id in self.active:
            del self.active[chat_id]

    def record_poll(self, poll_id: str, chat_id: int, correct_option_id: int):
        self.polls_info[poll_id] = {"chat_id": chat_id, "correct_option_id": correct_option_id}

    def handle_answer(self, poll_id: str, user_id: str, is_correct: bool, username: str | None, full_name: str | None):
        info = self.polls_info.get(poll_id)
        if not info:
            return None
        chat_id = info["chat_id"]
        self.stats.add_player(int(user_id))
        st = self.active.get(chat_id)
        if not st:
            return None
        st.user_scores.setdefault(user_id, {"score": 0, "user_name": "", "full_name": ""})
        st.user_scores[user_id]["user_name"] = username
        st.user_scores[user_id]["full_name"] = full_name
        if is_correct:
            st.user_scores[user_id]["score"] += 1
        return chat_id

    async def run_quiz(self, bot: Bot, chat_id: int, quiz_time: int, messages: dict):
        st = self.active.get(chat_id)
        if not st:
            return

        self.stats.inc_games()
        for i, q in enumerate(st.questions):
            print(q)
            options = list(q["answers"].keys())
            correct_answer = normalize_answer(q["CorrectAnswers"].upper())
            options_norm = [normalize_answer(o).upper() for o in options]

            if len(q["question"]) >= 299:
                self.logger.error("Слишком длинный вопрос — пропущено")
                continue

            f = False
            for opt in options:
                if len(opt) >= 99:
                    f = True
                    self.logger.error(f"Слишком длинный вопрос — пропущено")
            if f:
                continue

            if correct_answer not in options_norm:
                self.logger.error("Правильный ответ не найден в вариантах — пропущено")
                continue

            if "picture_id" in q:
                if q["picture_id"]:
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=q["picture_id"]
                        )
                        await asyncio.sleep(1)
                    except:
                        await bot.send_message(
                            CFG.ADMIN_ID,
                            f"⚠️ Не удалось отправить картинку для вопроса:\n{q['question']}"
                        )
                        continue

            correct_index = options_norm.index(correct_answer)
            try:
                poll_msg = await bot.send_poll(
                    chat_id,
                    f"[{i+1}/{len(st.questions)}] " + q["question"],
                    list(q["answers"].values()),
                    type=PollType.QUIZ,
                    correct_option_id=correct_index,
                    is_anonymous=False,
                    open_period=False if quiz_time == 0 else quiz_time
                )
            except Exception as e:
                await bot.send_message(
                    CFG.ADMIN_ID,
                    f"<b>Не удалось отправить вопрос!</b>"
                    f"\n {q['question']} \n\n<b>Ошибка</b>"
                    f"\n<blockquote><code>{e}</code></blockquote>", parse_mode="HTML"
                )
                continue

            self.record_poll(poll_msg.poll.id, chat_id, poll_msg.poll.correct_option_id)
            await asyncio.sleep(30 if quiz_time == 0 else quiz_time)

            if chat_id not in self.active:
                return  # остановлено

        await self.send_results(bot, chat_id, messages)

    async def send_results(self, bot: Bot, chat_id: int, messages: dict):
        st = self.active.get(chat_id)
        if not st:
            return
        sorted_scores = sorted(st.user_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        text = messages["quiz_res"]
        f = 1
        for idx, (uid, data) in enumerate(sorted_scores, start=1):
            if (idx > 1):
                if int(data["score"]) != int(sorted_scores[idx - 2][1]["score"]):
                    f += 1
            if data["user_name"] and data["full_name"]:
                user_disp = f"<a href='tg://user?id={uid}'>{escape(data['full_name'])}</a>"
            elif data["user_name"]:
                user_disp = f"@{data['user_name']}"
            else:
                user_disp = data["full_name"] or messages.get("unknown_user", "Unknown")
            num = f
            if (f == 1):
                num = "🥇"
            elif (f == 2):
                num = "🥈"
            elif (f == 3):
                num = "🥉"
            text += messages["user_score"].format(num=num, user=user_disp, score=str(data["score"]))

        add_text = f"<blockquote>{self.ad.get_ad()}</blockquote>\n" if self.ad.get_ad() != " " else messages.get("default_ad", "").format(chat_link="@mmt_taj")
        text += "\n" + add_text

        from aiogram.types import LinkPreviewOptions
        await bot.send_message(
            chat_id, text, parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(
                url=self.ad.get_link()
                if self.ad.get_link()
                   or self.ad.get_link() != " "
                else None,
                prefer_small_media=True)
        )
        del self.active[chat_id]
