# Copyright (C) 2018 New York University,
#                    University at Buffalo,
#                    Illinois Institute of Technology.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Implementation for module handles that are maintained as an objects in an
object store.
"""

from vizier.core.io.base import DefaultObjectStore
from vizier.core.timestamp import get_current_time, to_datetime
from vizier.datastore.dataset import DatasetColumn, DatasetDescriptor
from vizier.viztrail.command import ModuleCommand, UNKNOWN_ID
from vizier.viztrail.module import ModuleHandle, ModuleOutputs, ModuleProvenance
from vizier.viztrail.module import ModuleTimestamp, OutputObject, TextOutput
from vizier.viztrail.module import MODULE_CANCELED, MODULE_ERROR, MODULE_PENDING
from vizier.viztrail.module import MODULE_ERROR, MODULE_RUNNING, MODULE_SUCCESS


"""Json labels for serialized object."""
KEY_ARGUMENTS = 'args'
KEY_COLUMN_ID = 'id'
KEY_COLUMN_NAME = 'name'
KEY_COLUMN_TYPE = 'type'
KEY_COMMAND = 'command'
KEY_COMMAND_ID = 'commandId'
KEY_CREATED_AT = 'createdAt'
KEY_DATASETS = 'datasets'
KEY_DATASET_COLUMNS = 'columns'
KEY_DATASET_ID = 'id'
KEY_DATASET_NAME = 'name'
KEY_DATASET_ROWCOUNT = 'rowCount'
KEY_EXTERNAL_FORM = 'externalForm'
KEY_FINISHED_AT = 'finishedAt'
KEY_STARTED_AT = 'startedAt'
KEY_OUTPUTS = 'output'
KEY_OUTPUT_TYPE = 'type'
KEY_OUTPUT_VALUE = 'value'
KEY_PACKAGE_ID = 'packageId'
KEY_PROVENANCE = 'prov'
KEY_PROVENANCE_READ = 'read'
KEY_PROVENANCE_RESOURCES = 'resources'
KEY_PROVENANCE_WRITE = 'write'
KEY_STATE = 'state'
KEY_STDERR = 'stderr'
KEY_STDOUT = 'stdout'
KEY_TIMESTAMP = 'timestamp'


class OSModuleHandle(ModuleHandle):
    """Handle for workflow modules that are maintained as objects in an object
    store.

    Modules are maintained as Json objects with the following structure:

    - identifier: ...
    - externalForm: ...
    - state: ...
    - command:
      - packageId: ...
      - commandId: ...
      - arguments: [
          - key: ...
          - value: ...
        ]
    - timestamps:
      - createdAt
      - startedAt
      - finishedAt
    - datasets: [
        - id: ...
        - name: ...
        - columns: [
          - id: ...
          - name: ...
        ]
      ]
    - outputs
      - stderr: [
          - type: ...
          - value: ...
        ]
      - stdout: [
          - type: ...
          - value: ...
        ]
    - provenance
      - read: [
          - id: ...
          - name: ...
        ]
      - write: [
          - id: ...
          - name: ...
        ]
    """
    def __init__(
        self, identifier, command, external_form, module_path,
        state=None, timestamp=None, datasets=None, outputs=None,
        provenance=None, object_store=None
    ):
        """Initialize the module handle. For new modules, datasets and outputs
        are initially empty.

        Parameters
        ----------
        identifier : string
            Unique module identifier
        command : vizier.viztrail.command.ModuleCommand
            Specification of the module (i.e., package, name, and arguments)
        external_form: string
            Printable representation of module command
        module_path: string
            Path to module resource in object store
        state: int
            Module state (one of PENDING, RUNNING, CANCELED, ERROR, SUCCESS)
        timestamp: vizier.viztrail.module.ModuleTimestamp, optional
            Module timestamp
        datasets : dict(vizier.datastore.dataset.DatasetDescriptor), optional
            Dictionary of resulting datasets. Dataset descriptors are keyed by
            the user-specified dataset name.
        outputs: vizier.viztrail.module.ModuleOutputs, optional
            Module output streams STDOUT and STDERR
        provenance: vizier.viztrail.module.ModuleProvenance, optional
            Provenance information about datasets that were read and writen by
            previous execution of the module.
        object_store: vizier.core.io.base.ObjectStore, optional
            Object store implementation to access and maintain resources
        """
        super(OSModuleHandle, self).__init__(
            identifier=identifier,
            command=command,
            external_form=external_form,
            state=state if not state is None else MODULE_PENDING,
            timestamp=timestamp,
            datasets=datasets,
            outputs= outputs,
            provenance=provenance
        )
        self.module_path = module_path
        self.object_store = object_store if not object_store is None else DefaultObjectStore()

    @staticmethod
    def create_module(
        command, external_form, state, timestamp, datasets, outputs, provenance,
        module_folder, object_store=None
    ):
        """Create a new materialized module instance for the given values.

        Parameters
        ----------
        command : vizier.viztrail.command.ModuleCommand
            Specification of the module (i.e., package, name, and arguments)
        external_form: string
            Printable representation of module command
        state: int
            Module state (one of PENDING, RUNNING, CANCELED, ERROR, SUCCESS)
        timestamp: vizier.viztrail.module.ModuleTimestamp
            Module timestamp
        datasets : dict(vizier.datastore.dataset.DatasetDescriptor)
            Dictionary of resulting datasets. Dataset descriptors are keyed by
            the user-specified dataset name.
        outputs: vizier.viztrail.module.ModuleOutputs
            Module output streams STDOUT and STDERR
        provenance: vizier.viztrail.module.ModuleProvenance
            Provenance information about datasets that were read and writen by
            previous execution of the module.
        module_folder: string
            Object store folder containing module resources
        object_store: vizier.core.io.base.ObjectStore, optional
            Object store implementation to access and maintain resources

        Returns
        -------
        vizier.viztrail.driver.objectstore.module.OSModuleHandle
        """
        # Make sure the object store is not None
        if object_store is None:
            object_store = DefaultObjectStore()
        # Serialize module components and materialize
        obj = serialize_module(
            command=command,
            external_form=external_form,
            state=state,
            timestamp=timestamp,
            datasets=datasets,
            outputs=outputs,
            provenance=provenance
        )
        identifier = object_store.create_object(
            parent_folder=module_folder,
            content=obj
        )
        # Return handle for created module
        return OSModuleHandle(
            identifier=identifier,
            command=command,
            external_form=external_form,
            module_path=object_store.join(module_folder, identifier),
            state=state,
            timestamp=timestamp,
            datasets=datasets,
            outputs=outputs,
            provenance=provenance,
            object_store=object_store
        )

    @staticmethod
    def load_module(identifier, module_path, object_store=None):
        """Load module from given object store.

        Parameters
        ----------
        identifier: string
            Unique module identifier
        module_path: string
            Resource path for module object
        object_store: vizier.core.io.base.ObjectStore, optional
            Object store implementation to access and maintain resources

        Returns
        -------
        vizier.viztrail.driver.objectstore.module.OSModuleHandle
        """
        # Make sure the object store is not None
        if object_store is None:
            object_store = DefaultObjectStore()
        # Read object from store. This may raise a ValueError to indicate that
        # the module does not exists (in a system error condtion). In this
        # case we return a new module that is in error state.
        try:
            obj = object_store.read_object(object_path=module_path)
        except ValueError:
            return OSModuleHandle(
                identifier=identifier,
                command=ModuleCommand(
                    package_id=UNKNOWN_ID,
                    command_id=UNKNOWN_ID
                ),
                external_form='fatal error: object not found',
                module_path=module_path,
                state=MODULE_ERROR,
                object_store=object_store
            )
        # Create module command
        command = ModuleCommand(
            package_id=obj[KEY_COMMAND][KEY_PACKAGE_ID],
            command_id=obj[KEY_COMMAND][KEY_COMMAND_ID],
            arguments=obj[KEY_COMMAND][KEY_ARGUMENTS]
        )
        # Create module timestamps
        created_at = to_datetime(obj[KEY_TIMESTAMP][KEY_CREATED_AT])
        if KEY_STARTED_AT in obj[KEY_TIMESTAMP]:
            started_at = to_datetime(obj[KEY_TIMESTAMP][KEY_STARTED_AT])
        else:
            started_at = None
        if KEY_FINISHED_AT in obj[KEY_TIMESTAMP]:
            finished_at = to_datetime(obj[KEY_TIMESTAMP][KEY_FINISHED_AT])
        else:
            finished_at = None
        timestamp = ModuleTimestamp(
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at
        )
        # Create dataset index. In the resulting dictionary datasets are
        # keyed by their name
        datasets = get_dataset_index(obj[KEY_DATASETS])
        # Create module output streams.
        outputs = ModuleOutputs(
            stdout=get_output_stream(obj[KEY_OUTPUTS][KEY_STDOUT]),
            stderr=get_output_stream(obj[KEY_OUTPUTS][KEY_STDERR])
        )
        # Create module provenance information
        read_prov = None
        if KEY_PROVENANCE_READ in obj[KEY_PROVENANCE]:
            read_prov = get_dataset_index(obj[KEY_PROVENANCE][KEY_PROVENANCE_READ])
        write_prov = None
        if KEY_PROVENANCE_WRITE in obj[KEY_PROVENANCE]:
            write_prov = get_dataset_index(obj[KEY_PROVENANCE][KEY_PROVENANCE_WRITE])
        res_prov = None
        if KEY_PROVENANCE_RESOURCES in obj[KEY_PROVENANCE]:
            res_prov = obj[KEY_PROVENANCE][KEY_PROVENANCE_RESOURCES]
        provenance = ModuleProvenance(
            read=read_prov,
            write=write_prov,
            resources=res_prov
        )
        # Return module handle
        return OSModuleHandle(
            identifier=identifier,
            command=command,
            external_form=obj[KEY_EXTERNAL_FORM],
            module_path=module_path,
            state=obj[KEY_STATE],
            timestamp=timestamp,
            datasets=datasets,
            outputs=outputs,
            provenance=provenance,
            object_store=object_store
        )

    def set_canceled(self, finished_at=None, outputs=None):
        """Set status of the module to canceled. The finished_at property of the
        timestamp is set to the given value or the current time (if None). The
        module outputs are set to the given value. If no outputs are given the
        module output streams will be empty.

        Parameters
        ----------
        finished_at: datetime.datetime, optional
            Timestamp when module started running
        outputs: vizier.viztrail.module.ModuleOutputs, optional
            Output streams for module
        """
        # Update state, timestamp and output information. Clear database state.
        self.state = MODULE_CANCELED
        self.timestamp.finished_at = finished_at if not finished_at is None else get_current_time()
        self.outputs = outputs if not outputs is None else ModuleOutputs()
        self.datasets = dict()
        # Materialize module state
        self.write_safe()

    def set_error(self, finished_at=None, outputs=None):
        """Set status of the module to error. The finished_at property of the
        timestamp is set to the given value or the current time (if None). The
        module outputs are adjusted to the given value. the output streams are
        empty if no value is given for the outputs parameter.

        Parameters
        ----------
        finished_at: datetime.datetime, optional
            Timestamp when module started running
        outputs: vizier.viztrail.module.ModuleOutputs, optional
            Output streams for module
        """
        # Update state, timestamp and output information. Clear database state.
        self.state = MODULE_ERROR
        self.timestamp.finished_at = finished_at if not finished_at is None else get_current_time()
        self.outputs = outputs if not outputs is None else ModuleOutputs()
        self.datasets = dict()
        # Materialize module state
        self.write_safe()

    def set_running(self, external_form, started_at=None):
        """Set status of the module to running. The started_at property of the
        timestamp is set to the given value or the current time (if None).

        Parameters
        ----------
        external_form: string
            Adjusted external representation for the module command.
        started_at: datetime.datetime, optional
            Timestamp when module started running
        """
        # Update state and timestamp information. Clear outputs and, database
        # state,
        self.external_form = external_form
        self.state = MODULE_RUNNING
        self.timestamp.started_at = started_at if not started_at is None else get_current_time()
        self.outputs = ModuleOutputs()
        self.datasets = dict()
        # Materialize module state
        self.write_safe()

    def set_success(self, finished_at=None, datasets=None, outputs=None, provenance=None):
        """Set status of the module to success. The finished_at property of the
        timestamp is set to the given value or the current time (if None).

        If case of a successful module execution the database state and module
        provenance information are also adjusted together with the module
        output streams.

        Parameters
        ----------
        finished_at: datetime.datetime, optional
            Timestamp when module started running
        datasets : dict(vizier.datastore.dataset.DatasetDescriptor), optional
            Dictionary of resulting datasets. The user-specified name is the key
            for the dataset descriptor.
        outputs: vizier.viztrail.module.ModuleOutputs, optional
            Output streams for module
        provenance: vizier.viztrail.module.ModuleProvenance, optional
            Provenance information about datasets that were read and writen by
            previous execution of the module.
        """
        # Update state, timestamp, database state, outputs and provenance
        # information.
        self.state = MODULE_SUCCESS
        self.timestamp.finished_at = finished_at if not finished_at is None else get_current_time()
        # If the module is set to success straight from pending state the
        # started_at timestamp may not have been set.
        if self.timestamp.started_at is None:
            self.timestamp.started_at = self.timestamp.finished_at
        self.outputs = outputs if not outputs is None else ModuleOutputs()
        self.datasets = datasets if not datasets is None else dict()
        self.provenance = provenance if not provenance is None else ModuleProvenance()
        # Materialize module state
        self.write_safe()

    def write_module(self):
        """Write current module state to object store."""
        obj = serialize_module(
            command=self.command,
            external_form=self.external_form,
            state=self.state,
            timestamp=self.timestamp,
            datasets=self.datasets,
            outputs=self.outputs,
            provenance=self.provenance
        )
        self.object_store.write_object(
            object_path=self.module_path,
            content=obj
        )

    def write_safe(self):
        """The write safe method writes the current module state to the object
        store. It catches any occuring exception and sets the module into error
        state if an exception occurs. This method is used to ensure that the
        state of the module is in error (i.e., the workflow cannot further be
        executed) if a state change fails.
        """
        try:
            self.write_module()
        except Exception as ex:
            self.state = MODULE_ERROR
            self.outputs = ModuleOutputs(stderr=[TextOutput(str(ex))])
            self.datasets = dict()


# ------------------------------------------------------------------------------
# Helper Methods
# ------------------------------------------------------------------------------

def get_dataset_index(datasets):
    """Convert a list of dataset references in default serialization format into
    a dictionary. The elements of the dictionary are either dataset descriptors
    or strings representing the dataset identifier. The user-provided dataset
    name is the key for the dictionary.

    Parameters
    ----------
    datasets: list(dict)
        List of datasets in default serialization format

    Returns
    -------
    dict
    """
    result = dict()
    for ds in datasets:
        identifier = ds[KEY_DATASET_ID]
        name = ds[KEY_DATASET_NAME]
        if KEY_DATASET_COLUMNS in ds or KEY_DATASET_ROWCOUNT in ds:
            descriptor = DatasetDescriptor(
                identifier=identifier,
                columns=[
                    DatasetColumn(
                        identifier=col[KEY_COLUMN_ID],
                        name=col[KEY_COLUMN_NAME],
                        data_type=col[KEY_COLUMN_TYPE]
                    ) for col in ds[KEY_DATASET_COLUMNS]
                ],
                row_count=ds[KEY_DATASET_ROWCOUNT]
            )
            result[name] = descriptor
        else:
            result[name] = identifier
    return result


def get_module_path(modules_folder, module_id, object_store):
    """Use a single method to get the module path. This should make it easier to
    change the directory structure for maintaining modules.

    Parameters
    ----------
    modules_folder: string
        path to base folder for module objects
    module_id: string
        Unique module identifier
        object_store: vizier.core.io.base.ObjectStore
            Object store implementation to access and maintain resources


    Returns
    -------
    string
    """
    # At the moment we maintain all module objects as files in a single folder
    return object_store.join(modules_folder, module_id)


def get_output_stream(items):
    """Convert a list of items in an output stream into a list of output
    objects. The element in list items are expected to be in default
    serialization format for output objects.

    Paramaters
    ----------
    items: list(dict)
        Items in the output stream in default serialization format

    Returns
    -------
    list(vizier.viztrail.module.OutputObject)
    """
    result = list()
    for item in items:
        result.append(
            OutputObject(
                type=item[KEY_OUTPUT_TYPE],
                value=item[KEY_OUTPUT_VALUE]
            )
        )
    return result


def serialize_module(command, external_form, state, timestamp, datasets, outputs, provenance):
    """Get dictionary serialization of a module.

    Parameters
    ----------
    command : vizier.viztrail.command.ModuleCommand
        Specification of the module (i.e., package, name, and arguments)
    external_form: string
        Printable representation of module command
    state: int
        Module state (one of PENDING, RUNNING, CANCELED, ERROR, SUCCESS)
    timestamp: vizier.viztrail.module.ModuleTimestamp
        Module timestamp
    datasets : dict(vizier.datastore.dataset.DatasetDescriptor)
        Dictionary of resulting dataset descriptors.
    outputs: vizier.viztrail.module.ModuleOutputs
        Module output streams STDOUT and STDERR
    provenance: vizier.viztrail.module.ModuleProvenance
        Provenance information about datasets that were read and writen by
        previous execution of the module.

    Returns
    -------
    dict
    """
    # Create dictionary serialization for module timestamps
    ts = {KEY_CREATED_AT: timestamp.created_at.isoformat()}
    if not timestamp.started_at is None:
        ts[KEY_STARTED_AT] = timestamp.started_at.isoformat()
    if not timestamp.finished_at is None:
        ts[KEY_FINISHED_AT] = timestamp.finished_at.isoformat()
    # Create dictionary serialization for module provenance
    prov = dict()
    if not provenance.read is None:
        prov[KEY_PROVENANCE_READ] = [{
                KEY_DATASET_NAME: name,
                KEY_DATASET_ID: provenance.read[name]
            } for name in provenance.read
        ]
    if not provenance.write is None:
        prov[KEY_PROVENANCE_WRITE] = [{
                KEY_DATASET_NAME: name,
                KEY_DATASET_ID: provenance.write[name]
            } for name in provenance.write
        ]
    if not provenance.resources is None:
        prov[KEY_PROVENANCE_RESOURCES] = provenance.resources
    # Create dictionary serialization for the module handle
    return {
        KEY_EXTERNAL_FORM: external_form,
        KEY_COMMAND: {
            KEY_PACKAGE_ID: command.package_id,
            KEY_COMMAND_ID: command.command_id,
            KEY_ARGUMENTS: command.arguments.to_list()
        },
        KEY_STATE: state,
        KEY_OUTPUTS: {
            KEY_STDERR: [{
                    KEY_OUTPUT_TYPE: obj.type,
                    KEY_OUTPUT_VALUE: obj.value
                } for obj in outputs.stderr],
            KEY_STDOUT: [{
                    KEY_OUTPUT_TYPE: obj.type,
                    KEY_OUTPUT_VALUE: obj.value
                } for obj in outputs.stdout]
        },
        KEY_TIMESTAMP: ts,
        KEY_DATASETS: [{
                KEY_DATASET_NAME: ds,
                KEY_DATASET_ID: datasets[ds].identifier,
                KEY_DATASET_COLUMNS: [{
                    KEY_COLUMN_ID: col.identifier,
                    KEY_COLUMN_NAME: col.name,
                    KEY_COLUMN_TYPE: col.data_type
                } for col in datasets[ds].columns],
                KEY_DATASET_ROWCOUNT: datasets[ds].row_count
            } for ds in datasets],
        KEY_PROVENANCE: prov
    }