import os
import logging
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (
    StatusCodeError
)


load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN_API')
TELEGRAM_TOKEN = os.getenv('TOKEN_BOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logger = logging.getLogger(__name__)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


TOKEN_IS_NONE_ERROR = 'Отсутствует переменная {name}'
MESSAGE_SEND_ERROR = 'Сообщение "{message}" не удалось отправить: {error}'
MESSAGE_SEND_SUCCESS = 'Бот отправил сообщение: "{message}"'
REQUEST_PARAMS = (
    'Параметры запроса: url - {ENDPOINT}, headers - {HEADERS}, '
    'params - {timestamp}'
)
REQUEST_ERROR = (
    f'Ошибка при запросе к API: {{error}} {REQUEST_PARAMS}'
)
STATUS_CODE_ERROR = (
    f'Статус ответа: {{status_code}}. Ожидался 200. {REQUEST_PARAMS}'
)
RESPONSE_JSON_ERROR = (
    f'Ошибка в ответе API: {{key}}: {{value}}. {REQUEST_PARAMS}'
)
RESPONSE_TYPE_ERROR = (
    'Тип данных ответа API не соответствует ожиданиям'
    'Ожидается словарь, но получен {type}'
)
HOMEWORKS_IS_NONE_ERROR = 'Отсутствует ключ "homeworks" в ответе API'
HOMEWORKS_TYPE_ERROR = (
    'Ожидается список с домашними заданиями, но получен {type}'
)
HOMEWORK_NAME_ERROR = 'Отсутствует имя домашней работы'
HOMEWORK_STATUS_ERROR = 'Неожиданный статус домашней работы: {status}'
PARSE_SUCCESS = (
    'Изменился статус проверки работы '
    '"{homework_name}". '
    '{status}'
)
EMPTY_HOMEWORKS = 'Новых домашних работ не найдено'
MAIN_ERROR = 'Сбой в работе программы: {error}'


def check_tokens():
    """Проверка наличия токенов в переменных окружения."""
    missing_tokens = [name for name in (
        'PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'
    ) if globals()[name] is None]
    if missing_tokens:
        logger.critical(TOKEN_IS_NONE_ERROR.format(name=missing_tokens))
        raise ValueError(
            TOKEN_IS_NONE_ERROR.format(name=missing_tokens)
        )


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.exception(
            MESSAGE_SEND_ERROR.format(message=message, error=error)
        )
    logger.debug(MESSAGE_SEND_SUCCESS.format(message=message))


def get_api_answer(timestamp):
    """Получение ответа от API."""
    request_params = dict(
        url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
    )
    try:
        response = requests.get(**request_params)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            REQUEST_ERROR.format(
                error=error,
                **request_params
            )
        )
    if response.status_code != requests.codes.ok:
        raise StatusCodeError(
            STATUS_CODE_ERROR.format(
                status_code=response.status_code,
                **request_params
            )
        )
    response_json = response.json()
    for key in ('code', 'error'):
        if key in response_json:
            raise RuntimeError(
                RESPONSE_JSON_ERROR.format(
                    key=key,
                    value=response_json[key],
                    **request_params
                )
            )
    return response_json


def check_response(response):
    """Проверка ответа API на соответствие ожиданиям."""
    if not isinstance(response, dict):
        raise TypeError(
            RESPONSE_TYPE_ERROR.format(type=type(response))
        )
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_IS_NONE_ERROR)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            HOMEWORKS_TYPE_ERROR.format(type=type(homeworks))
        )


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_ERROR)
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(HOMEWORK_STATUS_ERROR.format(status=status))
    return PARSE_SUCCESS.format(
        homework_name=homework['homework_name'],
        status=HOMEWORK_VERDICTS[status]
    )


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                if (open(f'{__file__}.log', 'r').readlines()[-1] ==
                        MESSAGE_SEND_SUCCESS.format(message=message)):
                    timestamp = response.get('current_date', timestamp)
            else:
                logger.debug(EMPTY_HOMEWORKS)

        except Exception as error:
            message = MAIN_ERROR.format(error=error)
            if message != last_error_message:
                send_message(bot, message)
                if (open(f'{__file__}.log', 'r').readlines()[-1] ==
                        MESSAGE_SEND_SUCCESS.format(message=message)):
                    last_error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s [%(levelname)s] %(funcName)s '
                '%(lineno)s %(message)s'),
        handlers=(
            logging.FileHandler(f'{__file__}.log'),
            logging.StreamHandler(stream=sys.stdout)
        ),
        level=logging.DEBUG
    )
    main()
