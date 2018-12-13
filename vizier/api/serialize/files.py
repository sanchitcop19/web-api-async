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
serialize file resources.
"""

import vizier.api.serialize.base as serialize


def FILE_HANDLE(f_handle, project, urls):
    """Dictionary serialization for a file handle.

    Parameters
    ----------
    f_handle : vizier.filestore.base.FileHandle
        File handle
    project: vizier.engine.project.ProjectHandle
        Handle for the containing project
    urls: vizier.api.webservice.routes.UrlFactory
        Factory for resource urls

    Returns
    -------
    dict
    """
    project_id = project.identifier
    file_id = f_handle.identifier
    # At the moment the self reference and the download Url are identical
    download_url = urls.file_download(project_id, file_id)
    obj = {
        'id': file_id,
        'name': f_handle.file_name,
        'links': serialize.HATEOAS({
            'self': download_url,
            'file:download': download_url
        })
    }
    # Add mimetype and encoding if not None
    if not f_handle.mimetype is None:
        obj['mimetype'] = f_handle.mimetype
    if not f_handle.encoding is None:
        obj['encoding'] = f_handle.encoding
    return obj
