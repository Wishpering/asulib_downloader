#!/usr/bin/python3

import logging
from bs4 import BeautifulSoup as bs4
from os.path import dirname, abspath, exists
from os import mkdir
import asyncio
from threading import Thread
import aiohttp
from random import uniform

def start_background_loop(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()          

class Loop:
    loop = asyncio.new_event_loop()
    main_Thread = Thread(target = start_background_loop, args = (loop,), daemon = True).start()    

class Parcer:
    def __init__(self, logger):
        self.logger = logger

    async def get_Link(self, book_Url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(book_Url) as request:
            
                    if request.status != 200:
                        self.logger.exception('Crash on downloading page for parsing with BeautifulSoup')
                        exit()
                
                    request = await request.read()

        except Exception as error:
            self.logger.exception(error)
                
        soup = bs4(request, 'lxml')
        link = soup.frame.extract()['src']

        try:
            temp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')

            id_For_Headers = str(temp[0]).replace('id=', '') + '.7book'
            name_For_Headers = str(temp[1]).replace('name=', '').replace('.7book', '')

            id_For_Request = str(temp[0]).replace('id=', '')
            name_For_Request = str(temp[1]).replace('name=', '')
        
        except:
            self.logger.exception('Crash on getting Book_ID and Book_Name')

        return id_For_Headers, id_For_Request, name_For_Headers, name_For_Request

class Book:
    def __init__(self, Path, loop, logger):
        self.Path = Path
        self.loop = Loop
        self.logger = logger

    async def download_Book(self, headers, count_Of_Pages, id_For_Headers, id_For_Request, name_For_Headers, name_For_Request):
        tasks = []

        for i in range(1, page_Count + 1):
            tasks.append(
                asyncio.create_task(
                    Book.__downloader(
                        self,
                        'http://elibrary.asu.ru/els/files/test/?name=' + name_For_Request +'&id=' + id_For_Request +'&page=' + str(i) + '&mode=1',
                        headers  
                    )
                )
            )

        print(len(tasks))

        return await asyncio.gather(*tasks)

    async def __downloader(self, link, headers):
        await asyncio.sleep(uniform(0, 5))

        try:
            async with aiohttp.ClientSession() as session:
                    async with session.get(link, headers = headers) as request:
                        if request.status == 200:
                            return await request.read()
                        else:
                            return -1

        except Exception as error:
            self.logger.exception(error)

if __name__ == '__main__':
    Path = str(dirname(abspath(__file__))) + '/'

    # Проверяем, что есть директория под скаченные файлы
    if exists(Path + 'output') is False:
        mkdir(Path + 'output')

    logging.basicConfig(filename = Path + 'log.txt', level = logging.DEBUG)
    log_File = logging.getLogger("Book downloader")

    # Создаем экземпляры классов
    parcer = Parcer(log_File)
    downloader = Book(Path, Loop.loop, log_File)

    url_For_Downloading = str(input('Ссылка на книгу - '))
    page_Count = int(input('Сколько страниц в книге - '))

    # Получаем ID и название книги
    # Они слегка отличаются для Headers и для ссылки на скачивание, посему они дублируются
    id_For_Headers, id_For_Request, name_For_Headers, name_For_Request = asyncio.run_coroutine_threadsafe(parcer.get_Link(url_For_Downloading), Loop.loop).result()

    # Готовим headers для обманки
    headers = {
    'Host' : 'elibrary.asu.ru',
    'Connection' : 'keep-alive',
    'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
    'DNT' : '1',
    'Accept' : 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Referer' : 'http://elibrary.asu.ru/els/files/book?name=' + str(name_For_Headers) + '&id=' + str(id_For_Headers),
    'Accept-Encoding' : 'gzip, deflate',
    'Accept-Language' : 'en-GB,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6'
    }

    # Выкачиваем все странички
    result_Of_Downloader = asyncio.run_coroutine_threadsafe(
        downloader.download_Book(
            headers, page_Count, id_For_Headers, id_For_Request, name_For_Headers, name_For_Request
        ),
        Loop.loop
    ).result()

    # Записываем все скаченное в файлы
    for res, count in zip(result_Of_Downloader, range(1, page_Count + 1)):
        with open(Path + 'output/page' + str(count), 'wb') as file:
            if res == -1:
                print('Не удалось загрузить страницу №' + str(count))
            else:
                file.write(res)