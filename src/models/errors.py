class BookDownloadError(Exception):
    def __init__(self, http_code):
        self.code = http_code
    
    def __str__(self):
        return(repr(self.code))

class EmptyBookPage(Exception):
    pass

class ReadLinkNotFound(Exception):
    pass

class LinkNotFound(Exception):
    def __init__(self, error):
        self.error = error
    
    def __str__(self):
        return(repr(self.error))

class BookInfoNotFound(Exception):
    def __init__(self, error):
        self.error = error
    
    def __str__(self):
        return(repr(self.error))