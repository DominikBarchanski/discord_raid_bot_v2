# db.py
import json
import redis
from config import REDIS_URL

# Inicjuj klienta Redis
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

def ensure_db_table():
    # Dla Redisa nie musimy tworzyć tabel – funkcja placeholder
    pass

def save_raid_to_db(raid: "Raid"):
    """
    Zapisuje dane raidu jako JSON w Redis.
    Klucz: "raid:{channel_id}"
    """
    key = f"raid:{raid.channel_id}"
    data_json = json.dumps(raid.to_dict())
    redis_client.set(key, data_json)

def load_all_raids_from_db(bot: "RaidBot"):
    """
    Ładuje wszystkie raidy zapisane w Redisie.
    Klucze mają format "raid:{channel_id}".
    """
    keys = redis_client.keys("raid:*")
    for key in keys:
        data_json = redis_client.get(key)
        if data_json:
            data = json.loads(data_json)
            from models import Raid  # import w czasie wykonania
            raid = Raid.from_dict(data, bot)
            if raid is not None:
                bot.raids[int(raid.channel_id)] = raid

def remove_raid_from_db(channel_id: int):
    key = f"raid:{channel_id}"
    redis_client.delete(key)
