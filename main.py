#!/usr/bin/python3

from loguru import logger
from argparse import ArgumentParser
import asyncio
import aiohttp
from bs4 import BeautifulSoup as bs4
from os.path import dirname, abspath, exists
from random import SystemRandom
from img2pdf import convert

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
        self.debug_Mode = args.get('debug')

    async def get_Book_Info(self, book_Url):
        try:
            if self.debug_Mode == True:
                logger.debug('Downloading page for parsing...')

            async with aiohttp.ClientSession() as session:
                # Если ссылка не на чтение книгу, а просто на страницу с книгой,
                # то вытягиваем ссылку на чтение из неё
                if 'xmlui/bitstream/handle/asu' not in book_Url:
                    book_Url = await Parser.get_Read_Link(session, book_Url, self.debug_Mode)
                    
                    if 'error' in book_Url:
                        return book_Url
                    
                # Скачиваем страничку для чтения и дергаем из неё инфу о книге
                async with session.get(book_Url) as request:
                    if request.status == 200:
                        request = await request.read()
                    else:
                        return {'error' : f'Can\'not dowload page for parsing - {request.status}'}

            if self.debug_Mode == True:
                logger.debug('Page loaded successfully...')

        except Exception as error:
            logger.exception(f'Smth went wrong on getting link, error - {error}')
            return {'error' : 'Can\'not get link for downloading page'}

        book_Info = Parser.get_Book_ID(request, self.debug_Mode)

        return book_Info 

    @classmethod
    async def get_Read_Link(cls, session, link, debug_Mode):
        if debug_Mode == True:
            logger.debug('Book page not found, searching it in link...')

        async with session.get(link) as request:   
            if request.status == 200:
                page = await request.read()
            else:
                return {'error' : 'Can\'not dowload page for finding book link'}

        book_Url = Parser.get_Book_Link(page, debug_Mode)

        if book_Url == None:
            return {'error' : 'Can\'not get book link from page'}
        else:
            return book_Url

    @classmethod
    def get_Book_ID(cls, page, debug_Mode):
        if debug_Mode == True:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        link = soup.frame.extract()['src']

        try:
            if debug_Mode == True:
                logger.debug('Parsing the page to get book name and ID...')

            temp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')

            id_For_Headers = temp[0].replace('id=', '') + '.7book'
            name_For_Headers = temp[1].replace('name=', '').replace('.7book', '')

            id_For_Request = temp[0].replace('id=', '')
            name_For_Request = temp[1].replace('name=', '')
        
        except Exception as error:
            logger.exception(f'Crash on getting Book_ID and Book_Name, error - {error}')
            return {'error' : f'Crash on getting Book_ID and Book_Name, error - {error}'}

        if debug_Mode == True:
            logger.debug(f'Book name - {name_For_Request}, Book ID - {id_For_Request}')

        return {
            'headers_id' : id_For_Headers, 'request_id' : id_For_Request, 
            'headers_name' : name_For_Headers, 'request_name' : name_For_Request
        }

    @classmethod
    def get_Book_Link(cls, link, debug_Mode):
        main_Link = 'http://elibrary.asu.ru'

        if debug_Mode == True:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(link, 'lxml')
        content = soup.find_all('a', href = True)

        for line in content:
            tmp = line['href']
                    
            if 'xmlui/bitstream/handle/asu' in tmp:
                main_Link += tmp

                if debug_Mode == True:
                    logger.debug(f'Link for book reading founded - {main_Link}, dowloading page with it...')
                
                return main_Link

        if main_Link == 'http://elibrary.asu.ru':
            logger.info('Link for book reading not founded')
            return None

class Book:
    def __init__(self, debug, count_Of_Pages, info):
        self.debug_Mode = debug
        self.count_Of_Pages = count_Of_Pages
        self.id_For_Headers = info.get('headers_id')
        self.id_For_Request = info.get('request_id')
        self.name_For_Headers = info.get('headers_name')
        self.name_For_Request = info.get('request_name')
        
    async def download(self):
        tasks = []

        generator = SystemRandom()
        
        # Готовим обманку
        headers['Referer'] = f'http://elibrary.asu.ru/els/files/book' \
                             f'?name={self.name_For_Headers}&id={self.id_For_Headers}'

        # Выставляем максимальный delay
        if self.count_Of_Pages < 50:
            cooldown = 5
        elif self.count_Of_Pages < 85:
            cooldown = 10
        elif self.count_Of_Pages >= 100:
            cooldown = 60
        elif self.count_Of_Pages >= 250:
            cooldown = 120

        if self.debug_Mode == True:
            logger.debug(f'Delay value set to {cooldown}')
            
        async with aiohttp.ClientSession() as session:
            for task_Num in range(1, self.count_Of_Pages + 1):
                tasks.append(
                    asyncio.create_task(
                        Book.__downloader(
                            session,
                            f'http://elibrary.asu.ru/els/files/test/' \
                            f'?name={self.name_For_Request}&id={self.id_For_Request}' \
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
            logger.debug(f'Waiting {cooldown} seconds before downloading page №{num_Of_Task}')

        await asyncio.sleep(cooldown)

        if debug_Mode == True:
            logger.debug(f'Downloading page №{num_Of_Task}')
        
        try:
            async with session.get(link, headers = headers) as request:
                if request.status == 200:
                    return await request.read()
                else:
                    return None

        except Exception as error:
            logger.exception(f'Can\'not download page №{num_Of_Task}, error - {error}')
            return None

if __name__ == '__main__':
    arg_Parser = ArgumentParser(description = 'Скрипт для выкачивания чего-то с elibrary.asu.ru')
    arg_Parser.add_argument('-d', '--debug', action = 'store_true', help = 'Enable debug mode')
    arg_Parser.add_argument('-o', '--output-dir', type = str, help = 'Change output directory')
    arg_Parser.add_argument('-f', '--file-name', type = str, help = 'Change file name')
    required = arg_Parser.add_argument_group('Required')    
    required.add_argument('-p', '--pages', help = 'Количество страниц', type = int, required = True)
    required.add_argument('-l', '--link', help = 'Ссылка на книгу', type = str, required = True)

    args = vars(arg_Parser.parse_args())

    page_Count = args.get('pages')
    output_File_Name = args.get('file_name') or 'output'
    Path = args.get('output_dir') or str(dirname(abspath(__file__)))

    # Проверка ввода
    if page_Count <= 0:
        print('Количество страниц меньше или равно 0')
        exit(1)
    
    # Проверка на корректность указанного пути
    if Path.endswith('/') is False:
        Path += '/'

    logger.add(
        'log.file', 
        colorize = True, backtrace = False, diagnose = False,
        format = '{time} {message}', level = 'DEBUG'
    )

    loop = asyncio.get_event_loop()

    # Создаем экземпляры классов
    parser = Parser(args)
    
    # Получаем ID и название книги
    # Они слегка отличаются для headers и для ссылки на скачивание, посему они дублируются
    book_Info = loop.run_until_complete( 
        parser.get_Book_Info(args.get('link'))
    )

    # Если что-то пошло не так
    if 'error' in book_Info:
        print(book_Info.get('error'))
        loop.close()
        exit(1)
    
    book = Book(
        args.get('debug'),
        page_Count,
        book_Info 
    )

    print('Downloading pages ...')

    # Выкачиваем все странички
    book_Pages = loop.run_until_complete(
        book.download()
    )

    # Проверяем, все ли скачалось
    for page, page_Num in zip(book_Pages, range(1, page_Count + 1)):
        if page is None:
            print(f'Не удалось загрузить страницу №{page_Num + 1}')

    # Если файл с таким названием уже существует, то запрашиваем другое название
    while exists(f'{Path}{output_File_Name}.pdf') is True:
        output_File_Name = str(
            input(
                f'Файл {output_File_Name} уже существует, введите другое название - '
            )
        )

    print('Making pdf file ...')

    # Конвертируем все в PDF
    with open(f'{Path}{output_File_Name}.pdf', 'wb') as file:
        file.write(
            convert(
                [res for res in book_Pages]
            )
        )

    loop.close()
    print('Done')