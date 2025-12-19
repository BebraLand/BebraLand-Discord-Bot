# Temporary Voice Channels

A comprehensive temporary voice channel system for Discord that allows users to create and manage their own voice channels.

## Features

### Automatic Channel Creation
- Users join the lobby voice channel (configured in `TEMP_VOICE_CHANNEL_LOBBY_ID`)
- Bot automatically creates a personal voice channel
- User is moved to their new channel
- Channel is stored in database for restart-proof operation

### Channel Permissions
- **@everyone role**: Restricted by default (cannot see or connect)
- **DEFAULT_USER_ROLE_ID**: Can see and connect by default
- **Channel owner**: Full control over their channel

### Control Panel

Each temp voice channel gets an embedded control panel with the following buttons:

#### Main Controls
- **🔒 Lock**: Users can see the channel but cannot connect
- **🔓 Unlock**: Users can see and connect to the channel
- **✅ Permit**: Allow specific users or roles to join (even when locked)
- **❌ Reject**: Block specific users or roles from joining
- **📨 Invite**: Send a DM invitation to a user (can be disabled via `TEMP_VOICE_INVITE_ENABLED`)
- **👻 Ghost**: Make the channel invisible to everyone except those with special permissions
- **👁️ Unghost**: Make the channel visible again
- **🔄 Transfer**: Transfer ownership to another user
- **⚙️ Settings**: Open advanced settings menu

#### Settings Panel
- **✏️ Name**: Change the channel name
- **👥 Limit**: Set user limit (0 for unlimited, max 99)
- **🎵 Bitrate**: Adjust audio quality (can be disabled via `TEMP_VOICE_BITRATE_SETTINGS_ENABLED`)
  - Automatically adjusts max bitrate based on server boost level
  - Level 0: 96 kbps max
  - Level 1: 128 kbps max
  - Level 2: 256 kbps max
  - Level 3: 384 kbps max
- **🌍 Region**: Select voice region (can be disabled via `TEMP_VOICE_REGION_SETTINGS_ENABLED`)
- **🔞 NSFW**: Toggle NSFW status

### Ownership Management

#### Manual Transfer
- Owner can transfer ownership to any user via the Transfer button

#### Automatic Transfer
- When the owner leaves but others remain in the channel:
  - Ownership automatically transfers to the next person
  - New owner is notified in chat
  - Control panel updates with new permissions

#### Channel Cleanup
- When channel becomes empty:
  - Deletion is scheduled after `DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS`
  - If someone rejoins before deletion, the timer is cancelled
  - Channel and database entry are removed together

## Configuration

Add these constants to `config/constants.py`:

```python
# Required
TEMP_VOICE_CHANNEL_CATEGORY_ID = 1234567890  # Category where temp channels are created
TEMP_VOICE_CHANNEL_LOBBY_ID = 1234567890     # Lobby channel that triggers creation
DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS = 15  # Delay before deleting empty channels
DEFAULT_USER_ROLE_ID = 1234567890             # Role allowed to see/connect to channels

# Optional Features
TEMP_VOICE_INVITE_ENABLED = True              # Enable/disable invite button
TEMP_VOICE_BITRATE_SETTINGS_ENABLED = True    # Enable/disable bitrate settings
TEMP_VOICE_REGION_SETTINGS_ENABLED = False    # Enable/disable region settings

# Limits
TEMP_VOICE_MIN_BITRATE = 8000                 # Minimum bitrate in bps
TEMP_VOICE_MAX_BITRATE = 96000                # Maximum bitrate in bps (auto-adjusts for boost)
TEMP_VOICE_DEFAULT_LIMIT = 0                  # Default user limit (0 = unlimited)
TEMP_VOICE_MAX_LIMIT = 99                     # Maximum user limit
```

## Database

The system uses the `temp_voice_channels` table with the following schema:

```sql
- channel_id (Primary Key)
- owner_id
- guild_id
- control_message_id
- created_at
- permitted_users (JSON array)
- permitted_roles (JSON array)
- rejected_users (JSON array)
- rejected_roles (JSON array)
```

## Restart-Proof Operation

The system is fully restart-proof:

1. **On Startup**:
   - Loads all temp channels from database
   - Re-registers persistent views for control panels
   - Cleans up orphaned database entries
   - Schedules deletion for empty channels

2. **During Operation**:
   - All permission changes are saved to database
   - Control panel state persists across restarts
   - Ownership transfers are immediately saved

3. **On Shutdown**:
   - Channels remain in Discord
   - Database maintains all state
   - Resumes operation seamlessly on restart

## File Structure

```
src/features/temp_voice_channels/
├── views/
│   ├── __init__.py
│   ├── TempVoiceControlView.py     # Main control panel with lock, unlock, permit, etc.
│   └── TempVoiceSettingsView.py    # Settings panel for name, limit, bitrate, etc.
└── utils.py                         # Helper functions for channel management

src/events/
└── on_voice_state_update.py         # Event handler for voice state changes

src/storage/
├── models.py                        # TempVoiceChannel database model
└── sqlalchemy_storage.py            # Database operations
```

## How It Works

### User Flow

1. User joins lobby channel (`TEMP_VOICE_CHANNEL_LOBBY_ID`)
2. Bot creates a new voice channel with user's name
3. Bot moves user to their new channel
4. Control panel embed is sent to the channel
5. User can customize their channel using the buttons
6. When user leaves and channel is empty, it's deleted after configured delay

### Permission System

The system uses Discord's permission overwrites:

- **Lock**: `connect=False, view_channel=True` for DEFAULT_USER_ROLE
- **Unlock**: `connect=True, view_channel=True` for DEFAULT_USER_ROLE
- **Ghost**: `view_channel=False` for DEFAULT_USER_ROLE
- **Permit**: Adds specific `view_channel=True, connect=True` override for user/role
- **Reject**: Adds specific `view_channel=False, connect=False` override for user/role

### Ownership Transfer Logic

```python
1. Owner leaves channel
2. Check if channel has other members
3. If yes:
   - Get first member in channel
   - Update database with new owner_id
   - Update channel name if it contains old owner's name
   - Update control panel view with new owner permissions
   - Notify new owner in chat
4. If no:
   - Schedule channel deletion
```

## Error Handling

- Failed channel creation: Channel is immediately deleted
- Failed user move: Channel is deleted and database entry removed
- Database errors: Logged but don't crash the bot
- Missing permissions: User receives error message
- Invalid IDs: User receives validation error

## Security

- Only channel owner can use most controls
- Transfer ownership requires valid user ID
- Permit/Reject validates user/role existence
- NSFW toggle restricted to owner
- All database operations use parameterized queries

## Performance

- Persistent views don't timeout
- Database queries are asynchronous
- Channel deletion is deferred to prevent race conditions
- Batch cleanup on startup for orphaned channels
- Efficient permission caching

## Future Enhancements

Potential features to add:
- Channel templates/presets
- Scheduled auto-deletion
- Activity-based auto-lock
- Whitelist/blacklist management UI
- Channel cloning
- Usage statistics
- Multi-owner support
