import warnings
import re
from time import sleep
from hashlib import md5
from .changelog_reader import read_changelog


AUTHOR_AND_ID_REGEX = r'--[\s+]?changeset[\s+]?([^:]+):([^\s]+)[\s+]?(endDelimiter:)?([^\s]+)?'
COMMENT_REGEX = r'--.*'
EMPTY_LINE_REGEX = r'^\n'

WAIT_LOCK = 10
WAIT_PER_STEP = 5

applied_migrations = None
current_context = None


def migrate(app, changelog, context=None):
    global current_context
    current_context = context

    print('\nExecuting Update')

    Transaction.init(app)
    Transaction.connect(app)

    try:
        _create_lock()

        print(f"Reading from {app.config.get('DB_DATABASE', 'hub')}.DATABASECHANGELOG")

        migrations = read_changelog(changelog)

        for migration in migrations:
            _apply_migration(changelog, migration)

    except Exception as e:
        _release_lock()
        Transaction.close()

        raise e

    else:
        _release_lock()
        Transaction.close()

        print('Update Successful\n')


def _create_lock():
    wait_lock = WAIT_LOCK

    with Transaction() as transaction:
        while wait_lock > 0:
            transaction.execute('SELECT LOCKED AS "LOCKED", LOCKEDBY AS "LOCKEDBY" FROM DATABASECHANGELOGLOCK')
            current_lock = transaction.fetchone()

            if isinstance(current_lock.get('LOCKED'), bytes):
                # workaround to support bit column
                is_locked = current_lock.get('LOCKED').hex()[-1] == '1'

            elif isinstance(current_lock.get('LOCKED'), (bool, int)):
                is_locked = bool(current_lock.get('LOCKED'))

            if is_locked:
                print(f'Database is currently locked! Waiting {WAIT_PER_STEP} seconds to try again...')

                sleep(WAIT_PER_STEP)
                wait_lock -= WAIT_PER_STEP

            else:
                print('Successfully acquired change log lock')
                transaction.execute('UPDATE DATABASECHANGELOGLOCK SET LOCKED = TRUE WHERE ID = 1')
                return

        else:
            print(f'Waited {WAIT_LOCK} seconds but the lock it\'s not released, given up!')


def _release_lock():
    with Transaction() as transaction:
        transaction.execute('UPDATE DATABASECHANGELOGLOCK SET LOCKED = FALSE WHERE ID = 1')
        print('Successfully released change log lock')


def _apply_migration(changelog, migration):
    file_name = migration.get('file')
    context = migration.get('context')

    with open(f'{changelog}/{file_name}', 'r') as file:
        raw_text = file.read()
        md5sum = md5(raw_text.encode('utf-8')).hexdigest()

        if not _should_apply_migration(file_name, context):
            return

        metadata = _extract_migration_metadata(raw_text)
        sql = re.sub(COMMENT_REGEX, '', raw_text)

        print(f'--> {file_name}::executed')

        with Transaction() as transaction:
            for statement in sql.split(metadata.get('delimiter')):
                statement = re.sub(EMPTY_LINE_REGEX, '', statement, flags=re.MULTILINE).strip()

                if statement:
                    transaction.execute(statement)

            transaction.execute(
                '''
                INSERT INTO DATABASECHANGELOG (
                    ID,
                    AUTHOR,
                    FILENAME,
                    DATEEXECUTED,
                    ORDEREXECUTED,
                    EXECTYPE,
                    MD5SUM,
                    DESCRIPTION
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    NOW(),
                    COALESCE(
                        (SELECT ORDEREXECUTED + 1 FROM DATABASECHANGELOG d ORDER BY ORDEREXECUTED DESC LIMIT 1),
                        1
                    ),
                    'EXECUTED',
                    %s,
                    'sql'
                );
                ''',
                [
                    metadata['migration_id'],
                    metadata['author'],
                    file_name,
                    md5sum
                ]
            )

            global applied_migrations
            applied_migrations.append(file_name)

        print(f'--> {file_name}::ran successfully')


def _should_apply_migration(file_name, context):
    global current_context

    # if the migration has any context, only apply when the current context are one of them
    if context is not None:
        if not re.search(fr'\b{current_context}\b', context):
            return False

    migrations = _get_already_applied_migrations()

    return file_name not in migrations


def _extract_migration_metadata(raw_text):
    match = re.findall(AUTHOR_AND_ID_REGEX, raw_text)

    if len(match) > 0:
        metadata = match[0]

        author = metadata[0]
        migration_id = metadata[1]
        delimiter = metadata[3].replace('\\', '') or ';'

        return {'author': author, 'migration_id': migration_id, 'delimiter': delimiter}

    else:
        raise ValueError('Migration metadata not found!')


def _get_already_applied_migrations():
    global applied_migrations

    if applied_migrations is None:
        applied_migrations = Transaction.select_autocommit(
            'SELECT FILENAME AS "FILENAME" FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED'
        )

        applied_migrations = [migration.get('FILENAME') for migration in applied_migrations]

    return applied_migrations


class Transaction:

    connection = None
    _engine = None

    @classmethod
    def connect(cls, app):
        # MySQL - PyMySQL
        try:
            from pymysql.connections import Connection
            from pymysql.cursors import DictCursor

            if cls.connection is None:
                cls.connection = Connection(
                    user=app.config.get('DB_USER', 'user'),
                    password=app.config.get('DB_PASSWORD', 'password'),
                    host=app.config.get('DB_HOST', 'localhost'),
                    database=app.config.get('DB_DATABASE', 'foo'),
                    port=app.config.get('DB_PORT', 3306),
                    cursorclass=DictCursor
                )

            elif not cls.connection.open:
                cls.connection.ping(reconnect=True)

            cls._engine = 'MYSQL'
            return

        except ModuleNotFoundError:
            pass

        # PostegreSQL - Pyscopg
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor as DictCursorPostgres

            if cls.connection is None or cls.connection.closed:
                cls.connection = psycopg2.connect(
                    user=app.config.get('DB_USER', 'user'),
                    password=app.config.get('DB_PASSWORD', 'password'),
                    host=app.config.get('DB_HOST', 'localhost'),
                    dbname=app.config.get('DB_DATABASE', 'foo'),
                    port=app.config.get('DB_PORT', 5432),
                    cursor_factory=DictCursorPostgres
                )

            cls._engine = 'POSTGRESQL'
            return

        except ModuleNotFoundError:
            pass

        raise ModuleNotFoundError('No database module found! The supported ones are: PyMySQL, Psycopg')

    def __enter__(self):
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_value:
            self.connection.rollback()

            return False

        self.connection.commit()
        return True

    @classmethod
    def init(cls, app):
        cls.connect(app)

        with cls() as transaction:
            # ignore warnings telling that the tables already exists
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                if cls._engine == 'MYSQL':
                    transaction.execute(
                        '''
                        CREATE TABLE IF NOT EXISTS DATABASECHANGELOG (
                            ID varchar(255) NOT NULL,
                            AUTHOR varchar(255) NOT NULL,
                            FILENAME varchar(255) NOT NULL,
                            DATEEXECUTED datetime NOT NULL,
                            ORDEREXECUTED int(11) NOT NULL,
                            EXECTYPE varchar(10) NOT NULL,
                            MD5SUM varchar(35) DEFAULT NULL,
                            DESCRIPTION varchar(255) DEFAULT NULL,
                            COMMENTS varchar(255) DEFAULT NULL,
                            TAG varchar(255) DEFAULT NULL,
                            LIQUIBASE varchar(20) DEFAULT NULL,
                            CONTEXTS varchar(255) DEFAULT NULL,
                            LABELS varchar(255) DEFAULT NULL,
                            DEPLOYMENT_ID varchar(10) DEFAULT NULL
                        )
                        '''
                    )

                    transaction.execute(
                        '''
                        CREATE TABLE IF NOT EXISTS DATABASECHANGELOGLOCK (
                            ID int(11) NOT NULL,
                            LOCKED bit(1) NOT NULL,
                            LOCKGRANTED datetime DEFAULT NULL,
                            LOCKEDBY varchar(255) DEFAULT NULL,
                            PRIMARY KEY (ID)
                        )
                        '''
                    )

                    transaction.execute(
                        '''
                        INSERT IGNORE INTO DATABASECHANGELOGLOCK (
                            ID,
                            LOCKED,
                            LOCKGRANTED,
                            LOCKEDBY
                        )
                        VALUES (
                            1,
                            FALSE,
                            NULL,
                            NULL
                        )
                        '''
                    )

                elif cls._engine == 'POSTGRESQL':
                    transaction.execute(
                        '''
                        CREATE TABLE IF NOT EXISTS DATABASECHANGELOG (
                            ID varchar(255) NOT NULL,
                            AUTHOR varchar(255) NOT NULL,
                            FILENAME varchar(255) NOT NULL,
                            DATEEXECUTED timestamp NOT NULL,
                            ORDEREXECUTED INTEGER NOT NULL,
                            EXECTYPE varchar(10) NOT NULL,
                            MD5SUM varchar(35) DEFAULT NULL,
                            DESCRIPTION varchar(255) DEFAULT NULL,
                            COMMENTS varchar(255) DEFAULT NULL,
                            TAG varchar(255) DEFAULT NULL,
                            LIQUIBASE varchar(20) DEFAULT NULL,
                            CONTEXTS varchar(255) DEFAULT NULL,
                            LABELS varchar(255) DEFAULT NULL,
                            DEPLOYMENT_ID varchar(10) DEFAULT NULL
                        )
                        '''
                    )

                    transaction.execute(
                        '''
                        CREATE TABLE IF NOT EXISTS DATABASECHANGELOGLOCK (
                            ID INTEGER NOT NULL,
                            LOCKED BOOLEAN NOT NULL,
                            LOCKGRANTED timestamp DEFAULT NULL,
                            LOCKEDBY varchar(255) DEFAULT NULL,
                            PRIMARY KEY (ID)
                        )
                        '''
                    )

                    transaction.execute(
                        '''
                        INSERT INTO DATABASECHANGELOGLOCK (
                            ID,
                            LOCKED,
                            LOCKGRANTED,
                            LOCKEDBY
                        )
                        VALUES (
                            1,
                            FALSE,
                            NULL,
                            NULL
                        )
                        ON CONFLICT(ID) DO NOTHING
                        '''
                    )

                else:
                    raise ValueError(f'Engine {cls._engine} not supported')

    @classmethod
    def close(cls):
        cls.connection.close()

    @classmethod
    def select_autocommit(cls, query, args=[]):
        with cls() as transaction:
            transaction.execute(query, args)
            return transaction.fetchall()
