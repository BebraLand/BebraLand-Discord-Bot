"""
Example integration of the News Dashboard into main.py

Add this code to your main.py file to enable the web dashboard.
"""

# ============================================================================
# STEP 1: Add imports at the top of main.py
# ============================================================================

from src.web import init_dashboard, run_dashboard
import threading
import os

# ============================================================================
# STEP 2: Add to your bot's on_ready event
# ============================================================================

@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")
    
    # ... your existing on_ready code ...
    
    # Initialize the news dashboard
    try:
        init_dashboard(bot)
        logger.info("News dashboard initialized")
        
        # Start dashboard in a separate thread so it doesn't block the bot
        dashboard_host = os.getenv('DASHBOARD_HOST', '127.0.0.1')
        dashboard_port = int(os.getenv('DASHBOARD_PORT', 5000))
        dashboard_debug = os.getenv('DASHBOARD_DEBUG', 'False').lower() == 'true'
        
        dashboard_thread = threading.Thread(
            target=run_dashboard,
            kwargs={
                'host': dashboard_host,
                'port': dashboard_port,
                'debug': dashboard_debug
            },
            daemon=True  # Thread will close when main program exits
        )
        dashboard_thread.start()
        
        logger.info(f"🌐 News Dashboard started on http://{dashboard_host}:{dashboard_port}")
        logger.info(f"📋 Access the dashboard at: http://{dashboard_host}:{dashboard_port}")
        
    except Exception as e:
        logger.error(f"Failed to start news dashboard: {e}")
        logger.error("Dashboard will not be available. Bot will continue running.")

# ============================================================================
# STEP 3: Add to your .env file
# ============================================================================

"""
Add these environment variables to your .env file:

# News Dashboard Configuration
DASHBOARD_PASSWORD=your_secure_password_here
DASHBOARD_SECRET_KEY=random_hex_string_for_sessions
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=5000
DASHBOARD_DEBUG=False
"""

# ============================================================================
# STEP 4: Install dependencies
# ============================================================================

"""
Install Flask:
    pip install flask

Or add to requirements.txt:
    flask>=3.0.0
"""

# ============================================================================
# Example: Full on_ready with dashboard
# ============================================================================

"""
@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")
    
    # Initialize scheduler (if you have one)
    try:
        from src.utils.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.initialize(bot)
        logger.info("Scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
    
    # Register views/components
    try:
        from src.utils.register_persistent_ticket_views import register_persistent_ticket_views
        await register_persistent_ticket_views(bot)
        logger.info("Persistent views registered")
    except Exception as e:
        logger.error(f"Failed to register views: {e}")
    
    # Initialize and start dashboard
    try:
        from src.web import init_dashboard, run_dashboard
        import threading
        
        init_dashboard(bot)
        
        dashboard_thread = threading.Thread(
            target=run_dashboard,
            kwargs={
                'host': os.getenv('DASHBOARD_HOST', '127.0.0.1'),
                'port': int(os.getenv('DASHBOARD_PORT', 5000)),
                'debug': os.getenv('DASHBOARD_DEBUG', 'False').lower() == 'true'
            },
            daemon=True
        )
        dashboard_thread.start()
        
        logger.info(f"🌐 Dashboard: http://{os.getenv('DASHBOARD_HOST', '127.0.0.1')}:{os.getenv('DASHBOARD_PORT', 5000)}")
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
    
    logger.info("Bot is ready!")
"""
