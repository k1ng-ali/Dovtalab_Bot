import re
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Config:
    TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
    ADMIN_ID: str = os.getenv("ADMIN_ID", "YOUR_ID")
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "YOUR_CHANNEL_ID")
    CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME", "YOUR_CHANNEL_USERNAME")
    RATING_FILE: str = os.getenv("RATING_FILE", "db/rating.json")
    GROUP_RATING_FILE: str = os.getenv("GROUP_RATING_FILE", "db/group_rating.json")
    USERS_FILE: str = os.getenv("USERS_FILE", "db/UsersConfig.json")
    MESSAGES_FILE: str = os.getenv("MESSAGES_FILE", "db/Messages.json")
    LEMMA_FILE: str = os.getenv("LEMMA_FILE", "db/lemma.json")
    files = {
        "БИОЛОГИЯ": "db/Biology.json",
        #"ГЕОГРАФИЯ": "db/Geography.json",
        #"ИСТОРИЯ": "db/History.json",
        #"ЛИТЕРАТУРА": "db/Literature.json",
        #"ПРАВО": "db/Rights.json",
        #"ЯЗЫК": "db/Zabon.json",
        #"ДИПЛОМАТИЯ": "db/Diplomacy.json"
    }

@dataclass
class AD:
    ad_text:str = os.getenv("AD", "Чати мо: @mmt_taj")

    def set_ad(self, ad_text):
        self.ad_text = ad_text

    def get_ad(self):
        return self.ad_text

    def get_link(self):
        text = self.ad_text.replace("@", "https://t.me/")
        match = re.search(r'(https://\S+|t\.me/\S+)', text)
        ad_link = match.group(0) if match else None
        return ad_link

CFG = Config()
LANGUAGES = {
    "ru": "Русский",
    "en": "English",
    "tg": "Тоҷикӣ",
    "uz": "Узбекча"
}
