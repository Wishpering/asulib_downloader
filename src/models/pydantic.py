from pydantic import BaseModel

class BookInfo(BaseModel):
    """ Содержит в себе ID книги """

    headers_id: str
    request_id: str
    headers_name: str
    request_name: str