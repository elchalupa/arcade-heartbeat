# arcade-heartbeat

A stream copilot that nudges small creators to engage with their audience.

Heartbeat monitors your Twitch chat and sends Windows toast notifications with contextual prompts. Think of it as the person holding up cue cards — it watches the room and whispers suggestions in your ear.

**Philosophy:** The tool never speaks for you. It coaches you to speak. The goal is to build the habit of engagement, not replace it.

## Features

**Chat Silence Detection**
When chat goes quiet for 5+ minutes, you get a toast with a suggested conversation starter.

**Regular Viewer Welcome Back**
When a known regular returns after being away, you get a toast showing their name and when they were last seen.

**Viewer Database**
Tracks every chatter you've ever had, building a history of your community over time.

## Installation

### Prerequisites

- Python 3.11+
- Windows 10/11 (for toast notifications)
- Twitch account

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/elchalupa/arcade-heartbeat.git
   cd arcade-heartbeat
   ```

2. Create virtual environment:
   ```
   py -3.11 -m venv venv
   .\venv\Scripts\Activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure the application:
   ```
   copy config.example.yaml config.yaml
   copy .env.example .env
   ```

5. Edit `.env` with your Twitch credentials:
   ```
   TWITCH_ACCESS_TOKEN=your_oauth_token_here
   TWITCH_CHANNEL=your_channel_name
   ```

6. (Optional) Customize `config.yaml` with your preferred thresholds.

### Getting a Twitch OAuth Token

1. Go to https://dev.twitch.tv/console/apps
2. Click "Register Your Application"
3. Fill in:
   - Name: `arcade-heartbeat`
   - OAuth Redirect URLs: `http://localhost:3000`
   - Category: Chat Bot
4. Click "Create" and copy your **Client ID**
5. Visit this URL (replace `YOUR_CLIENT_ID`):
   ```
   https://id.twitch.tv/oauth2/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:3000&response_type=token&scope=chat:read
   ```
6. Authorize the app
7. The redirect URL will contain `access_token=XXXXX` — copy that token

## Usage

### Start the application

```
python -m heartbeat
```

Or use the batch file:

```
start.bat
```

### What you'll see

The application runs in a console window showing connection status and events:

```
[Heartbeat] Connected to #yourchannel
[Heartbeat] Loaded 142 known viewers from database
[Heartbeat] Monitoring chat...
[12:34:56] NewViewer123: Hello everyone!
[12:34:56] → New viewer spotted: NewViewer123
[12:35:12] RegularFan: I'm back!
[12:35:12] → Regular returning: RegularFan (last seen 3 days ago)
[12:40:56] → Chat quiet for 5 minutes
```

Toast notifications appear in Windows when action is suggested.

### Stop the application

Press `Ctrl+C` in the console window.

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
thresholds:
  # Minutes of chat silence before notification
  chat_quiet_minutes: 5
  
  # Number of streams to qualify as a "regular" viewer
  regular_viewer_streams: 3
  
  # Days away before showing "welcome back" notification
  regular_away_days: 2

cooldowns:
  # Minutes before repeating a "chat quiet" notification
  chat_quiet_cooldown: 10
  
  # Minutes before welcoming the same viewer again (0 = always notify)
  viewer_welcome_cooldown: 0

notifications:
  # Play Windows notification sound
  sound: true
  
  # App name shown in toast
  app_name: "Heartbeat"
```

## Customizing Prompts

Edit `prompts/default.yaml` to customize the suggestions:

```yaml
chat_quiet:
  - "What games has everyone been playing lately?"
  - "Anyone have plans for the weekend?"
  - "What brought you to the stream today?"

viewer_return:
  - "Welcome back {username}! (last seen {days_ago})"
  - "{username} is back! They've visited {stream_count} streams"
```

Use `{username}`, `{days_ago}`, and `{stream_count}` as placeholders.

## Data Storage

Viewer data is stored in:
```
%APPDATA%\arcade-heartbeat\viewers.db
```

This SQLite database persists across sessions and tracks:
- Username
- First seen date
- Last seen date
- Total message count
- Number of streams attended

## Future Enhancements

- [ ] Speaker.bot integration (detect when streamer is talking)
- [ ] Streamer.bot WebSocket integration
- [ ] System tray mode (hide console)
- [ ] Analytics dashboard
- [ ] Export viewer data

## Related Projects

- [arcade-tts](https://github.com/elchalupa/arcade-tts) — Channel point TTS with voice cloning
- [arcade-newsletter](https://github.com/elchalupa/arcade-newsletter) — Automated monthly newsletter

## License

MIT License — See [LICENSE](LICENSE) for details.
