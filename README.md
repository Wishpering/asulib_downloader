# Описание

Программа, предназначена для скачивания книг/методичик/etc с сайта elibrary.asu.ru

## Getting Started

```bash
git clone https://github.com/Wishpering/asulib_downloader.git
```
## Требования

Python 3.6+, пакеты из файла requirements.txt

## Запуск

Обычный вариант:
```bash
pip3 install -r requirements.txt.
python src -p PAGE_COUNT -l LINK
```
Docker:
```docker
docker build -t TAG .
docker run --rm -it -v $PWD/output_dir:/tmp TAG sh -c "python /code/src -p PAGE_COUNT -l LINK"
```

### Фичи баги и приколы
Указывать количество страниц приходится потому что я не придумал способ подсчета страниц. 