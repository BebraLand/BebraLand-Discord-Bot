# This module holds the global bot instance for access in background tasks,
# schedulers, or utilities where passing the bot object is difficult or causes circular imports.

_bot = None

def set_bot(bot_instance):
    """Store the global bot instance."""
    global _bot
    _bot = bot_instance

def get_bot():
    """Retrieve the global bot instance. Returns None if not set."""
    return _bot
