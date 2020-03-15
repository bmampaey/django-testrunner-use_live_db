# Based on http://stackoverflow.com/a/5809952/689985

from django.test.runner import DiscoverRunner
from django.test.utils import dependency_ordered

class ByPassableDBDjangoTestSuiteRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        from django.db import connections, DEFAULT_DB_ALIAS

        # First pass -- work out which databases actually need to be created,
        # and which ones are test mirrors or duplicate entries in DATABASES
        mirrored_aliases = {}
        test_databases = {}
        dependencies = {}
        default_sig = connections[DEFAULT_DB_ALIAS].creation.test_db_signature()
        for alias in connections:
            connection = connections[alias]
            test_settings = connection.settings_dict['TEST']
            if test_settings['MIRROR']:
                # If the database is marked as a test mirror, save
                # the alias.
                mirrored_aliases[alias] = test_settings['MIRROR']
            else:
                # Store a tuple with DB parameters that uniquely identify it.
                # If we have two aliases with the same values for that tuple,
                # we only need to create the test database once.
                item = test_databases.setdefault(
                    connection.creation.test_db_signature(),
                    (connection.settings_dict['NAME'], set())
                )
                item[1].add(alias)

                if 'DEPENDENCIES' in test_settings:
                    dependencies[alias] = test_settings['DEPENDENCIES']
                else:
                    if alias != DEFAULT_DB_ALIAS and connection.creation.test_db_signature() != default_sig:
                        dependencies[alias] = test_settings.get('DEPENDENCIES', [DEFAULT_DB_ALIAS])

        # Second pass -- actually create the databases.
        old_names = []
        mirrors = []

        for signature, (db_name, aliases) in dependency_ordered(
                test_databases.items(), dependencies):
            test_db_name = None

            # Actually create the database for the first connection
            for alias in aliases:
                connection = connections[alias]
                if connection.settings_dict.get("USE_LIVE_FOR_TESTS"):
                    continue

                if test_db_name is None:
                    test_db_name = connection.creation.create_test_db(
                        self.verbosity,
                        autoclobber=not self.interactive,
                        serialize=connection.settings_dict.get("TEST_SERIALIZE", True),
                    )
                    destroy = True
                else:
                    connection.settings_dict['NAME'] = test_db_name
                    destroy = False
                old_names.append((connection, db_name, destroy))

        for alias, mirror_alias in mirrored_aliases.items():
            mirrors.append((alias, connections[alias].settings_dict['NAME']))
            connections[alias].settings_dict['NAME'] = (
                connections[mirror_alias].settings_dict['NAME'])

        return old_names
