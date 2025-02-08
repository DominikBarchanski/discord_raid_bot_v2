# config.py
import os

# Role i stałe
ROLE_MARATO = "maratoniarz"
ROLE_CZLONEK = "członek"
ROLE_MLODY_CZLONEK = "młodszy członek"
ROLE_ALT_ALLOW = "alt_allow"

STANDARD_MENTION_ROLES = ["członek", "młodszy członek"]

SKILL_RANGE_DEFAULT = range(1, 12)
SKILL_RANGE_MSW = [1, 2, 3, 4, 9, 10, 11]

MARATONIARZ_THRESHOLD_HOURS = 10
NOTIFICATION_THRESHOLD_HOURS = 12
AUTO_PROMOTE_CHECK_MINUTES = 5
WARN_THRESHOLD_MINUTES = 180

DATETIME_FORMAT_1 = "%H:%M %Y-%m-%d"
DATETIME_FORMAT_2 = "%Y-%m-%d %H:%M"

TOKEN = os.environ.get("DISCORD_TOKEN")

# Specializations – zapisywane jako np. ":MSW_SP1:"; w pick liście wyświetlamy tylko "SP1"
specializations = {
    "⚔️ Swordsman": [f":Sword_SP{i}:" for i in SKILL_RANGE_DEFAULT],
    "🏹 Archer": [f":Arch_SP{i}:" for i in SKILL_RANGE_DEFAULT],
    "🔮 Mage": [f":MAG_SP{i}:" for i in SKILL_RANGE_DEFAULT],
    "🥋 Martial Artist": [f":MSW_SP{i}:" for i in SKILL_RANGE_MSW],
}

# Redis – jeśli korzystasz z Redisa, ustaw zmienną środowiskową REDISCLOUD_URL
REDIS_URL = os.environ.get("REDISCLOUD_URL", "redis://localhost:6379")
