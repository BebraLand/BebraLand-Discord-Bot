# Temp Voice Channels - Quick Start Guide

## What Was Implemented

A complete temporary voice channel system with:

✅ **Automatic channel creation** when users join the lobby  
✅ **Full control panel** with 9+ interactive buttons  
✅ **Database persistence** for restart-proof operation  
✅ **Ownership management** with auto-transfer when owner leaves  
✅ **Advanced settings** for name, limit, bitrate, region, NSFW  
✅ **Permission system** for lock, unlock, permit, reject, ghost  
✅ **DM invitations** (toggleable via constants)  
✅ **Automatic cleanup** when channels are empty  

## Files Created

### Core Files
- `src/features/temp_voice_channels/utils.py` - Channel management utilities
- `src/features/temp_voice_channels/__init__.py` - Package initialization
- `src/features/temp_voice_channels/README.md` - Full documentation

### Views
- `src/features/temp_voice_channels/views/TempVoiceControlView.py` - Main control panel
- `src/features/temp_voice_channels/views/TempVoiceSettingsView.py` - Settings panel
- `src/features/temp_voice_channels/views/__init__.py` - Views package

### Events
- `src/events/on_voice_state_update.py` - Voice state change handler

### Database
- Updated `src/storage/models.py` - Added TempVoiceChannel model
- Updated `src/storage/base.py` - Added TempVoiceChannelStorage protocol
- Updated `src/storage/sqlalchemy_storage.py` - Implemented storage methods

### Configuration
- Updated `config/constants.py` - Added all configuration constants
- Updated `main.py` - Added temp channel restoration on startup

## Configuration Required

Before using, configure these constants in `config/constants.py`:

```python
TEMP_VOICE_CHANNEL_CATEGORY_ID = YOUR_CATEGORY_ID
TEMP_VOICE_CHANNEL_LOBBY_ID = YOUR_LOBBY_CHANNEL_ID
DEFAULT_USER_ROLE_ID = YOUR_DEFAULT_ROLE_ID
```

## How to Use

1. **Setup Discord**:
   - Create a category for temp channels
   - Create a lobby voice channel
   - Set the IDs in constants

2. **Run the bot**:
   - Database tables will be created automatically
   - Lobby channel will become active

3. **Users join lobby**:
   - Bot creates personal channel
   - User is moved to new channel
   - Control panel appears

4. **Users customize**:
   - Use buttons to control channel
   - Settings panel for advanced options
   - Transfer ownership or leave to auto-transfer

## Features Summary

### Main Control Panel Buttons

| Button | Function | Owner Only |
|--------|----------|-----------|
| 🔒 Lock | Users see but can't connect | ✅ |
| 🔓 Unlock | Users can see and connect | ✅ |
| ✅ Permit | Allow specific users/roles | ✅ |
| ❌ Reject | Block specific users/roles | ✅ |
| 📨 Invite | Send DM invite to user | ✅ |
| 👻 Ghost | Make channel invisible | ✅ |
| 👁️ Unghost | Make channel visible | ✅ |
| 🔄 Transfer | Transfer ownership | ✅ |
| ⚙️ Settings | Open settings panel | ✅ |

### Settings Panel Options

| Setting | Function | Toggleable |
|---------|----------|-----------|
| ✏️ Name | Change channel name | No |
| 👥 Limit | Set user limit (0-99) | No |
| 🎵 Bitrate | Adjust audio quality | Yes* |
| 🌍 Region | Select voice region | Yes* |
| 🔞 NSFW | Toggle NSFW status | No |

*Via constants: `TEMP_VOICE_BITRATE_SETTINGS_ENABLED`, `TEMP_VOICE_REGION_SETTINGS_ENABLED`

## Database Schema

```sql
CREATE TABLE temp_voice_channels (
    channel_id BIGINT PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    control_message_id BIGINT,
    created_at FLOAT NOT NULL,
    permitted_users JSON,
    permitted_roles JSON,
    rejected_users JSON,
    rejected_roles JSON
);
```

## Automatic Features

### On Bot Startup
- Restores all temp channels from database
- Re-registers persistent views
- Cleans up orphaned entries
- Schedules deletion for empty channels

### On Owner Leave
- If others in channel: Auto-transfer to first member
- If empty: Schedule deletion after configured delay
- Notify new owner in chat

### On Channel Empty
- Wait `DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS`
- Delete channel if still empty
- Remove from database
- Cancel if someone rejoins

## Security & Permissions

- Only owner can use control buttons
- Permission changes validate user/role existence
- Database uses parameterized queries
- Error messages are user-friendly
- Persistent views never timeout

## Customization Options

### Toggle Features via Constants

```python
TEMP_VOICE_INVITE_ENABLED = False          # Disable invite button
TEMP_VOICE_BITRATE_SETTINGS_ENABLED = False # Disable bitrate settings
TEMP_VOICE_REGION_SETTINGS_ENABLED = False  # Disable region settings
```

### Adjust Limits

```python
TEMP_VOICE_MIN_BITRATE = 8000              # Min: 8 kbps
TEMP_VOICE_MAX_BITRATE = 96000             # Max: 96 kbps (auto-adjusts for boost)
TEMP_VOICE_DEFAULT_LIMIT = 0               # Default user limit
TEMP_VOICE_MAX_LIMIT = 99                  # Max user limit
DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS = 15  # Cleanup delay
```

## Next Steps

1. ✅ All code is implemented
2. 🔧 Configure your constants
3. 🗄️ Database tables will auto-create on first run
4. 🚀 Start the bot
5. 🎮 Test by joining the lobby channel

## Troubleshooting

**Channel not created?**
- Check lobby channel ID is correct
- Verify bot has permission to create channels
- Check category ID exists and bot can access it

**Buttons not working?**
- Views are persistent and survive restarts
- Check bot has necessary permissions
- Verify database connection is working

**Permissions not applying?**
- Ensure DEFAULT_USER_ROLE_ID is correct
- Check bot role is above the roles it's managing
- Verify bot has "Manage Channels" permission

**Database errors?**
- Tables auto-create on first run
- Check database connection in .env
- Look for migration errors in logs

## Support

See [README.md](README.md) for full documentation including:
- Detailed feature explanations
- Permission system details
- Error handling
- Performance considerations
- Future enhancement ideas
