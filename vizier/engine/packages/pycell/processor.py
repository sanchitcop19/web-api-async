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

"""Implementation of the task processor for the Python cell package."""

import sys

from vizier.engine.task.processor import ExecResult, TaskProcessor
from vizier.engine.packages.pycell.client.base import VizierDBClient
from vizier.engine.packages.pycell.stream import OutputStream
from vizier.viztrail.module import ModuleOutputs, ModuleProvenance, TextOutput

import vizier.engine.packages.base as pckg
import vizier.engine.packages.pycell.base as cmd

"""Context variable name for Vizier DB Client."""
VARS_DBCLIENT = 'vizierdb'


class PyCellTaskProcessor(TaskProcessor):
    """Implementation of the task processor for the Python cell package."""
    def compute(self, command_id, arguments, context):
        """Execute the Python script that is contained in the given arguments.

        Parameters
        ----------
        command_id: string
            Unique identifier for a command in a package declaration
        arguments: vizier.viztrail.command.ModuleArguments
            User-provided command arguments
        context: vizier.engine.task.base.TaskContext
            Context in which a task is being executed

        Returns
        -------
        vizier.engine.task.processor.ExecResult
        """
        if command_id == cmd.PYTHON_CODE:
            return self.execute_script(
                args=arguments,
                context=context
            )
        else:
            raise ValueError('unknown pycell command \'' + str(command_id) + '\'')

    def execute_script(self, args, context):
        """Execute a Python script in the given context.

        Parameters
        ----------
        args: vizier.viztrail.command.ModuleArguments
            User-provided command arguments
        context: vizier.engine.task.base.TaskContext
            Context in which a task is being executed

        Returns
        -------
        vizier.engine.task.processor.ExecResult
        """
        # Get Python script from user arguments
        source = args.get_value(cmd.PYTHON_SOURCE)
        # Initialize the scope variables that are available to the executed
        # Python script. At this point this includes only the client to access
        # and manipulate datasets in the undelying datastore
        client = VizierDBClient(
            datastore=context.datastore,
            datasets=context.datasets
        )
        variables = {VARS_DBCLIENT: client}
        # Redirect standard output and standard error streams
        out = sys.stdout
        err = sys.stderr
        stream = list()
        sys.stdout = OutputStream(tag='out', stream=stream)
        sys.stderr = OutputStream(tag='err', stream=stream)
        # Run the Pyhton code
        try:
            exec source in variables, variables
        except Exception as ex:
            template = "{0}:{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            sys.stderr.write(str(message) + '\n')
        finally:
            # Make sure to reverse redirection of output streams
            sys.stdout = out
            sys.stderr = err
        # Set module outputs
        outputs = ModuleOutputs()
        is_success = True
        for tag, text in stream:
            text = ''.join(text).strip()
            if tag == 'out':
                outputs.stdout.append(TextOutput(text))
            else:
                outputs.stderr.append(TextOutput(text))
                is_success = False
        if is_success:
            datasets = dict(client.datasets)
            read = dict()
            for name in client.read:
                read[name] = context.datasets[name] if name in context.datasets else ''
            write = dict()
            for name in client.write:
                write[name] = client.datasets[name] if name in client.datasets else ''
            # Ensure that all three variables are valid dictionaries and the
            # user did not attempt anything tricky
            for mapping in [datasets, read, write]:
                for key in mapping:
                    if not isinstance(key, basestring) or not isinstance(mapping[key], basestring):
                        raise RuntimeError('not a valid mapping dictionary')
            provenance = ModuleProvenance(read=read, write=write)
        else:
            datasets = context.datasets
            provenance = ModuleProvenance()
        # Return execution result
        return ExecResult(
            is_success=is_success,
            datasets=datasets,
            outputs=outputs,
            provenance=provenance
        )