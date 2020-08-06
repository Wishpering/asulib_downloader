from asyncio import sleep, gather, create_task
from bs4 import BeautifulSoup as bs4
from random import SystemRandom

import models.errors as errors
from models.pydantic import BookInfo
from utils.logger import Logger

logger = Logger.get(__file__)

class WebPage:
    """
    Представляет собой Web-страницу
    """

    __headers = {
        'Host' : 'elibrary.asu.ru',
        'Connection' : 'close',
        'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
        'Accept' : 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Encoding' : 'gzip, deflate',
        'Accept-Language' : 'en-GB,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6'
    }

    def __init__(self, session, link):
        """
        session = aiohttp.Session
        link = link for book page
        """

        self.session = session
        self.link = link

    @classmethod
    def get_headers(cls):
        """
        Получить текущие Headers
        """

        return cls.__headers

    async def download(self, **kwargs):
        """
        Загрузить страницу
        kwargs:
            headers - headers for request, default=WebPage.__headers
        """

        headers = kwargs.get('headers', WebPage.__headers)

        async with self.session.get(
            self.link, 
            headers=headers
        ) as request:
            if request.status == 200:
                return await request.read()
            else:
                raise errors.BookDownloadError(request.status)

class BookPage(WebPage):
    """
    Представляет собой страницу с информацией о книге
    """

    def __init__(self, session, link, **kwargs):
        """
        session = aiohttp.Session
        link = link for book page
        kwargs:
            debug(bool) - enable\disable debug mode (default = False)
        """

        super().__init__(session, link)

        self.debug_mode = kwargs.get('debug', False)

    async def get_read_link(self):
        """
        Метод возвращает ссылку на чтение книги
        """

        page = await self.download()
        read_url = self.find_book_readlink(page)

        if read_url == -1:
            raise errors.ReadLinkNotFound
        else:
            return read_url

    def find_book_readlink(self, page):
        """
        Поиск ссылки на чтение на скаченной странице
        """

        link = 'http://elibrary.asu.ru'

        if self.debug_mode:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        page_content = soup.find_all('a', href=True)

        for line in page_content:
            tmp = line['href']
                    
            if 'xmlui/bitstream/handle/asu' in tmp:
                link += tmp

                if self.debug_mode:
                    logger.debug(
                        f'Link for book reading founded - {link}, dowloading page with it...'
                    )
                
                return link

        if link == 'http://elibrary.asu.ru':
            logger.critical('Link for book reading not founded')
            return -1

    def find_book_info(self, page):
        """
        Поиск служебной информации о книге на скаченной странице
        """

        if page is None:
            raise errors.EmptyBookPage

        if self.debug_mode:
            logger.debug('Preparing Beautifulsoup with lxml engine')

        soup = bs4(page, 'lxml')
        link = soup.frame.extract()['src']

        if self.debug_mode:
            logger.debug('Parsing the page to get book name and ID...')

        if link is not None:
            tmp = str(link).split('http://elibrary.asu.ru/els/files/book?')[1].split('&')
        else:
            raise errors.BookInfoNotFound('Link for book reader is empty')
        
        headers_id = tmp[0].replace('id=', '')
        headers_name = tmp[1].replace('name=', '').replace('.7book', '')

        request_id = tmp[0].replace('id=', '')
        request_name = tmp[1].replace('name=', '')
        
        if self.debug_mode:
            logger.debug(f'Book name - {request_name}, Book ID - {request_id}')

        return BookInfo(
            headers_id=headers_id, request_id=request_id, 
            headers_name=headers_name, request_name=request_name
        )

    async def parse(self):
        """
        Метод возвращает информацию о книге
        return = models.pydantic.BookInfo
        """

        if 'xmlui/bitstream/handle/asu' not in self.link:
            if self.debug_mode:
                logger.debug('Book page not found, searching it in link...')

            self.link = await self.get_read_link()

        book_page = await self.download()

        if self.debug_mode:
            logger.debug('Page loaded successfully...')

        return self.find_book_info(book_page)

class ReaderPage(WebPage):
    """
    Представляет собой одиночную страницу в читалке сайта
    """

    def __init__(self, session, link, **kwargs):
        """
        session = aiohttp.Session
        link = link for book page
        kwargs:
            debug(bool) - enable\disable debug mode (default = False)
            headers - headers for request
            cooldown - cooldown before request
            task_num - page num
        """

        super().__init__(session, link)

        self.debug_mode = kwargs.get('debug', False)
        self.headers = kwargs.get('headers', None)
        self.cooldown = kwargs.get('cooldown', 0)
        self.task_num = kwargs.get('task_num', 0)

    async def get(self):
        """
        Скачать страницу
        """

        if self.cooldown != 0:
            if self.debug_mode:
                logger.debug(f'Waiting {self.cooldown} seconds before downloading page №{self.task_num}')

            await sleep(self.cooldown)

        if self.debug_mode:
            logger.debug(f'Downloading page №{self.task_num}')
        
        try:
            return await self.download()
        except Exception as error:
            logger.exception(f'Can\'not download page №{self.task_num}, error - {error}')
            return -1

class ReaderPagePool:
    """
    Представляет собой всю читалку сайта
    """

    def __init__(self, session, pages_num, info, **kwargs):
        """
        session = aiohttp.Session
        pages_num = количество страниц в книге
        info = models.pydantic.BookInfo
        kwargs:
            debug(bool) - enable\disable debug mode (default = False)
        """

        self.debug_mode = kwargs.get('debug', False)
        self.session = session

        self.id_for_headers = info.headers_id
        self.id_for_request = info.request_id
        self.name_for_headers = info.headers_name
        self.name_for_request = info.request_name
        self.pages_count = pages_num

    async def get_all(self):
        """Скачать все страницы книги"""

        generator = SystemRandom()

        # Выставляем максимальный delay
        if self.pages_count < 50:
            cooldown = 5
        elif self.pages_count < 85:
            cooldown = 10
        elif self.pages_count >= 100:
            cooldown = 60
        elif self.pages_count >= 250:
            cooldown = 120
        else:
            cooldown = 30

        if self.debug_mode:
            logger.debug(f'Delay value set to {cooldown}')

        # Готовим обманку
        headers = WebPage.get_headers()
        headers['Referer'] = f'http://elibrary.asu.ru/els/files/book' \
                             f'?name={self.name_for_headers}&id={self.name_for_request}.7book'
            
        pages = []

        for task_num in range(1, self.pages_count + 1):
            page = ReaderPage(
                self.session,
                f'http://elibrary.asu.ru/els/files/test/' \
                f'?name={self.name_for_request}&id={self.id_for_request}' \
                f'&page={task_num}&mode=1',
                debug=self.debug_mode,
                headers=headers,
                cooldown=generator.uniform(0, cooldown),
                task_num=task_num
            )

            pages.append(page)

        tasks = []

        for page in pages:
            tasks.append(
                create_task(
                    page.get()
                )
            )
            
        return await gather(*tasks)
