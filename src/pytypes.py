from pydantic import BaseModel

class Book_Info(BaseModel):
    """ Содержит в себе ID книги """

    headers_id: int
    request_id: int
    headers_name: str
    request_name: str