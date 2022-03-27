from flask import Flask
import re
import yaml
from migrator import migrate

from pathlib import Path


def convert_from_xml_to_json():
    migrations = []

    with open('changelog.xml', 'r') as changelog:
        for line in changelog.readlines():
            migration = {}

            match = re.findall(r'file="([^"]+)"', line)

            if len(match) > 0:
                migration['file'] = match[0]

            match = re.findall(r'context="([^"]+)"', line)

            if len(match) > 0:
                context = match[0]

                # remove all white spaces
                # context = re.sub(r'\s+', '', context)

                # split by comma
                # context = context.split(',')

                migration['context'] = context

            if 'file' in migration:
                migrations.append(migration)

    return migrations


def convert_from_xml_to_yaml():
    migrations = convert_from_xml_to_json()

    with open('changelog.yaml', 'w') as changelog:
        yaml.dump(migrations, changelog, sort_keys=False)
