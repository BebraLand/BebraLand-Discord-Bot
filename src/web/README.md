# 🎮 BebraLand News Dashboard

A secure, web-based interface for broadcasting news to your Discord server. Send beautiful announcements with rich embeds, multilingual support, and full Discord webhook format compatibility.

![Dashboard Preview](https://img.shields.io/badge/Status-Ready-brightgreen) ![Security](https://img.shields.io/badge/Security-Password%20Protected-blue) ![License](https://img.shields.io/badge/License-MIT-orange)

---

## ✨ Features

### 🔐 Secure Access
- Password-protected authentication
- Session-based login (12-hour timeout)
- Secure cookie management
- Activity logging

### 📢 Powerful Broadcasting
- **Plain Text Mode**: Multilingual support (EN/RU/LT)
- **JSON Mode**: Full Discord webhook format
  - Single or multiple embeds (up to 10)
  - Rich formatting with fields, colors, images
  - Content text + embeds combo
  - Full markdown support

### 🎯 Flexible Targeting
- Send to language-specific channels
- DM all guild members or specific roles
- Ghost ping support (@everyone)
- Multi-guild support

### 🎨 Modern Interface
- Clean, responsive design
- Real-time JSON validation
- Tab-based content switching
- Confirmation dialogs for safety
- Instant feedback with flash messages

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install flask
```

### 2. Configure
Add to `.env`:
```env
DASHBOARD_PASSWORD=your_secure_password
DASHBOARD_SECRET_KEY=random_string_for_sessions
```

### 3. Integrate with Bot
Add to `main.py`:
```python
from src.web import init_dashboard, run_dashboard
import threading

@bot.event
async def on_ready():
    # Initialize dashboard
    init_dashboard(bot)
    
    # Start in separate thread
    threading.Thread(
        target=run_dashboard,
        kwargs={'host': '127.0.0.1', 'port': 5000},
        daemon=True
    ).start()
```

### 4. Access Dashboard
Open: http://localhost:5000

---

## 📸 Screenshots

### Login Page
```
┌─────────────────────────────┐
│   🔐 Dashboard Login        │
│                             │
│   Password: [___________]   │
│                             │
│   [       Login       ]     │
└─────────────────────────────┘
```

### Send News Interface
```
┌─────────────────────────────────────────┐
│  📢 Send News Broadcast                 │
├─────────────────────────────────────────┤
│  Guild: [Select...]                     │
│                                         │
│  Format: [📝 Plain Text] [🎨 JSON]      │
│                                         │
│  Content:                               │
│  ┌───────────────────────────────────┐ │
│  │ Your news here...                 │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ☑ Send to channels                    │
│  ☐ Send to all users                   │
│  ☑ Ghost ping                          │
│                                         │
│  [🚀 Send Now]  [Cancel]                │
└─────────────────────────────────────────┘
```

---

## 🎨 Supported Formats

### Plain Text
```
English: Your announcement here
Russian: Ваше объявление здесь
Lithuanian: Jūsų pranešimas čia
```

### Single Embed
```json
{
    "title": "Announcement",
    "description": "Your news",
    "color": 5814783
}
```

### Webhook Format
```json
{
    "content": "**Breaking News!** 🎉",
    "embeds": [
        {
            "title": "Update",
            "description": "Details here",
            "fields": [
                {"name": "Field", "value": "Value"}
            ]
        }
    ]
}
```

---

## 🔒 Security

### Authentication
- Required password from environment variable
- Brute force protection (logged attempts)
- Secure session management
- Auto-logout after 12 hours

### Network Security
- Default: Localhost only (127.0.0.1)
- Optional: Remote access with proper HTTPS setup
- Session cookies with secret key
- CSRF protection via Flask sessions

### Best Practices
1. Use strong, random password
2. Keep dashboard on localhost or behind VPN
3. Use HTTPS for remote access (reverse proxy)
4. Monitor logs for suspicious activity
5. Rotate passwords periodically

---

## 📝 Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DASHBOARD_PASSWORD` | **Yes** | - | Login password |
| `DASHBOARD_SECRET_KEY` | No | Auto-generated | Session secret |
| `DASHBOARD_HOST` | No | `127.0.0.1` | Host to bind to |
| `DASHBOARD_PORT` | No | `5000` | Port to listen on |
| `DASHBOARD_DEBUG` | No | `False` | Debug mode |

### Security Recommendations

**Development:**
```env
DASHBOARD_HOST=127.0.0.1
DASHBOARD_DEBUG=True
```

**Production (Local):**
```env
DASHBOARD_HOST=127.0.0.1
DASHBOARD_DEBUG=False
DASHBOARD_SECRET_KEY=your_random_hex_string
```

**Production (Remote):**
```env
DASHBOARD_HOST=0.0.0.0  # Only with HTTPS!
DASHBOARD_PORT=8080
DASHBOARD_DEBUG=False
# Use nginx/apache reverse proxy with SSL
```

---

## 🛠️ Advanced Features

### JSON Validation
- Real-time syntax checking
- Format detection (single/webhook)
- Helpful error messages
- Embed/content preview

### Confirmation Dialogs
- DM to all users: Double confirmation
- Send confirmation: Final check
- Prevents accidental broadcasts

### Activity Logging
- Login attempts (IP, timestamp)
- Broadcast activity (success/fail counts)
- Error tracking
- Security events

---

## 🔗 Integration with Existing Features

### Works With
- ✅ Scheduled broadcasts
- ✅ Multilingual system
- ✅ All embed formats
- ✅ Image attachments (via Discord command)
- ✅ Ghost ping
- ✅ Role-based targeting (coming soon)

### Compatible Formats
- Plain text multilingual
- Single embed JSON
- Webhook format (content + embeds)
- All Discord markdown

---

## 🐛 Troubleshooting

### Can't access dashboard
```bash
# Check if Flask is installed
pip show flask

# Check if port is available
netstat -an | findstr 5000  # Windows
lsof -i :5000               # Linux/Mac

# Check environment variables
echo $DASHBOARD_PASSWORD
```

### Can't login
- Verify `.env` file has `DASHBOARD_PASSWORD`
- Check for typos
- Restart bot after changing `.env`
- Check logs for error messages

### News not sending
- Verify bot permissions in target channels
- Check channel IDs in `config/constants.py`
- Review bot logs for errors
- Test with Discord command first

---

## 📚 Documentation

- **Setup Guide**: [DASHBOARD_SETUP.md](DASHBOARD_SETUP.md)
- **Format Guide**: [NEWS_FORMAT_GUIDE.md](NEWS_FORMAT_GUIDE.md)
- **Integration Example**: [DASHBOARD_INTEGRATION_EXAMPLE.py](DASHBOARD_INTEGRATION_EXAMPLE.py)

---

## 🎯 Use Cases

### Server Announcements
Send important updates to all members with rich formatting.

### Event Notifications
Beautiful event cards with dates, prizes, and registration info.

### Update Logs
Multi-embed format for changelog releases.

### Emergency Alerts
Quick broadcast to all members via DM.

### Multilingual Content
Automatically send correct language to each user.

---

## 🔮 Future Enhancements

- [ ] Role-based targeting UI
- [ ] Template library (save/load)
- [ ] Broadcast history viewer
- [ ] Schedule broadcasts from dashboard
- [ ] A/B testing support
- [ ] Analytics and metrics
- [ ] Mobile app
- [ ] Two-factor authentication

---

## 💡 Tips & Tricks

1. **Use Online Builders**: [Discohook](https://discohook.org/) for creating JSON
2. **Test First**: Preview in Discord before dashboard broadcast
3. **Save Templates**: Keep commonly-used JSON in a file
4. **Markdown Support**: Use Discord markdown in all text fields
5. **JSON Validation**: Always validate before sending
6. **Localhost Only**: Keep dashboard local unless using HTTPS

---

## 🤝 Contributing

Suggestions and improvements welcome! Consider:
- UI/UX enhancements
- Additional format support
- Security improvements
- Mobile responsiveness
- Accessibility features

---

## 📄 License

Part of BebraLand Discord Bot project.

---

## 🆘 Support

Need help?
1. Check documentation in `/docs`
2. Review logs for errors
3. Test with simple plain text first
4. Verify environment configuration

---

## 🎉 Credits

Built with:
- **Flask** - Web framework
- **Discord.py** - Discord integration
- **CSS** - Custom styling
- **JavaScript** - Interactive features

---

**Made with ❤️ for BebraLand Community**
