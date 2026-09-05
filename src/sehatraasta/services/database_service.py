from sehatraasta.storage.db import backup_database, restore_database


class DatabaseService:
    def __init__(self, database_path):
        self.database_path = database_path

    def backup(self, output_path):
        return backup_database(self.database_path, output_path)

    def restore(self, backup_path, output_path):
        return restore_database(backup_path, output_path)
