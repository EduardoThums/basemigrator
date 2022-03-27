from os import walk
import pathlib
from pymysql.connections import Connection
import re

SQL_PATH_REGEX = r'file="([^"]+)'

__conn = None


def execute_migration(app, changelog):
    global __conn
    # changelog = pathlib.Path(__file__).parent.absolute()

    # __conn = __connect(app)
    # __create_lock()

    # create connection
    # 1. check if database is locked
    # 2. if it is, wait until lock is released(max 1 min)
    # 3. if its not, create lock

    # check if necessary tables exist
    # if not: create necessary tables

    # execute each script on a single transaction
    # take care of commit and rollback if necessary

    # close connection
    # print(changelog)
    # print(f'{pathlib.Path(__file__).parent.absolute()}/changelog.xml')

    for script in __retrive_scripts(changelog):
        print(script)
    # for root, _, files in walk(migrations_path):

    #     for name in [x for x in files if x.endswith('.sql')]:
    #         with open(f'{root}/{name}', 'r') as file:
    #             print(file.read())


def __create_lock():
    pass


def __release_lock():
    pass


def __connect(app):
    if __conn is None:
        __conn = Connection(
            user=app.config.get('DB_USER', 'cwi'),
            password=app.config.get('DB_PASSWORD', 'cwi'),
            host=app.config.get('DB_HOST', 'localhost'),
            database=app.config.get('DB_NAME', 'cwi')
        )

    elif not __conn.open:
        __conn.ping(reconnect=True)

    return __conn


def __retrive_scripts(changelog):

    with open(f'{changelog}/changelog.xml', 'r') as file:
        for line in file.readlines():
            path = re.findall(SQL_PATH_REGEX, line)

            if len(path) > 0:
                path = path[0]

                yield f'{changelog}/{path}.sql'
