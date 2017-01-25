# Система управления данными о работе котельных МУП "Волгоградское коммунальное хозяйство"

## Установка

```
git clone https://github.com/Gerold103/volgograd.git
cd volgograd/www
python3 setup.py install # или sudo python3 setup.py install
mysql -u <example_user> -p < sql_prepare.sql
```
, где вместо `example_user` необходимо ввести ваше имя пользователя mysql

## Подготовка к запуску

Перед запуском вам необходимо создать файл secret_conf.json следующего вида:

```
{
	"db_host": "localhost",            # хост, где работает mysql сервер
	"db_user": "example_user",         # mysql пользователь
	"db_passwd": "mypassword",         # пароль от mysql пользователя, заданного выше
	"cookie_secret": "SECRET_COOKIE",  # секретный ключ для cookie
	"pepper": "wgew@#%@%674766&(^67"   # произвольный набор символов - чем сложнее, тем надежнее защищена база
}
```

Опциональные параметры secret_conf:
* max_db_connections - максимальное количество зарезервинованных соединений с базой данных;
* db_idle_seconds - когда незакрытое соединение будет автоматически уничтожено;
* db_connection_timeout - таймаут на соединение с базой;
* db_charset - кодировка базы;

Чтобы можно было загружать файлы таблиц и смотреть их, надо создать пользователей.
Создадим двух пользователей: администратора, который сможет загружать и смотреть таблицы, а так же простого пользователя,
который может только смотреть таблицы.
Сначала сгенерируем пароли:
```
python3
>>> import secret_conf
>>> secret_conf.parse_config()
>>> secret_conf.generate_password_hash('123456') # первый пароль
('869DMHlD', 'wgew@#%@%674766&(^67MHlD$IspufLNDWbanb6mhltuvtAmCAphp6tdd')
>>> secret_conf.generate_password_hash('qwerty') # второй пароль
('IOKqD7jV', 'wgew@#%@%674766&(^67D7jV$IFRwpkZ6HfSfotHSgDESeI0NmvaLY2kM')
```
Далее загрузим пользователей в базу:

```
mysql -u <example_user> -p
mysql> use volgograd;
mysql> insert into users values (NULL, '<почта администратора>', 'wgew@#%@%674766&(^67MHlD$IspufLNDWbanb6mhltuvtAmCAphp6tdd', '869DMHlD', 'Администратор', 7);
mysql> insert into users values (NULL, '<почта простого пользователя>', 'wgew@#%@%674766&(^67D7jV$IFRwpkZ6HfSfotHSgDESeI0NmvaLY2kM', 'IOKqD7jV', 'Пользователь', 2);
```

Для входа пользователи на сайте должны использовать пароли, которые были переданы аргументами в generate_password_hash.
То есть, например, пользователь Администратор для входа на сайте должен будет указать выбранный email, и пароль `123456` из примера выше.

## Запуск

В директории www выполните:

`python3 main.py -p <порт>`

После чего можно заходить на сайт через:<br>
http://localhost:port/

Например, если была выполнена команда:
`python3 main.py -p 8888`

То сайт доступен по адресу
http://localhost:8888/

## Тесты

Для запуска тестов необходимо выполнить команду:
`python3 main.py -p <порт> --test`

То есть достаточно указать аргумент --test к запуску сервера и тесты будут автоматически запущены.
