# 🎯 News Dashboard - Quick Setup Checklist

Follow these steps to get the dashboard running in minutes!

## ✅ Step 1: Install Flask
```bash
pip install flask
```

## ✅ Step 2: Configure Environment
Add to your `.env` file:
```env
# REQUIRED: Set a strong password
DASHBOARD_PASSWORD=your_secure_password_here

# OPTIONAL: Set a secret key (auto-generated if not set)
DASHBOARD_SECRET_KEY=random_hex_string_here

# OPTIONAL: Custom host/port
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=5000
DASHBOARD_DEBUG=False
```

**Generate secure values:**
```bash
# Generate password (copy the output)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate secret key (copy the output)
python -c "import secrets; print(secrets.token_hex(32))"
```

## ✅ Step 3: Integrate with Bot
Open `main.py` and add these imports at the top:
```python
from src.web import init_dashboard, run_dashboard
import threading
import os
```

Then add this to your `on_ready` event:
```python
@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")
    
    # ... your existing code ...
    
    # Initialize dashboard
    try:
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
        
        logger.info(f"🌐 Dashboard: http://127.0.0.1:5000")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
```

## ✅ Step 4: Start Bot
```bash
python main.py
```

Look for this in logs:
```
🌐 Dashboard: http://127.0.0.1:5000
```

## ✅ Step 5: Access Dashboard
1. Open browser: http://localhost:5000
2. Login with your `DASHBOARD_PASSWORD`
3. Click "Send News"
4. Fill in the form and broadcast!

---

## 🎉 You're Done!

The dashboard is now running. You can:
- ✅ Send news in plain text or JSON format
- ✅ Support webhook format with multiple embeds
- ✅ Target specific guilds
- ✅ Choose channels or DMs
- ✅ Use ghost ping
- ✅ Real-time JSON validation

---

## 🔍 Verification

Check that everything works:

1. **Dashboard Loads**: Open http://localhost:5000
   - [ ] Login page appears
   - [ ] No errors in console

2. **Authentication Works**: Enter password
   - [ ] Redirects to dashboard
   - [ ] Shows connected guilds

3. **Send News Works**: Try a simple broadcast
   - [ ] Form loads correctly
   - [ ] Can select guild
   - [ ] JSON validation works
   - [ ] Broadcast succeeds

---

## 🆘 Troubleshooting

### "Can't access dashboard"
```bash
# Check Flask is installed
pip show flask

# Check port 5000 is free
netstat -an | findstr 5000  # Windows
lsof -i :5000               # Linux/Mac
```

### "Wrong password"
- Check `.env` file exists in bot root directory
- Verify `DASHBOARD_PASSWORD` is set
- No quotes needed around the value
- Restart bot after changing `.env`

### "Dashboard not starting"
- Check bot logs for errors
- Ensure threading import is added
- Verify init_dashboard is called before run_dashboard

---

## 📚 Next Steps

1. **Read Format Guide**: [NEWS_FORMAT_GUIDE.md](NEWS_FORMAT_GUIDE.md)
2. **Try Webhook Format**: Use https://discohook.org/ to create JSON
3. **Secure Setup**: Review [DASHBOARD_SETUP.md](DASHBOARD_SETUP.md)
4. **Advanced Features**: Explore scheduling, templates

---

## 💾 Files Created

```
src/web/
├── __init__.py              # Module exports
├── app.py                   # Flask application
├── README.md               # Dashboard documentation
├── templates/
│   ├── base.html           # Base template
│   ├── login.html          # Login page
│   ├── dashboard.html      # Main dashboard
│   ├── send_news.html      # News form
│   └── error.html          # Error pages
└── static/                 # (future: CSS/JS files)

docs/
├── DASHBOARD_SETUP.md      # Detailed setup guide
├── DASHBOARD_INTEGRATION_EXAMPLE.py  # Integration code
└── NEWS_FORMAT_GUIDE.md    # Content formatting

```

---

## 🎯 Quick Command Reference

```bash
# Install
pip install flask

# Generate password
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Start bot (dashboard auto-starts)
python main.py

# Access dashboard
# Open: http://localhost:5000
```

---

**That's it! Enjoy your new News Dashboard! 🎉**
