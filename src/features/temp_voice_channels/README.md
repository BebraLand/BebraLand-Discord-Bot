# Temporary Voice Channels Feature

This feature allows users to create temporary voice channels on-demand by joining a lobby channel.

## Features

### Core Functionality
- **Auto Channel Creation**: When a user joins the configured lobby channel, a temporary voice channel is automatically created and they are moved to it
- **Automatic Cleanup**: Empty channels are automatically deleted after a configurable delay (default 15 seconds)
- **Owner Transfer**: If the owner leaves, ownership is automatically transferred to the next user in the channel
- **Database Persistence**: All channels are tracked in the database, making the feature restart-proof

### Control Panel Features
The control panel provides the following options:
- 🔒 **Lock** - Prevent new users from joining (they can see but not connect)
- 🔓 **Unlock** - Allow users to join again
- ✅ **Permit** - Allow specific users to join your locked channel
- ❌ **Reject** - Block specific users from your channel
- 📧 **Invite** - Send a DM invitation to a user (configurable)
- 👻 **Ghost** - Make your channel invisible to others
- 👁️ **Unghost** - Make your channel visible again
- 👑 **Transfer** - Transfer ownership to another user

### Settings Panel Features (Configurable)
The settings panel allows channel customization:
- ✏️ **Name** - Change the channel name
- 👥 **User Limit** - Set maximum users (0 = unlimited)
- 🎵 **Bitrate** - Adjust audio quality
- 🌍 **Region** - Select voice server region (configurable)
- 🔞 **Toggle NSFW** - Enable/disable NSFW mode

## Configuration

Add these constants to `config/constants.py`:

```python
# Temp voice channel IDs
TEMP_VOICE_CHANNEL_CATEGORY_ID = 1451282373927768155  # Category where temp channels are created
TEMP_VOICE_CHANNEL_LOBBY_ID = 1451282476159729876     # Lobby channel users join to create a temp channel
DEFAULT_USER_ROLE_ID = 1451283495899889967             # Role that can see/connect to temp channels

# Cleanup settings
DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS = 15   # Delay before deleting empty channels

# Feature flags
TEMP_VOICE_INVITE_ENABLED = True          # Enable/disable invite button
TEMP_VOICE_SETTINGS_ENABLED = True        # Enable/disable settings panel
TEMP_VOICE_REGION_ENABLED = False         # Enable/disable region selection

# Voice channel limits (adjust based on your server's boost level)
TEMP_VOICE_MAX_BITRATE = 96000           # Max bitrate in bps (96k for non-boosted)
TEMP_VOICE_MAX_USER_LIMIT = 99           # Maximum users in a channel
TEMP_VOICE_DEFAULT_USER_LIMIT = 0        # Default user limit (0 = unlimited)
```

## Setup Instructions

1. **Create Discord Channels**:
   - Create a category for temporary voice channels
   - Create a lobby voice channel in that category
   - Note their IDs and add to constants

2. **Configure Permissions**:
   - Set `@everyone` role to NOT see the temp voice category
   - Create or identify a role that should have access (DEFAULT_USER_ROLE_ID)
   - Ensure the bot has Manage Channels, Move Members, and Manage Permissions in the category

3. **Adjust Settings**:
   - Set `TEMP_VOICE_MAX_BITRATE` based on your server boost level:
     - No boost: 96000 (96 kbps)
     - Level 1: 128000 (128 kbps)
     - Level 2: 256000 (256 kbps)
     - Level 3: 384000 (384 kbps)
   - Enable/disable features as needed using the feature flags

## Database Schema

The feature adds a `temp_voice_channels` table:

```sql
CREATE TABLE temp_voice_channels (
    channel_id BIGINT PRIMARY KEY,
    owner_id VARCHAR(255) NOT NULL,
    guild_id BIGINT NOT NULL,
    created_at FLOAT NOT NULL,
    control_message_id BIGINT,
    permitted_users TEXT,  -- JSON array
    rejected_users TEXT,   -- JSON array
    is_locked INTEGER DEFAULT 0,
    is_ghost INTEGER DEFAULT 0
);
```

## How It Works

1. **User Joins Lobby**: When a user joins `TEMP_VOICE_CHANNEL_LOBBY_ID`
2. **Channel Created**: Bot creates a new voice channel with:
   - Owner permissions (full control)
   - Hidden from @everyone
   - Visible to DEFAULT_USER_ROLE_ID
3. **User Moved**: User is automatically moved to the new channel
4. **Control Panels Sent**: Bot sends control panel and settings panel embeds to the channel
5. **User Leaves**: When users leave:
   - If owner leaves and others remain: ownership transfers
   - If channel becomes empty: scheduled for deletion after delay
6. **Cleanup**: After the delay, empty channels are deleted and removed from database

## Persistence

The feature is fully restart-proof:
- All channel data is stored in the database
- Scheduled deletions are persisted
- Views are re-registered on bot startup
- Ownership and permissions are maintained across restarts

## Files Structure

```
src/
├── events/
│   └── on_voice_state_update.py          # Main event handler
├── features/
│   └── temp_voice_channels/
│       ├── __init__.py
│       ├── channel_manager.py             # Core logic (create, cleanup, transfer)
│       └── view/
│           ├── __init__.py
│           ├── TempVoiceControlPanel.py   # Control panel UI
│           └── TempVoiceSettingsPanel.py  # Settings panel UI
├── storage/
│   ├── models.py                          # Database models (+TempVoiceChannel)
│   ├── base.py                            # Storage protocol
│   └── sqlalchemy_storage.py              # Implementation
└── utils/
    ├── scheduler.py                       # Task scheduler (+delete_temp_voice_channel)
    └── register_persistent_temp_voice_views.py  # View registration
```

## Troubleshooting

**Channels not being created:**
- Check bot has Manage Channels permission in the category
- Verify TEMP_VOICE_CHANNEL_CATEGORY_ID and TEMP_VOICE_CHANNEL_LOBBY_ID are correct
- Check bot logs for errors

**Users can't be moved:**
- Ensure bot has Move Members permission
- Check that the bot's role is high enough in the hierarchy

**Views not working after restart:**
- Ensure `register_persistent_temp_voice_views` is called in `on_ready`
- Check database connection is working

**Channels not being deleted:**
- Verify scheduler is initialized properly
- Check DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS is set
- Look for scheduler errors in logs

## Inspired By

This feature replicates functionality from popular Discord voice bots:
- [VoiceMaster](https://voicemaster.xyz/)
- [TempVoice](https://tempvoice.xyz/)
