#!/usr/bin/python3

from loguru import logger
from argparse import ArgumentParser
import asyncio
import aiohttp
from bs4 import BeautifulSoup as bs4
from threading import Thread
from os.path import dirname, abspath, exists
from random import SystemRandom
from img2pdf import convert

headers = {
    'Host' : 'elibrary.asu.ru',
    'Connection' : 'close',
    'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
    'DNT' : '1',
    'Accept' : 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding' : 'gzip, deflate',
    'Accept-Language' : 'en-GB,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6'
    }

class Loop:
    loop = asyncio.new_event_loop()  
    main_Thread = Thread(target = loop.run_forever, daemon = True).start()

class Parser:
    def __init__(self, args : dict):
        self.debug_Mode = args.get('debug')

    async def get_Book_Info(self, book_Url):
        try:
            if self.debug_Mode == True:
                print('Downloading page for parsing...')

            async with aiohttp.ClientSession() as session:
                # Если ссылка не на чтение книгу, а просто на страницу с книгой,
                # то вытягиваем ссылку на чтение из неё
                if 'xmlui/bitstream/handle/asu' not in book_Url:
                    book_Url = await Parser.get_Read_Link(session, book_Url, self.debug_Mode)
                    
                    if 'error' in book_Url:
                        return book_Url.get('error')
                    
                # Скачиваем страничку для чтения и дергаем из неё инфу о книге
                async with session.get(book_Url) as request:
                    if request.status == 200:
                        request = await request.read()
                    else:
                        return {'error' : f'Can\'not dowload page for parsing - {request.status}'}

            if self.debug_Mode == True:
                print('Page loaded successfully...')

        except Exception as error:
            logger.exception(f'Smth went wrong on getting link, error - {error}')
            return {'error' : 'Can\'not get link for downloading page'}

        book_Info = Parser.get_Book_ID(request, self.debug_Mode)

        if book_Info == -4:
            return {'error' : 'Can\'not get info about book'}
        else:
            return book_Info 

    @classmethod
    async def get_Read_Link(cls, session, link, debug_Mode):
        if debug_Mode == True:
            print('Book page not found, searching it in link...')

        async with session.get(link) as request:   
            if request.status == 200:
                request = await request.read()
            else:
                return {'error' : 'Can\'not dowload page for finding book link'}

        book_Url = Parser.get_Book_Link(request, debug_Mode)

        if book_Url == -5:
            return {'error' : 'Can\'not get book link from page'}
        else:
            return book_Url

    @classmethod
    def get_Book_ID(cls, page, debug_Mode):
        if debug_Mode == True:
            print('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        link = soup.frame.extract()['src']

        try:
            if debug_Mode == True:
                print('Parsing the page to get book name and ID...')

            temp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')

            id_For_Headers = str(temp[0]).replace('id=', '') + '.7book'
            name_For_Headers = str(temp[1]).replace('name=', '').replace('.7book', '')

            id_For_Request = str(temp[0]).replace('id=', '')
            name_For_Request = str(temp[1]).replace('name=', '')
        
        except Exception as error:
            logger.exception(f'Crash on getting Book_ID and Book_Name, error - {error}')
            return {'error' : 'Crash on getting Book_ID and Book_Name'}

        if debug_Mode == True:
            print(f'Book name - {name_For_Request}, Book ID - {id_For_Request}')

        return {
            'headers_ID' : id_For_Headers, 'request_ID' : id_For_Request, 
            'headers_Name' : name_For_Headers, 'request_Name' : name_For_Request
        }

    @classmethod
    def get_Book_Link(cls, link, debug_Mode):
        main_Link = 'http://elibrary.asu.ru'

        if debug_Mode == True:
            print('Preparing Beautifulsoup with lxml engine')

        soup = bs4(link, 'lxml')
        content = soup.find_all('a', href = True)

        for line in content:
            tmp = line['href']
                    
            if 'xmlui/bitstream/handle/asu' in tmp:
                main_Link += tmp

                if debug_Mode == True:
                    print(f'Link for book reading founded - {main_Link}, dowloading page with it...')
                
                return main_Link

        if main_Link == 'http://elibrary.asu.ru':
            print('Link for book reading not founded')
            return -5

class Book:
    def __init__(self, args):
        self.debug_Mode = args.get('debug')
        
    async def download(self, count_Of_Pages, id_For_Headers, id_For_Request, name_For_Headers, name_For_Request):
        tasks = []

        generator = SystemRandom()
        
        # Готовим обманку
        headers['Referer'] = f'http://elibrary.asu.ru/els/files/book' \
                             f'?name={name_For_Headers}&id={id_For_Headers}'

        # Выставляем максимальный delay
        if count_Of_Pages < 50:
            cooldown = 5
        elif count_Of_Pages < 85:
            cooldown = 10
        elif count_Of_Pages >= 100:
            cooldown = 60
        elif count_Of_Pages >= 250:
            cooldown = 120

        if self.debug_Mode == True:
            print(f'Delay value set to {cooldown}')
            
        async with aiohttp.ClientSession() as session:

            for task_Num in range(1, count_Of_Pages + 1):
                tasks.append(
                    asyncio.create_task(
                        Book.__downloader(
                            session,
                            f'http://elibrary.asu.ru/els/files/test/' \
                            f'?name={name_For_Request}&id={id_For_Request}' \
                            f'&page={task_Num}&mode=1',
                            task_Num,
                            self.debug_Mode,
                            generator.uniform(0, cooldown)
                        )
                    )
                )
            
            return await asyncio.gather(*tasks)

    @classmethod
    async def __downloader(cls, session, link, num_Of_Task, debug_Mode, cooldown):
        # Спим сколько-то перед запуском потока, а то сервак охуевает, если много страниц 
        if debug_Mode == True:
            print(f'Waiting {cooldown} seconds before starting thread № {num_Of_Task}')

        await asyncio.sleep(cooldown)

        if debug_Mode == True:
            print(f'Spawining thread for downloading page №{num_Of_Task}')
        
        try:
            async with session.get(link, headers = headers) as request:
                if request.status == 200:
                    return await request.read()
                else:
                    return -1

        except Exception as error:
            logger.exception(f'Can\'not download page №{num_Of_Task}, error - {error}')

            return -1

if __name__ == '__main__':
    arg_Parser = ArgumentParser(description = 'Скрипт для выкачивания чего-то с elibrary.asu')
    arg_Parser.add_argument('-d', '--debug', action = "store_true", help = 'Enable debug mode')
    arg_Parser.add_argument('-o', '--output-dir', type = str, help = 'Change output directory')
    arg_Parser.add_argument('-f', '--file-name', type = str, help = 'Change file name')
    required = arg_Parser.add_argument_group('Required')    
    required.add_argument('-p', '--pages', help = 'Количество страниц', type = int, required = True)
    required.add_argument('-l', '--link', help = 'Ссылка на книгу', type = str, required = True)

    args = vars(arg_Parser.parse_args())

    page_Count = args.get('pages')
    output_File_Name = args.get('file_name') or 'output'
    Path = args.get('output_dir') or str(dirname(abspath(__file__)))
    
    # Проверка на корректность указанного пути
    if Path.endswith('/') is False:
        Path += '/'

    logger.add(
        'log.file', 
        colorize = True, backtrace = True, diagnose = True,
        format = '{time} {message}', level = 'DEBUG'
    )

    # Создаем экземпляры классов
    parser = Parser(args)
    book = Book(args)

    # Получаем ID и название книги
    # Они слегка отличаются для Headers и для ссылки на скачивание, посему их 4
    book_Info = asyncio.run_coroutine_threadsafe( 
        parser.get_Book_Info(args.get('link')), 
        Loop.loop
    ).result()

    # Если что-то пошло не так
    if 'error' in book_Info:
        print(book_Info.get('error'))
        exit()

    print('Downloading pages ...')

    # Выкачиваем все странички
    book_Pages = asyncio.run_coroutine_threadsafe(
        book.download(
            page_Count, 
            book_Info.get('headers_ID'), book_Info.get('request_ID'), 
            book_Info.get('headers_Name'), book_Info.get('request_Name')
        ),
        Loop.loop
    ).result()

    # Проверяем, все ли скачалось
    for res, page_Num in zip(book_Pages, range(1, page_Count + 1)):
        if res == -1 :
            print(f'Не удалось загрузить страницу №{page_Num + 1}')

    # Если файл с таким названием уже существует, то запрашиваем другое название
    while exists(f'{Path}{output_File_Name}.pdf') is True:
        output_File_Name = str(
            input(
                f'Файл {output_File_Name}.pdf уже существует, введите другое название - '
                )
            )

    print('Making pdf file ...')

    # Конвертируем все в PDF
    with open(f'{Path}{output_File_Name}.pdf', "wb") as file:
            file.write(
                convert(
                    [res for res in book_Pages]
                    )
                )

    print('Done')
