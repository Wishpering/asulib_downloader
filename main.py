#!/usr/bin/python3

import logging
from bs4 import BeautifulSoup as bs4
from os.path import dirname, abspath, exists
import asyncio
from threading import Thread
import aiohttp
from random import uniform
from img2pdf import convert
from argparse import ArgumentParser

headers = {
    'Host' : 'elibrary.asu.ru',
    'Connection' : 'close',
    'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
    'DNT' : '1',
    'Accept' : 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Encoding' : 'gzip, deflate',
    'Accept-Language' : 'en-GB,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6'
    }

def start_background_loop(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()          

class Loop:
    loop = asyncio.new_event_loop()
    main_Thread = Thread(target = start_background_loop, args = (loop, ), daemon = True).start()    

class Parcer:
    def __init__(self, logger, args : dict):
        self.logger = logger
        self.args = args

    async def get_Link(self, book_Url):
        try:
            if self.args.get('verbose') == True:
                print('Downloading page for parsing...')

            async with aiohttp.ClientSession() as session:
                async with session.get(book_Url) as request:
            
                    if request.status != 200:
                        if self.args.get('debug') == True:
                            print('Can\'not dowload page for parsing')

                        self.logger.exception('Can\'not dowload page for parsing')
                        exit()
                
                    request = await request.read()

            if self.args.get('verbose') == True:
                print('Page loaded successfully...')

        except Exception as error:
            if self.args.get('debug') == True:
                print(error)

            self.logger.exception(error)
            exit()
                
        try:
            if self.args.get('verbose') == True:
                print('Preparing Beautifulsoup with lxml engine')

            soup = bs4(request, 'lxml')
            link = soup.frame.extract()['src']
        except Exception as error:
            if self.args.get('debug') == True:
                print('Cannot start BS4', error)

            self.logger.exception(error)
            exit()

        try:
            if self.args.get('verbose') == True:
                print('Parsing the page to get book name and ID...')

            temp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')

            id_For_Headers = str(temp[0]).replace('id=', '') + '.7book'
            name_For_Headers = str(temp[1]).replace('name=', '').replace('.7book', '')

            id_For_Request = str(temp[0]).replace('id=', '')
            name_For_Request = str(temp[1]).replace('name=', '')
        
        except Exception as error:
            if self.args.get('debug') == True:
                print('Can\'not get book name and ID', error)
                self.logger.exception('Crash on getting Book_ID and Book_Name' + '\n' + str(error))
            
            exit()

        if self.args.get('verbose') == True:
                print('Book name -', name_For_Request, 'Book ID -', id_For_Request)

        return id_For_Headers, id_For_Request, name_For_Headers, name_For_Request

class Book:
    def __init__(self, loop, logger, args):
        self.loop = Loop
        self.logger = logger
        self.args = args

    async def download_Book(self, count_Of_Pages, id_For_Headers, id_For_Request, name_For_Headers, name_For_Request):
        tasks = []

        # Готовим обманку
        headers['Referer'] = 'http://elibrary.asu.ru/els/files/book?name=' + str(name_For_Headers) + '&id=' + str(id_For_Headers)

        for task_Num in range(1, page_Count + 1):
            if self.args.get('verbose') == True:
                print('Preparing task for downloading page №' + str(task_Num))

            tasks.append(
                asyncio.create_task(
                    Book.__downloader(
                            'http://elibrary.asu.ru/els/files/test/?name='
                            + name_For_Request +'&id=' + id_For_Request +'&page=' + str(task_Num)
                            + '&mode=1',
                            headers,
                            task_Num,
                            self.args
                    )
                )
            )
            
        return await asyncio.gather(*tasks)

    @classmethod
    async def __downloader(cls, link, headers, num_Of_Task, args):
        # Спим сколько-то перед запуском потока, а то сервак охуевает, если много страниц 
        cooldown = uniform(0, 20)

        if args.get('verbose') == True or args.get('debug') == True:
            print('Waiting ' + str(cooldown) + ' seconds before starting thread №' + str(num_Of_Task))

        await asyncio.sleep(cooldown)

        if args.get('verbose') == True:
            print('Spawining thread for downloading page №' + str(num_Of_Task))
        
        try:
            async with aiohttp.ClientSession() as session:
                    async with session.get(link, headers = headers) as request:
                        if request.status == 200:
                            return await request.read()
                        else:
                            return -1

        except Exception as error:
            if args.get('debug') == True:
                print('Can\'not download page №' + num_Of_Task)
                cls.logger.exception(error)

if __name__ == '__main__':
    output_Filename = 'output'

    # Парсим аргументы
    arg_Parser = ArgumentParser(description = 'Скрипт для выкачивания чего-то с elibrary.asu')
    arg_Parser.add_argument('-d', '--debug', action = "store_true", help = 'Enable debug mode')
    arg_Parser.add_argument('-v', '--verbose', action = "store_true", help = 'Be more verbose')
    arg_Parser.add_argument('-o', '--output', type = str, help = 'Change output directory')
    required = arg_Parser.add_argument_group('Required')    
    required.add_argument('-p', '--pages', help = 'Количество страниц', type = int, required = True)
    required.add_argument('-l', '--link', help = 'Ссылка на книгу', type = str, required = True)

    args = vars(arg_Parser.parse_args())

    page_Count = args.get('pages')
    Path = args.get('output') or str(dirname(abspath(__file__))) + '/'

    # Запускаем логгер
    if args.get('debug') == True:
        logging.basicConfig(filename = Path + 'log.txt', level = logging.DEBUG)
        log_File = logging.getLogger("Book downloader")
    else:
        log_File = None

    # Создаем экземпляры классов
    parcer = Parcer(log_File, args)
    downloader = Book(Loop.loop, log_File, args)

    # Получаем ID и название книги
    # Они слегка отличаются для Headers и для ссылки на скачивание, посему их 4
    id_For_Headers, id_For_Request, \
        name_For_Headers, name_For_Request \
            = asyncio.run_coroutine_threadsafe( 
                parcer.get_Link(args.get('link')
                ), Loop.loop
            ).result()

    # Выкачиваем все странички
    result_Of_Downloader = asyncio.run_coroutine_threadsafe(
        downloader.download_Book(
            page_Count, id_For_Headers, id_For_Request, name_For_Headers, name_For_Request
        ),
        Loop.loop
    ).result()

    # Проверяем, все ли скачалось
    for res, count in zip(result_Of_Downloader, range(1, page_Count + 1)):
        if res == -1:
            print('Не удалось загрузить страницу №' + str(count))

    # Если файл с таким названием уже существует, то запрашиваем другое название
    while exists(Path + output_Filename + '.pdf') is True:
        output_Filename = str(
            input(
                'Такой файл уже существует, введите другое название - '
                )
            )

    # Конвертируем все в PDF
    with open(Path + output_Filename + '.pdf', "wb") as file:
            file.write(
                convert([res for res in result_Of_Downloader])
                )
