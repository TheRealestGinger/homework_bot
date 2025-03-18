import os
import logging
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (
    CantGetAnswerFromAPI, HomeworkNameIsNone, HomeworkVerdictIsUnknown
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_API')
TELEGRAM_TOKEN = os.getenv('TOKEN_BOT')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов в переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical('Отсутствует token практикума')
        raise AssertionError('Отсутствует token практикума')
    elif TELEGRAM_TOKEN is None:
        logger.critical('Отсутствует token telegram бота')
        raise AssertionError('Отсутствует token telegram бота')
    elif TELEGRAM_CHAT_ID is None:
        logger.critical('Отсутствует id чата')
        raise AssertionError('Отсутствует id чата')


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Сообщение не удалось отправить: {error}')
    else:
        logger.debug(f'Бот отправил сообщение: "{message}"')


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            text = f'Статус ответа: {response.status_code}. Ожидался 200.'
            logger.error(text)
            raise CantGetAnswerFromAPI(text)
    except Exception as error:
        text = f'Ошибка при запросе к API: {error}'
        logger.error(text)
        raise CantGetAnswerFromAPI(text)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие ожиданиям."""
    if not isinstance(response, dict):
        text = 'Структура данных API не соответствует ожиданиям'
        logger.error(text)
        raise TypeError(text)
    if not isinstance(response.get('homeworks'), list):
        text = ('Ожидается список с домашними заданиями, '
                'но получен другой тип.')
        logger.error(text)
        raise TypeError(text)


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    if homework == []:
        logger.debug('Отсутствуют новые статусы домашней работы')
    elif homework.get('homework_name') is None:
        text = 'Отсутствует имя домашней работы'
        logger.error(text)
        raise HomeworkNameIsNone(text)
    elif homework.get('status') not in HOMEWORK_VERDICTS:
        text = (f'Неожиданный статус домашней работы: '
                f'{homework.get("status")}')
        logger.error(text)
        raise HomeworkVerdictIsUnknown(text)
    else:
        return (f'Изменился статус проверки работы '
                f'"{homework.get("homework_name")}". '
                f'{HOMEWORK_VERDICTS[homework.get("status")]}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            print(response)
            check_response(response)
            if response.get('homeworks'):
                update_status = parse_status(response.get('homeworks')[0])
                send_message(bot, update_status)
            else:
                parse_status(response.get('homeworks'))

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        time.sleep(600)
        timestamp = int(time.time())


if __name__ == '__main__':
    main()
