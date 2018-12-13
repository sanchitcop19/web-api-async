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

"""This module contains helper methods for the webservice that are used to
serialize branches.
"""

import vizier.api.serialize.base as serialize


def BRANCH_DESCRIPTOR(project, branch, urls):
    """Dictionary serialization for branch descriptor.

    Parameters
    ----------
    project: vizier.engine.project.ProjectHandle
        Handle for the containing project
    branch : vizier.viztrail.branch.BranchHandle
        Branch handle
    urls: vizier.api.webservice.routes.UrlFactory
        Factory for resource urls

    Returns
    -------
    dict
    """
    project_id = project.identifier
    branch_id = branch.identifier
    return {
        'id': branch_id,
        'isDefault': project.viztrail.is_default_branch(branch_id),
        'properties': serialize.ANNOTATIONS(branch.properties),
        'links': serialize.HATEOAS({
            'self': urls.get_branch(project_id, branch_id),
            'branch:delete': urls.delete_branch(project_id, branch_id),
            'branch:head': urls.get_branch_head(project_id, branch_id),
            'branch:project': urls.get_project(project_id),
            'branch:update': urls.update_branch(project_id, branch_id)
        })
    }
