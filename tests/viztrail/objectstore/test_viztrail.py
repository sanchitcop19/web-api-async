"""Test functionality of the file system viztrail repository."""

import os
import shutil
import unittest


from vizier.viztrail.driver.objectstore.branch import OBJ_METADATA, OBJ_PROPERTIES, OBJ_WORKFLOWS
from vizier.viztrail.driver.objectstore.viztrail import OSViztrailHandle
from vizier.viztrail.driver.objectstore.viztrail import FOLDER_BRANCHES, FOLDER_MODULES
from vizier.viztrail.driver.objectstore.viztrail import OBJ_BRANCHINDEX, OBJ_METADATA, OBJ_PROPERTIES
from vizier.viztrail.base import PROPERTY_NAME


REPO_DIR = './.temp'


class TestOSViztrail(unittest.TestCase):

    def setUp(self):
        """Create an empty repository directory."""
        if os.path.isdir(REPO_DIR):
            shutil.rmtree(REPO_DIR)
        os.makedirs(REPO_DIR)

    def tearDown(self):
        """Delete repository directory.
        """
        shutil.rmtree(REPO_DIR)

    def test_create_and_delete_branch(self):
        """Test creating and deleting a new branch."""
        base_path = os.path.join(os.path.abspath(REPO_DIR), 'ABC')
        os.makedirs(base_path)
        vt = OSViztrailHandle.create_viztrail(
            identifier='ABC',
            properties=None,
            exec_env_id='ENV1',
            base_path=base_path
        )
        self.assertEquals(len(vt.branches), 0)
        branch = vt.create_branch(properties={PROPERTY_NAME: 'My Branch'})
        self.assertEquals(len(vt.branches), 1)
        vt = OSViztrailHandle.load_viztrail(base_path)
        self.assertEquals(len(vt.branches), 1)
        self.assertTrue(branch.identifier in vt.branches)
        self.assertEquals(vt.get_branch(branch.identifier).name, 'My Branch')
        # Ensure that all branch files exist
        branch_path = os.path.join(base_path, FOLDER_BRANCHES, branch.identifier)
        self.assertTrue(os.path.isdir(branch_path))
        self.assertTrue(os.path.isfile(os.path.join(branch_path, OBJ_METADATA)))
        self.assertTrue(os.path.isfile(os.path.join(branch_path, OBJ_PROPERTIES)))
        self.assertTrue(os.path.isfile(os.path.join(branch_path, OBJ_WORKFLOWS)))
        vt.delete_branch(branch.identifier)
        self.assertFalse(os.path.isdir(branch_path))
        self.assertEquals(len(vt.branches), 0)
        vt = OSViztrailHandle.load_viztrail(base_path)
        self.assertEquals(len(vt.branches), 0)

    def test_create_empty_properties(self):
        """Ensure that create without pre-defined properties works."""
        base_path = os.path.join(os.path.abspath(REPO_DIR), 'ABC')
        os.makedirs(base_path)
        vt = OSViztrailHandle.create_viztrail(
            identifier='ABC',
            properties=None,
            exec_env_id='ENV1',
            base_path=base_path
        )
        self.assertEquals(vt.identifier, 'ABC')
        self.assertEquals(vt.exec_env_id, 'ENV1')
        self.assertIsNone(vt.name)

    def test_create_load_delete(self):
        """Ensure that create and load works properly."""
        base_path = os.path.join(os.path.abspath(REPO_DIR), 'ABC')
        os.makedirs(base_path)
        vt = OSViztrailHandle.create_viztrail(
            identifier='DEF',
            properties={PROPERTY_NAME: 'My Viztrail'},
            exec_env_id='ENV1',
            base_path=base_path
        )
        # Ensure that all files and subfolders are created
        vt_folder = os.path.join(REPO_DIR, 'ABC')
        self.assertTrue(os.path.isdir(vt_folder))
        self.assertTrue(os.path.isdir(os.path.join(vt_folder, FOLDER_BRANCHES)))
        self.assertTrue(os.path.isdir(os.path.join(vt_folder, FOLDER_MODULES)))
        self.assertTrue(os.path.isfile(os.path.join(vt_folder, OBJ_BRANCHINDEX)))
        self.assertTrue(os.path.isfile(os.path.join(vt_folder, OBJ_METADATA)))
        self.assertTrue(os.path.isfile(os.path.join(vt_folder, OBJ_PROPERTIES)))
        # Update name property
        self.assertEquals(vt.identifier, 'DEF')
        self.assertEquals(vt.exec_env_id, 'ENV1')
        self.assertEquals(vt.name, 'My Viztrail')
        vt.name = 'A Name'
        self.assertEquals(vt.name, 'A Name')
        # Load viztrail from disk
        vt = OSViztrailHandle.load_viztrail(base_path)
        self.assertEquals(vt.identifier, 'DEF')
        self.assertEquals(vt.exec_env_id, 'ENV1')
        self.assertEquals(vt.name, 'A Name')
        # Delete viztrail
        vt.delete_viztrail()
        self.assertFalse(os.path.exists(vt_folder))


if __name__ == '__main__':
    unittest.main()