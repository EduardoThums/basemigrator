import yaml
from os.path import exists
from xml.etree import ElementTree


def read_changelog(changelog):
    supported__extensions = [
        ('xml', _read_from_xml),
        ('yaml', _read_from_yaml)
    ]

    for extension, read_callback in supported__extensions:
        full_path = f'{changelog}/changelog.{extension}'

        if exists(full_path):
            migrations = read_callback(full_path)

            return migrations

    raise FileNotFoundError('The changelog file was not found')


def _read_from_xml(full_path):
    tree = ElementTree.parse(full_path)
    root = tree.getroot()

    for child in root:
        yield child.attrib


def _read_from_yaml(full_path):
    with open(full_path, 'r') as file:
        migrations = yaml.load(file, Loader=yaml.FullLoader)

    return migrations
