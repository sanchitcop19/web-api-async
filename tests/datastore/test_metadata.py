"""Test functionality of the dataset metadata object."""

import unittest

from vizier.datastore.annotation.dataset import DatasetMetadata


class TestDatasetMetadata(unittest.TestCase):

    def test_add_and_delete_metadata(self):
        """Test functionality to add and delete annotations."""
        annotations = DatasetMetadata()
        annotations.add(column_id=0, key='A', value=0)
        annotations.add(column_id=0, key='A', value=1)
        annotations.add(column_id=0, key='A', value=0)
        annotations.add(column_id=1, key='A', value=0)
        annotations.add(column_id=1, key='A', value=1)
        self.assertEqual(len(annotations.columns), 5)
        annotations.remove(column_id=0, value=1)
        self.assertEqual(len(annotations.columns), 4)
        annos = annotations.for_column(column_id=0)
        self.assertEqual(len(annos), 2)
        for a in annos:
            self.assertEqual(a.key, 'A')
            self.assertEqual(a.value, 0)
        annotations.add(row_id=0, key='A', value=0)
        annotations.add(row_id=0, key='B', value=1)
        annotations.add(row_id=0, key='A', value=0)
        annotations.add(row_id=1, key='A', value=0)
        annotations.add(row_id=1, key='A', value=1)
        self.assertEqual(len(annotations.rows), 5)
        annotations.remove(row_id=0, key='A')
        self.assertEqual(len(annotations.rows), 3)
        self.assertEqual(len(annotations.columns), 4)
        annos = annotations.for_row(row_id=0)
        self.assertEqual(len(annos), 1)
        self.assertEqual(annos[0].key, 'B')
        self.assertEqual(annos[0].value, 1)
        annotations.add(column_id=0, row_id=0, key='A', value=0)
        annotations.add(column_id=1, row_id=0, key='B', value=1)
        annotations.add(column_id=1, row_id=0, key='A', value=0)
        annotations.add(column_id=1, row_id=1, key='A', value=0)
        annotations.add(column_id=1, row_id=0, key='A', value=1)
        self.assertEqual(len(annotations.cells), 5)
        annotations.remove(row_id=0, column_id=1)
        self.assertEqual(len(annotations.cells), 2)


if __name__ == '__main__':
    unittest.main()
