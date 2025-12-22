"""Secure web dashboard for news broadcasting."""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import os
import asyncio
import discord
from datetime import datetime, timedelta
import json
from typing import Optional

from src.utils.logger import get_cool_logger
from src.features.news import NewsContent, BroadcastConfig, NewsBroadcaster
from src.features.news.models import BroadcastResult


logger = get_cool_logger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", os.urandom(32).hex())
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

# Store bot instance globally (will be set by main.py)
_bot_instance: Optional[discord.Bot] = None


def init_dashboard(bot: discord.Bot):
    """Initialize the dashboard with bot instance."""
    global _bot_instance
    _bot_instance = bot
    logger.info("Dashboard initialized with bot instance")


def get_bot() -> discord.Bot:
    """Get the bot instance."""
    if _bot_instance is None:
        raise RuntimeError("Dashboard not initialized. Call init_dashboard(bot) first.")
    return _bot_instance


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            flash('Please log in to access the dashboard.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Redirect to dashboard or login."""
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        password = request.form.get('password', '')
        expected_password = os.getenv('DASHBOARD_PASSWORD')
        
        if not expected_password:
            flash('Dashboard password not configured. Set DASHBOARD_PASSWORD in .env', 'error')
            logger.error("DASHBOARD_PASSWORD not set in environment")
            return render_template('login.html')
        
        if password == expected_password:
            session['authenticated'] = True
            session['login_time'] = datetime.utcnow().isoformat()
            session.permanent = True
            logger.info(f"Dashboard login successful from {request.remote_addr}")
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed login attempt from {request.remote_addr}")
            flash('Invalid password.', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page."""
    try:
        bot = get_bot()
        guilds = bot.guilds
        
        # Get guild info
        guild_info = []
        for guild in guilds:
            guild_info.append({
                'id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count,
                'icon_url': guild.icon.url if guild.icon else None
            })
        
        return render_template('dashboard.html', guilds=guild_info)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', guilds=[])


@app.route('/send-news', methods=['GET', 'POST'])
@login_required
def send_news():
    """News sending interface."""
    try:
        bot = get_bot()
        guilds = bot.guilds
        
        if request.method == 'GET':
            return render_template('send_news.html', guilds=guilds)
        
        # POST: Process news sending
        guild_id = int(request.form.get('guild_id', 0))
        content_type = request.form.get('content_type', 'plain')
        
        # Get content based on type
        news_contents = {}
        embed_json = None
        
        if content_type == 'plain':
            # Plain text multilingual
            news_contents['en'] = request.form.get('content_en', '').strip()
            news_contents['ru'] = request.form.get('content_ru', '').strip() or None
            news_contents['lt'] = request.form.get('content_lt', '').strip() or None
        elif content_type == 'json':
            # JSON embed format
            json_content = request.form.get('json_content', '').strip()
            try:
                embed_json = json.loads(json_content)
                # Extract description for fallback
                if 'embeds' in embed_json and embed_json['embeds']:
                    news_contents['en'] = embed_json.get('content', '') or embed_json['embeds'][0].get('description', '')
                else:
                    news_contents['en'] = embed_json.get('description', '') or embed_json.get('content', '')
            except json.JSONDecodeError as e:
                flash(f'Invalid JSON: {str(e)}', 'error')
                return render_template('send_news.html', guilds=guilds)
        
        if not news_contents.get('en') and not embed_json:
            flash('English content is required.', 'error')
            return render_template('send_news.html', guilds=guilds)
        
        # Create NewsContent
        content = NewsContent.from_dict({
            'en': news_contents.get('en', ''),
            'ru': news_contents.get('ru'),
            'lt': news_contents.get('lt'),
            'embed_json': embed_json
        })
        
        # Create BroadcastConfig
        config = BroadcastConfig(
            send_to_channels=request.form.get('send_to_channels') == 'on',
            send_to_users=request.form.get('send_to_users') == 'on',
            role_id=None,  # TODO: Add role selection
            send_ghost_ping=request.form.get('ghost_ping') == 'on',
            image_position=request.form.get('image_position', 'Before')
        )
        
        # Execute broadcast in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        broadcaster = NewsBroadcaster(
            bot=bot,
            guild_id=guild_id,
            content=content,
            config=config,
            ctx_for_footer=bot
        )
        
        result: BroadcastResult = loop.run_until_complete(broadcaster.broadcast())
        loop.close()
        
        # Show results
        flash(
            f'News sent! Success: {result.success_count}, Failed: {result.fail_count}, '
            f'Duration: {result.duration_seconds:.2f}s',
            'success' if result.fail_count == 0 else 'warning'
        )
        
        logger.info(
            f"Dashboard broadcast completed: {result.success_count} sent, "
            f"{result.fail_count} failed from {request.remote_addr}"
        )
        
        return redirect(url_for('send_news'))
        
    except Exception as e:
        logger.error(f"Send news error: {e}", exc_info=True)
        flash(f'Error: {str(e)}', 'error')
        return render_template('send_news.html', guilds=[])


@app.route('/api/preview', methods=['POST'])
@login_required
def api_preview():
    """API endpoint to preview news."""
    try:
        data = request.get_json()
        
        # Parse content
        content_type = data.get('content_type', 'plain')
        embed_json = None
        
        if content_type == 'json':
            json_content = data.get('json_content', '')
            try:
                embed_json = json.loads(json_content)
            except json.JSONDecodeError as e:
                return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400
        
        # Return preview info
        preview_data = {
            'valid': True,
            'type': 'webhook' if (embed_json and 'embeds' in embed_json) else 'embed' if embed_json else 'plain',
            'content_preview': data.get('content_en', '')[:200],
        }
        
        if embed_json:
            if 'embeds' in embed_json:
                preview_data['embed_count'] = len(embed_json.get('embeds', []))
                preview_data['has_content'] = bool(embed_json.get('content'))
            else:
                preview_data['embed_count'] = 1
        
        return jsonify(preview_data)
        
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/guilds')
@login_required
def api_guilds():
    """API endpoint to get guild information."""
    try:
        bot = get_bot()
        guilds_data = []
        
        for guild in bot.guilds:
            guilds_data.append({
                'id': guild.id,
                'name': guild.name,
                'member_count': guild.member_count,
                'icon_url': guild.icon.url if guild.icon else None
            })
        
        return jsonify({'guilds': guilds_data})
        
    except Exception as e:
        logger.error(f"API guilds error: {e}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """404 error handler."""
    return render_template('error.html', error='Page not found', code=404), 404


@app.errorhandler(500)
def internal_error(e):
    """500 error handler."""
    logger.error(f"Internal error: {e}")
    return render_template('error.html', error='Internal server error', code=500), 500


def run_dashboard(host='127.0.0.1', port=5000, debug=False):
    """Run the dashboard server."""
    logger.info(f"Starting dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
