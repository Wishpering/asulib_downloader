#!/usr/bin/python3

from asyncio import run
import aiohttp
from argparse import ArgumentParser
from img2pdf import convert
from os import getcwd
from os.path import exists

from utils.logger import Logger
import models.errors as errors
from utils.pages import BookPage, ReaderPagePool

logger = Logger.get(__file__)

def exit_with_error(msg):
    logger.exception(msg)
    exit(1)

async def main(link, pages_count):
    async with aiohttp.TCPConnector(limit=0) as connector:
        async with aiohttp.ClientSession(connector=connector, connector_owner=False) as session:
            # Создаем экземпляры классов
            book_page = BookPage(
                session, 
                link,
                debug=debug
            )
    
            # Получаем ID и название книги
            # Они слегка отличаются для headers и для ссылки на скачивание, посему они дублируются
            try:
                book_info = await book_page.parse()
            except errors.BookDownloadError as error:
                exit_with_error(f'Can\'not dowload page for parsing, http_code - {error.code}')
            except errors.LinkNotFound as error:
                exit_with_error(f'Can\'not get link for downloading page, error - {error}')
            except errors.ReadLinkNotFound:
                exit_with_error('Can\'not get link for downloading page')
            except errors.BookInfoNotFound:
                exit_with_error('Can\'not find book info needed for download')

            reader_page = ReaderPagePool(
                session, 
                pages_count, 
                book_info,
                debug=debug
            )

            logger.info('Downloading pages ...')

            # Выкачиваем все странички
            return await reader_page.get_all()

if __name__ == '__main__':
    arg_parser = ArgumentParser(description='Скрипт для выкачивания чего-то с elibrary.asu.ru')
    arg_parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode')
    arg_parser.add_argument('-f', '--file-name', type=str, help='Change file name')
    required = arg_parser.add_argument_group('Required')    
    required.add_argument('-p', '--pages', help='Количество страниц', type=int, required=True)
    required.add_argument('-l', '--link', help='Ссылка на книгу', type=str, required=True)

    args = vars(arg_parser.parse_args())

    if args['pages'] <= 0 or args['link'] == '' or args['link'] is None:
        logger.critical('Количество страниц меньше или равно 0')
        exit(1)
    
    path = getcwd()
    link = args.get('link')
    pages_count = args.get('pages')
    debug = args.get('debug')
    output_filename = args.get('file_name') or 'output.pdf'

    book_pages = run(
        main(
            link,
            pages_count
        )
    )

    # Проверяем, все ли скачалось
    for page, page_num in zip(book_pages, range(1, pages_count + 1)):
        if page == -1:
            logger.critical(f'Не удалось загрузить страницу №{page_num + 1}')

    # Если файл с таким названием уже существует, то запрашиваем другое название
    while exists(f'{path}/{output_filename}') is True:
        output_filename = str(
            input(
                f'Файл {output_filename} уже существует, введите другое название - '
            )
        )

    logger.info('Making pdf file ...')

    # Конвертируем все в PDF
    with open(f'{path}/{output_filename}', 'wb') as file:
        file.write(
            convert(
                [res for res in book_pages]
            )
        )