import settings_storage
import json
import os

print(f"Settings file exists: {os.path.exists('data/settings.json')}")

with open('data/settings.json', 'r') as f:
    settings = json.load(f)

print("Current settings:")
print(json.dumps(settings, indent=2))

guild_id = '123456789'  # Test guild ID

xp_settings = {
    "channel_id": 987654321,
    "min_xp": 20,
    "max_xp": 100,
    "duration": 1,
    "time_unit": "hour",
    "is_active": True
}

coin_settings = {
    "channel_id": 987654321,
    "min_coins": 10,
    "max_coins": 50,
    "duration": 1,
    "time_unit": "hour",
    "is_active": True
}

print("Saving test settings...")
settings_storage.settings_storage.save_xp_drop_settings(guild_id, xp_settings)
settings_storage.settings_storage.save_coin_drop_settings(guild_id, coin_settings)

with open('data/settings.json', 'r') as f:
    updated_settings = json.load(f)

print("\nUpdated settings:")
print(json.dumps(updated_settings, indent=2))