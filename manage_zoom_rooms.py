import requests
import jwt
import datetime
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Load configuration
def load_config(file_path='config.json'):
    try:
        with open(file_path) as config_file:
            config = json.load(config_file)
            return config
    except Exception as e:
        logging.error(f'Error loading configuration: {e}')
        raise

config = load_config()

ROOMS = config['rooms']
TELEGRAM_CONFIG = config.get('telegram', {})
SLACK_CONFIG = config.get('slack', {})

# Setup logging
logging.basicConfig(level=logging.INFO, filename='zoom_rooms.log', format='%(asctime)s - %(levelname)s - %(message)s')

def generate_jwt(api_key, api_secret):
    payload = {
        'iss': api_key,
        'exp': datetime.datetime.now() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, api_secret, algorithm='HS256')

def send_telegram_message(message):
    if TELEGRAM_CONFIG:
        url = f'https://api.telegram.org/bot{TELEGRAM_CONFIG["bot_token"]}/sendMessage'
        data = {
            'chat_id': TELEGRAM_CONFIG['chat_id'],
            'text': message,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                logging.info('Telegram message sent successfully')
            else:
                logging.error(f'Failed to send Telegram message: {response.text}')
        except Exception as e:
            logging.error(f'Error sending Telegram message: {e}')
    else:
        logging.info('Telegram configuration not provided. Skipping Telegram notification.')

def send_slack_message(message):
    if SLACK_CONFIG:
        data = {
            'text': message
        }
        try:
            response = requests.post(SLACK_CONFIG['webhook_url'], json=data)
            if response.status_code == 200:
                logging.info('Slack message sent successfully')
            else:
                logging.error(f'Failed to send Slack message: {response.text}')
        except Exception as e:
            logging.error(f'Error sending Slack message: {e}')
    else:
        logging.info('Slack configuration not provided. Skipping Slack notification.')

def send_notification(message):
    send_telegram_message(message)
    send_slack_message(message)

def handle_api_response(response, action, room_id):
    try:
        response.raise_for_status()
        if response.status_code == 204:
            logging.info(f'{action.capitalize()} successfully for room {room_id}.')
            return 'Success'
        else:
            error_message = f'{action.capitalize()} failed for room {room_id}. Response: {response.json()}'
            logging.error(error_message)
            send_notification(error_message)
            return 'Failed'
    except requests.exceptions.HTTPError as http_err:
        error_message = f'HTTP error occurred during {action} for room {room_id}: {http_err}'
        logging.error(error_message)
        send_notification(error_message)
        return 'Failed'
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f'Connection error occurred during {action} for room {room_id}: {conn_err}'
        logging.error(error_message)
        send_notification(error_message)
        return 'Failed'
    except requests.exceptions.Timeout as timeout_err:
        error_message = f'Timeout error occurred during {action} for room {room_id}: {timeout_err}'
        logging.error(error_message)
        send_notification(error_message)
        return 'Failed'
    except requests.exceptions.RequestException as req_err:
        error_message = f'API request error occurred during {action} for room {room_id}: {req_err}'
        logging.error(error_message)
        send_notification(error_message)
        return 'Failed'

def unmute_zoom_room(session, room_id, api_key, api_secret):
    jwt_token = generate_jwt(api_key, api_secret)
    headers = {
        'authorization': f'Bearer {jwt_token}',
        'content-type': 'application/json'
    }

    endpoints = {
        'audio': f'https://api.zoom.us/v2/rooms/{room_id}/audio/unmute',
        'video': f'https://api.zoom.us/v2/rooms/{room_id}/video/unmute'
    }

    results = {}
    for key, url in endpoints.items():
        attempts = 3
        while attempts > 0:
            try:
                response = session.put(url, headers=headers)
                result = handle_api_response(response, f'unmute {key}', room_id)
                if result == 'Success':
                    results[key] = 'Success'
                    break
            except Exception as e:
                logging.error(f'Failed to unmute {key} for room {room_id}: {e}')
                attempts -= 1
                sleep(5 * (3 - attempts))  # Exponential backoff
                if attempts == 0:
                    results[key] = 'Failed'
                    message = (f'Failed to unmute {key} for room {room_id} after 3 attempts.\n'
                               f'Timestamp: {datetime.datetime.now()}\n'
                               f'Room ID: {room_id}\n'
                               f'Endpoint: {url}\n'
                               f'API Key: {api_key}\n'
                               f'Response: {e}')
                    send_notification(message)
    return results

def get_room_status(session, room_id, api_key, api_secret):
    jwt_token = generate_jwt(api_key, api_secret)
    headers = {
        'authorization': f'Bearer {jwt_token}',
        'content-type': 'application/json'
    }

    url = f'https://api.zoom.us/v2/rooms/{room_id}'
    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        room_status = response.json()
        logging.info(f'Room status for {room_id}: {room_status}')
        return room_status
    except requests.exceptions.RequestException as e:
        logging.error(f'Failed to retrieve status for room {room_id}: {e}')
        message = (f'Failed to retrieve status for room {room_id}.\n'
                   f'Timestamp: {datetime.datetime.now()}\n'
                   f'Room ID: {room_id}\n'
                   f'API Key: {api_key}\n'
                   f'Response: {e}')
        send_notification(message)
        return None

def process_room(session, room):
    room_id = room['room_id']
    api_key = room['api_key']
    api_secret = room['api_secret']
    
    status = get_room_status(session, room_id, api_key, api_secret)
    if status and status['room_status'] == 'InMeeting':
        return unmute_zoom_room(session, room_id, api_key, api_secret)
    return { 'audio': 'Not in meeting', 'video': 'Not in meeting' }

def main():
    results_summary = []

    # Create a session with retry logic
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS", "POST", "PUT"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_room = {executor.submit(process_room, session, room): room for room in ROOMS}
        for future in as_completed(future_to_room):
            room = future_to_room[future]
            try:
                result = future.result()
                results_summary.append((room['room_id'], result))
            except Exception as e:
                logging.error(f'Error processing room {room["room_id"]}: {e}')
                results_summary.append((room['room_id'], 'Error'))

    message = (f'All specified Zoom rooms have been processed.\n'
               f'Timestamp: {datetime.datetime.now()}\n'
               f'Results:\n' +
               '\n'.join([f'Room ID: {room_id}, Results: {results}' for room_id, results in results_summary]))
    send_notification(message)

if __name__ == '__main__':
    main()
