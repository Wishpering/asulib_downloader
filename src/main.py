#!/usr/bin/python3

import asyncio
import aiohttp
from argparse import ArgumentParser
from bs4 import BeautifulSoup as bs4
from img2pdf import convert
from os import getcwd
from os.path import exists
from random import SystemRandom

import errors
from logger import Logger
from pytypes import Book_Info

logger = Logger()
headers = {
    'Host' : 'elibrary.asu.ru',
    'Connection' : 'close',
    'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
    'Accept' : 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding' : 'gzip, deflate',
    'Accept-Language' : 'en-GB,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6'
}

class Parser:
    def __init__(self, args : dict):
        self.debug_mode = args.get('debug')

    async def get_book_info(self, book_url):
        try:
            if self.debug_mode == True:
                logger.debug('Downloading page for parsing...')

            async with aiohttp.ClientSession() as session:
                # Если ссылка не на чтение книгу, а просто на страницу с книгой,
                # то вытягиваем ссылку на чтение из неё
                if 'xmlui/bitstream/handle/asu' not in book_url:
                    if self.debug_mode == True:
                        logger.debug('Book page not found, searching it in link...')

                    book_url = await Parser.get_read_link(
                        session, book_url, 
                        self.debug_mode
                    )
                    
                # Скачиваем страничку для чтения и дергаем из неё инфу о книге
                async with session.get(book_url) as request:
                    if request.status == 200:
                        book_page = await request.read()
                    else:
                        raise errors.BookDownloadError(request.status)

            if self.debug_mode == True:
                logger.debug('Page loaded successfully...')

        except Exception as error:
            raise errors.LinkNotFound(error)
        
        return Parser.find_book_info(book_page, self.debug_mode) 

    @classmethod
    async def get_read_link(cls, session, link, debug_mode):
        async with session.get(link) as request:   
            if request.status == 200:
                page = await request.read()
            else:
                raise errors.BookDownloadError(request.status)

        read_url = Parser.find_book_readlink(page, debug_mode)

        if read_url == -1:
            raise errors.BookNotFound
        else:
            return read_url

    @classmethod
    def find_book_info(cls, page, debug_mode):
        if debug_mode == True:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        link = soup.frame.extract()['src']

        try:
            if debug_mode == True:
                logger.debug('Parsing the page to get book name and ID...')

            temp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')

            headers_id = int(temp[0].replace('id=', ''))
            headers_name = temp[1].replace('name=', '').replace('.7book', '')

            request_id = int(temp[0].replace('id=', ''))
            request_name = temp[1].replace('name=', '')
        
        except Exception:
            raise errors.BookInfoNotFound

        if debug_mode == True:
            logger.debug(f'Book name - {request_name}, Book ID - {request_id}')

        return Book_Info(
            headers_id = headers_id, request_id = request_id, 
            headers_name = headers_name, request_name = request_name
        )

    @classmethod
    def find_book_readlink(cls, page, debug_mode):
        link = 'http://elibrary.asu.ru'

        if debug_mode == True:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        page_content = soup.find_all('a', href = True)

        for line in page_content:
            tmp = line['href']
                    
            if 'xmlui/bitstream/handle/asu' in tmp:
                link += tmp

                if debug_mode == True:
                    logger.debug(f'Link for book reading founded - {link}, dowloading page with it...')
                
                return link

        if link == 'http://elibrary.asu.ru':
            logger.info('Link for book reading not founded')
            return -1

class Book:
    def __init__(self, debug, pages_num, info):
        self.debug_mode = debug
        self.pages_count = pages_num
        self.id_for_headers = info.headers_id
        self.id_for_request = info.request_id
        self.name_for_headers = info.headers_name
        self.name_for_request = info.request_name
        
    async def download(self):
        tasks = []

        generator = SystemRandom()
        
        # Готовим обманку
        headers['Referer'] = f'http://elibrary.asu.ru/els/files/book' \
                             f'?name={self.name_for_headers}&id={self.id_for_headers}.7book'

        # Выставляем максимальный delay
        if self.pages_count < 50:
            cooldown = 5
        elif self.pages_count < 85:
            cooldown = 10
        elif self.pages_count >= 100:
            cooldown = 60
        elif self.pages_count >= 250:
            cooldown = 120

        if self.debug_mode == True:
            logger.debug(f'Delay value set to {cooldown}')
            
        async with aiohttp.ClientSession() as session:
            for task_num in range(1, self.pages_count + 1):
                tasks.append(
                    asyncio.create_task(
                        Book.__downloader(
                            session,
                            f'http://elibrary.asu.ru/els/files/test/' \
                            f'?name={self.name_for_request}&id={self.id_for_request}' \
                            f'&page={task_num}&mode=1',
                            task_num,
                            self.debug_mode,
                            generator.uniform(0, cooldown)
                        )
                    )
                )
            
            return await asyncio.gather(*tasks)

    @classmethod
    async def __downloader(cls, session, link, task_num, debug_mode, cooldown):
        # Спим сколько-то перед запуском потока, а то сервак охуевает, если много страниц 
        if debug_mode == True:
            logger.debug(f'Waiting {cooldown} seconds before downloading page №{task_num}')

        await asyncio.sleep(cooldown)

        if debug_mode == True:
            logger.debug(f'Downloading page №{task_num}')
        
        try:
            async with session.get(link, headers = headers) as request:
                if request.status == 200:
                    return await request.read()
                else:
                    logger.exception(f'Can\'not download page №{task_num}, http status code - {request.status}')
                    return -1

        except Exception as error:
            logger.exception(f'Can\'not download page №{task_num}, error - {error}')
            return -1

def exit_with_error(msg):
    logger.critical(msg)
    loop.close()
    exit(1)

if __name__ == '__main__':
    arg_parser = ArgumentParser(description = 'Скрипт для выкачивания чего-то с elibrary.asu.ru')
    arg_parser.add_argument('-d', '--debug', action = 'store_true', help = 'Enable debug mode')
    arg_parser.add_argument('-f', '--file-name', type = str, help = 'Change file name')
    required = arg_parser.add_argument_group('Required')    
    required.add_argument('-p', '--pages', help = 'Количество страниц', type = int, required = True)
    required.add_argument('-l', '--link', help = 'Ссылка на книгу', type = str, required = True)

    args = vars(arg_parser.parse_args())

    logger = logger.get()

    page_count = args.get('pages')
    output_filename = args.get('file_name') or 'output.pdf'

    # Проверка ввода
    if page_count <= 0:
        logger.critical('Количество страниц меньше или равно 0')
        exit(1)
    
    path = getcwd()
    loop = asyncio.get_event_loop()

    # Создаем экземпляры классов
    parser = Parser(args)
    
    # Получаем ID и название книги
    # Они слегка отличаются для headers и для ссылки на скачивание, посему они дублируются
    try:
        book_info = loop.run_until_complete( 
            parser.get_book_info(args.get('link'))
        )
    except errors.BookDownloadError as error:
        exit_with_error(f'Can\'not dowload page for parsing, http_code - {error.code}')
    except errors.LinkNotFound as error:
        exit_with_error(f'Can\'not get link for downloading page, error - {error}')
    except errors.BookNotFound:
        exit_with_error('Can\'not get link for downloading page')
    except errors.BookInfoNotFound:
        exit_with_error('Can\'not find book info needed for download')

    book = Book(
        args.get('debug'),
        page_count,
        book_info 
    )

    logger.info('Downloading pages ...')

    # Выкачиваем все странички
    book_Pages = loop.run_until_complete(
        book.download()
    )

    # Проверяем, все ли скачалось
    for page, page_Num in zip(book_Pages, range(1, page_count + 1)):
        if page == -1:
            logger.critical(f'Не удалось загрузить страницу №{page_Num + 1}')

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
                [res for res in book_Pages]
            )
        )

    loop.close()
