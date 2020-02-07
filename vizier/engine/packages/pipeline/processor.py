# Copyright (C) 2017-2019 New York University,
#                         University at Buffalo,
#                         Illinois Institute of Technology.
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

"""
Implementation of the task processor that executes commands that
are defined in the `pipeline` package.
"""

import math
import sys
from vizier.engine.task.processor import ExecResult, TaskProcessor
from vizier.api.webservice import server
from vizier.viztrail.module.output import ModuleOutputs, DatasetOutput, TextOutput
from vizier.viztrail.module.provenance import ModuleProvenance
from vizier.datastore.dataset import DatasetDescriptor, DatasetColumn, DatasetRow
import vizier.engine.packages.pipeline.base as cmd
import vizier.mimir as mimir
from sklearn.linear_model import SGDClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder
import pandas as pd
import numpy as np

# Rename
LinearClassifier = SGDClassifier


class PipelineProcessor(TaskProcessor):
    """
    Implmentation of the task processor for the pipeline package. The 
    processor uses an instance of the vizual API to allow running on 
    different types of datastores (e.g., the default datastore or the 
    Mimir datastore).
    """
    def __init__(self):
        """
        Initialize the vizual API instance
        """

    def save_context(self, context, notebook_context, keys, values):
        """
        Save a list of keys and corresponding values in a database for carrying context across cells.
        TODO: Lists and strings as values seem to throw vizier off, using keys to represent both keys 
        and values for now. This should be fixed as soon as lists and strings are supported, the current
        handling is just ugly haha. 
        """

        def save_pair(rows, key: str, value: int):
            """
            Save a specific key-value pair
            """

            is_key_present = False
            for i, row in enumerate(rows):
                if row.values[0] == key:
                    is_key_present = True
                    row[i] = DatasetRow(
                        identifier = notebook_context.max_row_id()+1,
                        values = [key, value]
                    )
                    break
            if not is_key_present:
                rows.append(
                    DatasetRow(
                        identifier = notebook_context.max_row_id()+1,
                        values = [key, value]
                    )
                )

        rows = notebook_context.fetch_rows()

        seen = set()
        for key, value in zip(keys, values):
            if key not in seen:
                save_pair(rows, key, value)
            seen.add(key)
        
        ds = context.datastore.create_dataset(
            columns = notebook_context.columns,
            rows = rows,
            annotations = notebook_context.annotations
        )
        return ds


    def compute(self, command_id, arguments, context):

        outputs = ModuleOutputs()
        provenance = ModuleProvenance()
        output_ds_name = ""
        notebook_context = context.get_dataset(cmd.CONTEXT_DATABASE_NAME)

        if command_id == cmd.SELECT_TRAINING or command_id == cmd.SELECT_TESTING:

            input_ds_name = arguments.get_value(cmd.PARA_INPUT_DATASET).lower()
            input_dataset = context.get_dataset(input_ds_name)
            sample_mode = None

            if input_dataset is None:
                raise ValueError('unknown dataset \'' + input_ds_name + '\'')

            def get_sample_mode(mode, sampling_rate):
                if sampling_rate > 1.0 or sampling_rate < 0.0:
                    raise Exception("Sampling rate must be between 0.0 and 1.0")
                return {
                    "mode" : mode,
                    "probability" : sampling_rate
                }

            if command_id == cmd.SELECT_TRAINING:
                output_ds_name = (input_ds_name + cmd.TRAINING_SUFFIX).lower()

            elif command_id == cmd.SELECT_TESTING:
                output_ds_name = (input_ds_name + cmd.TESTING_SUFFIX).lower()

            sample_mode = get_sample_mode(cmd.SAMPLING_MODE_UNIFORM_PROBABILITY, float(arguments.get_value(cmd.PARA_SAMPLING_RATE)))

            sample_view_id = mimir.createSample(
                input_dataset.table_name,
                sample_mode
            )

            row_count = mimir.countRows(sample_view_id)
            
            ## Register the view with Vizier
            ds = context.datastore.register_dataset(
                table_name=sample_view_id,
                columns=input_dataset.columns,
                row_counter=row_count
            )

            ds_output = server.api.datasets.get_dataset(
                project_id=context.project_id,
                dataset_id=ds.identifier,
                offset=0,
                limit=10
            )

            ds_output['name'] = output_ds_name
            outputs.stdout.append(DatasetOutput(ds_output))

            ## Record Reads and writes
            provenance = ModuleProvenance(
                read={
                    input_ds_name: input_dataset.identifier
                },
                write={
                    output_ds_name: DatasetDescriptor(
                        identifier=ds.identifier,
                        columns=ds.columns,
                        row_count=ds.row_count
                    )
                }
            )
        elif command_id == cmd.SELECT_MODEL:

            classifier = arguments.get_value(cmd.PARA_MODEL)

            outputs.stdout.append(TextOutput("{} selected for classification.".format(classifier)))

            ds = self.save_context(context, notebook_context, ["model_" + classifier], [0])

            provenance = ModuleProvenance(
                write = {
                    cmd.CONTEXT_DATABASE_NAME: DatasetDescriptor(
                        identifier=ds.identifier,
                        columns=ds.columns,
                        row_count=ds.row_count
                        )
                    }
            )
        elif command_id == cmd.SELECT_PREDICTION_COLUMNS:

            input_ds_name = arguments.get_value(cmd.PARA_INPUT_DATASET).lower()
            input_dataset = context.get_dataset(input_ds_name)

            columns = arguments.get_value(cmd.PARA_COLUMNS)
            outputs.stdout.append(TextOutput("Input columns selected for prediction. "))
            
            ds = self.save_context(context, notebook_context, ["column_" + str(column.arguments['columns_column']) for column in columns], [0 for column in columns])
            
            provenance = ModuleProvenance(
                read = {
                    input_ds_name: input_dataset.identifier
                },
                write={
                    cmd.CONTEXT_DATABASE_NAME: DatasetDescriptor(
                        identifier=ds.identifier,
                        columns=ds.columns,
                        row_count=ds.row_count
                        )
                    }
            )
        
        elif command_id == cmd.SELECT_LABEL_COLUMN:

            input_ds_name = arguments.get_value(cmd.PARA_INPUT_DATASET).lower()
            input_dataset = context.get_dataset(input_ds_name)
            label_column = arguments.get_value(cmd.PARA_LABEL_COLUMN)

            outputs.stdout.append(TextOutput("Column {} selected as the label column. ".format(label_column)))

            ds = self.save_context(context, notebook_context, ["label"], [label_column])

            provenance = ModuleProvenance(
                read = {
                    input_ds_name: input_dataset.identifier
                },
                write={
                    cmd.CONTEXT_DATABASE_NAME: DatasetDescriptor(
                        identifier=ds.identifier,
                        columns=ds.columns,
                        row_count=ds.row_count
                        )
                    }
            )

        elif command_id == cmd.SELECT_ACCURACY_METRIC:

            input_ds_name = arguments.get_value(cmd.PARA_INPUT_DATASET).lower()
            input_dataset = context.get_dataset(input_ds_name)

            training_sample = context.get_dataset(input_ds_name + cmd.TRAINING_SUFFIX)
            testing_sample = context.get_dataset(input_ds_name + cmd.TESTING_SUFFIX)

            def parse_context(saved_context):
                model, input_columns, output_column = '', [], ''
                for k, v in saved_context:
                    if not k:
                        continue
                    elif "model_" in k:
                        model = k.split("model_")[1]
                    elif "column_" in k:
                        colnum = k.split("column_")[1]
                        input_columns.append(int(colnum))
                    elif "label" in k:
                        output_column = v
                return model, input_columns, output_column

            saved_context = [row.values for row in notebook_context.fetch_rows()]
            model, input_columns, output_column = parse_context(saved_context)

            input_columns = [input_dataset.column_by_id(column).name.lower() for column in input_columns]
            output_column = input_dataset.column_by_id(output_column).name.lower()

            if model == "Linear Classifier":
                model = LinearClassifier()
            elif model == "Random Forest Classifier":
                model = RandomForestClassifier()
            elif model == "Neural Network":
                model = MLPClassifier()
            elif model == "Decision Tree Classifier":
                model = DecisionTreeClassifier()
            else:
                # This should never be reached since it isn't possible to select anything
                # else through the widget
                pass

            training_values = []
            testing_values = []

            for row in training_sample.fetch_rows():
                values = [value for index, value in enumerate(row.values)]
                training_values.append(values)

            for row in testing_sample.fetch_rows():
                values = [value for index, value in enumerate(row.values)]
                testing_values.append(row.values)

            def process(df, columns, label_column):
                
                le = LabelEncoder()
                
                df = df[df['is_recid'] != -1]
                df = df[df['decile_score_1'] != -1]
                df = df[df['decile_score_2'] != -1]
                df['recidivism_within_2_years'] = df['is_recid']
                
                # Categorize variables
                
                le.fit(df['race'])
                df['race'] = le.transform(df['race'])
                
                le.fit(df['age_cat'])
                df['age_cat'] = le.transform(df['age_cat'])
                
                le.fit(df['v_score_text'])
                df['v_score_text'] = le.transform(df['v_score_text'])
                
                df['score_text'] = np.where(df['score_text'] == 'Low', 0, 1)
                
                df["sex"] = np.where(df["sex"] == "Male", 0, 1)
                
                labels = df[label_column].to_numpy()
                
                # Remove all columns except the ones selected
                df = df[columns]
                
                df = df.to_numpy()
                
                return df, labels

            df_training = pd.DataFrame(np.array(training_values), columns = [col.name.lower() for col in training_sample.columns])
            df_training, training_labels = process(df_training, input_columns, output_column)

            df_testing = pd.DataFrame(np.array(testing_values), columns = [col.name.lower() for col in testing_sample.columns])
            df_testing, testing_labels = process(df_testing, input_columns, output_column)

            try:
                
                # Train the model using the label column selected on the training dataset without the label column
                model.fit(df_training, training_labels)
                
                # Predict labels using the testing dataset without the label column
                predictions = model.predict(df_testing)
                
                # Use the number of mismatched labels as a measure of the accuracy for the classification task
                score = accuracy_score(testing_labels, predictions)
                
                outputs.stdout.append(TextOutput("Accuracy score: {}%".format(str(round(score*100, 2)))))
                
            except ValueError as e:
                outputs.stdout.append(TextOutput("ERROR: Please choose numerical or categorical columns only"))

        else:
            raise Exception("Unknown pipeline command: {}".format(command_id))

        return ExecResult(
            outputs=outputs,
            provenance=provenance
        )