FROM python:alpine3.12

RUN apk add --no-cache libxml2-dev \
    	    	       libxslt-dev \
		       gcc musl-dev \
		       libjpeg-turbo-dev

WORKDIR /code
COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY ./src ./src/

WORKDIR /tmp
CMD ["python3", "/code/src"]