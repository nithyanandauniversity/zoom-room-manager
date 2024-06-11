# Zoom Room Manager

Automated Zoom Room management script with robust error handling, notifications via Telegram and Slack, and optimized performance using concurrency and session management.

## Features
- Retrieve the current status of Zoom Rooms
- Automatically unmute audio and video if the room is in a meeting
- Comprehensive error handling and retries with exponential backoff
- Detailed logging for troubleshooting
- Notifications via Telegram and Slack

## Configuration
Create a `config.json` file in the root directory with the following structure:
```json
{
  "rooms": [
    {
      "room_id": "your_room_id_1",
      "api_key": "your_api_key1",
      "api_secret": "your_api_secret1"
    },
    {
      "room_id": "your_room_id_2",
      "api_key": "your_api_key2",
      "api_secret": "your_api_secret2"
    }
  ],
  "telegram": {
    "bot_token": "your_telegram_bot_token",
    "chat_id": "your_telegram_chat_id"
  },
  "slack": {
    "webhook_url": "your_slack_webhook_url"
  }
}
```

## Requirements
- Python 3.6+
- Install dependencies:
  ```sh
  pip3 install -r requirements.txt
  ```

## Usage
Run the script:
```sh
python3 manage_zoom_rooms.py
```


## Sequence Diagram
![Zoom Room Manager Script : Sequence Diagram](sequence_diagram.png)


## Flow Diagram
![Zoom Room Manager Script : Flow Diagram](flow_diagram.png)


## License
MIT License
