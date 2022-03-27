from pymysql.connections import Connection
from pymysql.cursors import DictCursor
import warnings
import re
from time import sleep
from hashlib import md5
import yaml
from contextlib import suppress


AUTHOR_AND_ID_REGEX = r'--changeset ([^:]+):(.*)'
COMMENT_REGEX = r'--.*'
WAIT_LOCK = 10
WAIT_PER_STEP = 5

applied_migrations = None
current_context = None


def migrate(app, changelog, context):
    global current_context
    current_context = context

    print('Executing Update')

    Transaction.init(app)
    Transaction.connect(app)

    try:
        _create_lock()

        print(f"Reading from {app.config.get('DB_DATABASE', 'hub')}.DATABASECHANGELOG")

        try:
            with open(f'{changelog}/changelog.yaml', 'r') as file:
                migrations = yaml.load(file, Loader=yaml.FullLoader)

        except FileNotFoundError:
            print(f'Failed to read changelog file at {changelog}')

        for migration in migrations:
            _apply_migration(changelog, migration)

    except Exception as e:
        _release_lock()
        Transaction.close()

        raise e

    else:
        _release_lock()
        Transaction.close()

        print('Update Successful')


def _create_lock():
    wait_lock = WAIT_LOCK

    with Transaction() as transaction:
        while wait_lock > 0:
            transaction.execute('SELECT LOCKED, LOCKEDBY FROM DATABASECHANGELOGLOCK ORDER BY ID')
            current_lock = transaction.fetchone()

            # workaround to support bit column
            if current_lock.get('LOCKED').hex()[-1] == '1':
                print(f'Database is currently locked! Waiting {WAIT_PER_STEP} seconds to try again...')

                sleep(WAIT_PER_STEP)
                wait_lock -= WAIT_PER_STEP

            else:
                print('Successfully acquired change log lock')
                transaction.execute('UPDATE DATABASECHANGELOGLOCK SET LOCKED = 1 WHERE ID = 1')
                return

        else:
            print(f'Waited {WAIT_LOCK} seconds but the lock it\'s not released, given up!')


def _release_lock():
    with Transaction() as transaction:
        transaction.execute('UPDATE DATABASECHANGELOGLOCK SET LOCKED = 0 WHERE ID = 1')
        print('Successfully released change log lock')


def _apply_migration(changelog, migration):
    file_name = migration.get('file')
    context = migration.get('context')

    with suppress(FileNotFoundError):
        with open(f'{changelog}/{file_name}', 'r') as file:
            raw_text = file.read()
            md5sum = md5(raw_text.encode('utf-8')).hexdigest()

            metadata = _extract_migration_metadata(raw_text)
            migration_id = metadata.get("migration_id")

            if not _should_apply_migration(migration_id, md5sum, context):
                return

            sql = re.sub(COMMENT_REGEX, '', raw_text)

            print(f'--> {migration_id}::executed')

            with Transaction() as transaction:
                transaction.execute(sql)

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
                        IFNULL(
                            (SELECT ORDEREXECUTED + 1 FROM DATABASECHANGELOG d ORDER BY ORDEREXECUTED DESC LIMIT 1),
                            1
                        ),
                        'EXECUTED',
                        %s,
                        'sql'
                    );
                    ''',
                    [
                        migration_id,
                        metadata['author'],
                        file_name,
                        md5sum
                    ]
                )

            print(f'--> {migration_id}::ran successfully')


def _should_apply_migration(migration_id, md5sum, context):
    global current_context

    # if the migration has any context, only apply when the current context are one of them
    if context is not None:
        if not re.search(fr'\b{current_context}\b', context):
            return False

    migration = _get_already_applied_migrations().get(migration_id)

    if migration is not None:
        old_md5sum = migration.get('md5sum')

        if md5sum != old_md5sum:
            raise Exception(f'Validation error! {migration_id} was: {old_md5sum} but now is: {md5sum}')

        return False

    else:
        return True


def _extract_migration_metadata(raw_text):
    info = re.findall(AUTHOR_AND_ID_REGEX, raw_text)

    if len(info) > 0:
        author = info[0][0]
        migration_id = info[0][1]

        return {'author': author, 'migration_id': migration_id}

    else:
        return {}


def _get_already_applied_migrations():
    global applied_migrations

    if applied_migrations is None:
        applied_migrations = Transaction.select_autocommit(
            'SELECT ID, MD5SUM FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED'
        )

        applied_migrations = {
            migration.get('ID'): {'md5sum': migration.get('MD5SUM')}
            for migration in applied_migrations
        }

    return applied_migrations


class Transaction:

    connection = None

    @classmethod
    def connect(cls, app):
        if cls.connection is None:
            cls.connection = Connection(
                user=app.config.get('DB_USER', 'cwi'),
                password=app.config.get('DB_PASSWORD', 'cwi'),
                host=app.config.get('DB_HOST', 'localhost'),
                database=app.config.get('DB_DATABASE', 'hub'),
                cursorclass=DictCursor
            )

        elif not cls.connection.open:
            cls.connection.ping(reconnect=True)

    def __enter__(self):
        self.connection.begin()
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
            # nothing to see here >.>
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

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

    @classmethod
    def close(cls):
        cls.connection.close()

    @classmethod
    def select_autocommit(cls, query, args=[]):
        with cls() as transaction:
            transaction.execute(query, args)
            return transaction.fetchall()
