# News Dashboard Setup Guide

## 🚀 Quick Start

### 1. Install Required Dependencies

```bash
pip install flask
```

Or add to your `requirements.txt`:
```
flask>=3.0.0
```

### 2. Configure Environment Variables

Add to your `.env` file:

```env
# Dashboard Authentication (REQUIRED)
DASHBOARD_PASSWORD=your_secure_password_here

# Dashboard Secret Key (OPTIONAL - auto-generated if not set)
DASHBOARD_SECRET_KEY=random_string_for_session_security

# Dashboard Settings (OPTIONAL)
DASHBOARD_HOST=127.0.0.1  # Default: 127.0.0.1 (localhost only)
DASHBOARD_PORT=5000        # Default: 5000
DASHBOARD_DEBUG=False      # Default: False (set True for development)
```

### 3. Start the Dashboard

Add to your `main.py`:

```python
# Add this import at the top
from src.web import init_dashboard, run_dashboard
import threading

# After bot initialization, add:
async def on_ready():
    # ... existing on_ready code ...
    
    # Initialize dashboard with bot instance
    init_dashboard(bot)
    
    # Start dashboard in separate thread
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
    
    logger.info("Dashboard started on http://{}:{}".format(
        os.getenv('DASHBOARD_HOST', '127.0.0.1'),
        os.getenv('DASHBOARD_PORT', 5000)
    ))
```

### 4. Access the Dashboard

1. Start your bot
2. Open browser: http://localhost:5000
3. Login with your `DASHBOARD_PASSWORD`
4. Send news broadcasts!

---

## 🔒 Security Features

### Password Authentication
- Required password from environment variable
- Session-based authentication with 12-hour timeout
- Secure session cookies with secret key

### Access Control
- All routes require authentication (except login)
- Failed login attempts are logged
- Session management with automatic expiration

### Network Security
- Default: Localhost only (127.0.0.1)
- For remote access: Change `DASHBOARD_HOST` to `0.0.0.0`
- **Recommended**: Use reverse proxy (nginx) with HTTPS for remote access

---

## 📱 Features

### Dashboard Homepage
- View bot status
- See all connected guilds
- Guild member counts
- Quick access to send news

### Send News Interface
- **Plain Text Mode**: Multilingual support (EN/RU/LT)
- **JSON Mode**: Full Discord webhook format
  - Single embeds
  - Multiple embeds (up to 10)
  - Rich formatting with fields, images, etc.
  - Real-time JSON validation

### Broadcast Options
- Send to language-specific channels
- Send to all users via DM
- Ghost ping (@everyone)
- Image position control

### User Experience
- Clean, modern interface
- Tab-based content switching
- JSON validator
- Confirmation dialogs for critical actions
- Flash messages for feedback
- Mobile-responsive design

---

## 🎨 Supported Formats

### 1. Plain Text (Multilingual)
Simply fill in the text fields for each language.

### 2. Single Embed JSON
```json
{
    "title": "Announcement",
    "description": "Your news",
    "color": 5814783
}
```

### 3. Webhook Format (Content + Embeds)
```json
{
    "content": "Text with **markdown**!",
    "embeds": [
        {
            "title": "Title",
            "description": "Description",
            "fields": [
                {"name": "Field", "value": "Value"}
            ]
        }
    ]
}
```

---

## 🔧 Advanced Configuration

### Custom Host/Port

For remote access (⚠️ **Use HTTPS in production**):

```env
DASHBOARD_HOST=0.0.0.0  # Allow external connections
DASHBOARD_PORT=8080     # Custom port
```

### Reverse Proxy Setup (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Debug Mode

Enable detailed error messages (development only):

```env
DASHBOARD_DEBUG=True
```

---

## 🛡️ Security Best Practices

1. **Strong Password**: Use a long, random password
   ```bash
   # Generate secure password
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Secret Key**: Set a random secret key
   ```bash
   # Generate secret key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **HTTPS Only**: Never expose dashboard over HTTP in production

4. **Firewall**: Restrict access by IP if possible
   ```bash
   # Example: iptables rule for specific IP
   iptables -A INPUT -p tcp --dport 5000 -s YOUR_IP -j ACCEPT
   iptables -A INPUT -p tcp --dport 5000 -j DROP
   ```

5. **Logging**: Monitor `dashboard.log` for suspicious activity

6. **VPN**: Access dashboard through VPN for additional security

---

## 📊 Logging

Dashboard activities are logged:
- Login attempts (success/failure)
- News broadcasts (with results)
- Errors and exceptions

Check logs in your bot's log output.

---

## 🐛 Troubleshooting

### Dashboard won't start
- Check if port 5000 is available
- Verify Flask is installed: `pip install flask`
- Check environment variables are set

### Can't login
- Verify `DASHBOARD_PASSWORD` is set in `.env`
- Check for typos in password
- Restart bot after changing `.env`

### News not sending
- Check bot has permissions in target channels
- Verify channel IDs in constants
- Check bot logs for errors

### JSON validation fails
- Use online JSON validators
- Check for trailing commas
- Verify quotes are double quotes (")

---

## 🔗 Useful Tools

- **Discohook**: https://discohook.org/
- **Embed Builder**: https://glitchii.github.io/embedbuilder/
- **JSON Validator**: https://jsonlint.com/
- **Embed Visualizer**: https://leovoel.github.io/embed-visualizer/

---

## 📝 Example Environment File

```env
# Bot Configuration
DISCORD_TOKEN=your_bot_token_here

# Dashboard Configuration
DASHBOARD_PASSWORD=super_secure_password_123
DASHBOARD_SECRET_KEY=random_hex_string_for_sessions
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=5000
DASHBOARD_DEBUG=False

# News Channels (from your config)
NEWS_ENGLISH_CHANNEL_ID=123456789
NEWS_RUSSIAN_CHANNEL_ID=123456790
NEWS_LITHUANIAN_CHANNEL_ID=123456791
```

---

## 🎯 Quick Tips

1. **Test First**: Use preview mode in Discord before using dashboard
2. **JSON Builder**: Use online tools to build complex embeds
3. **Backup**: Save frequently-used JSON templates
4. **Markdown**: All text fields support Discord markdown
5. **Safety**: Always confirm before sending to all users

---

## 📞 Support

If you encounter issues:
1. Check the logs
2. Verify environment variables
3. Test with simple plain text first
4. Review the NEWS_FORMAT_GUIDE.md for content formatting
