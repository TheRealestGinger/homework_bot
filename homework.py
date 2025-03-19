import os
import logging
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN_API')
TELEGRAM_TOKEN = os.getenv('TOKEN_BOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logger = logging.getLogger('__name__')
logger.setLevel(logging.DEBUG)
logging.basicConfig(
    format=('%(asctime)s [%(levelname)s] %(funcName)s '
            '%(lineno)s %(message)s'),
    handlers=(
        logging.FileHandler(__file__ + '.log'),
        logging.StreamHandler(stream=sys.stdout)
    ),
    level=logging.DEBUG
)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


TOKEN_IS_NONE_ERROR = 'Отсутствует переменная {name}'
MESSAGE_SEND_ERROR = 'Сообщение \'{message}\' не удалось отправить'
MESSAGE_SEND_SUCCESS = 'Бот отправил сообщение: \'{message}\''
REQUEST_PARAMS = (
    'Параметры запроса: url - {ENDPOINT}, headers - {HEADERS}, '
    'params - {timestamp}'
)
REQUEST_ERROR = (
    'Ошибка при запросе к API: {error}' + REQUEST_PARAMS
)
STATUS_CODE_ERROR = (
    'Статус ответа: {status_code}. Ожидался 200.' + REQUEST_PARAMS
)
RESPONSE_JSON_ERROR = 'Ошибка в ответе API: {response_json}'
RESPONSE_TYPE_ERROR = (
    'Тип данных ответа API не соответствует ожиданиям'
    'Ожидается словарь, но получен {type}'
)
HOMEWORKS_IS_NONE_ERROR = 'Отсутствует ключ \'homeworks\' в ответе API'
HOMEWORKS_TYPE_ERROR = (
    'Ожидается список с домашними заданиями, но получен {type}'
)
HOMEWORK_NAME_ERROR = 'Отсутствует имя домашней работы'
HOMEWORK_STATUS_ERROR = 'Неожиданный статус домашней работы: {status}'
PARSE_SUCCESS = (
    'Изменился статус проверки работы '
    '\"{homework_name}\". '
    '{status}'
)
EMPTY_HOMEWORKS = 'Новых домашних работ не найдено'
MAIN_ERROR = 'Сбой в работе программы: {error}'


def check_tokens():
    """Проверка наличия токенов в переменных окружения."""
    for name in 'PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID':
        if globals()[name] is None:
            logger.critical(TOKEN_IS_NONE_ERROR.format(name=name))
            raise KeyError(TOKEN_IS_NONE_ERROR.format(name=name))


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logger.exception(MESSAGE_SEND_ERROR.format(message=message))
    logger.debug(MESSAGE_SEND_SUCCESS.format(message=message))


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        raise error(
            REQUEST_ERROR.format(
                error=error,
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                timestamp=timestamp
            )
        )
    if response.status_code != requests.codes.ok:
        raise requests.exceptions.HTTPError(
            STATUS_CODE_ERROR.format(
                status_code=response.status_code,
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                timestamp=timestamp
            )
        )
    response_json = response.json()
    if 'code' in response_json or 'error' in response_json:
        raise RuntimeError(
            RESPONSE_JSON_ERROR.format(response_json=response_json)
        )
    return response_json


def check_response(response):
    """Проверка ответа API на соответствие ожиданиям."""
    if not isinstance(response, dict):
        raise TypeError(
            RESPONSE_TYPE_ERROR.format(type=type(response))
        )
    if response.get('homeworks') is None:
        raise KeyError(HOMEWORKS_IS_NONE_ERROR)
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            HOMEWORKS_TYPE_ERROR.format(type=type(response['homeworks']))
        )


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_ERROR)
    elif status not in HOMEWORK_VERDICTS:
        raise KeyError(HOMEWORK_STATUS_ERROR.format(status=status))
    return PARSE_SUCCESS.format(
        homework_name=homework['homework_name'],
        status=HOMEWORK_VERDICTS[status]
    )


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response['current_date']
            check_response(response)
            homeworks = response['homeworks']
            if homeworks != []:
                update_status = parse_status(homeworks[0])
                send_message(bot, update_status)
            else:
                logger.debug(EMPTY_HOMEWORKS)

        except Exception as error:
            message = MAIN_ERROR.format(error=error)
            if message != logger.handlers[0].baseFilename:
                send_message(bot, message)
                logger.handlers[0].baseFilename = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
