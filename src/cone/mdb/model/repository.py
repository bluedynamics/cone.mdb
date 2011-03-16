import os
from pyramid.security import authenticated_userid
from cone.app.model import (
    Properties,
    XMLProperties,
    AdapterNode,
    BaseNodeInfo,
    registerNodeInfo,
)
from node.ext.mdb import Repository
from cone.mdb.model.media import MediaAdapter
from cone.mdb.model.utils import DBLocation
from cone.mdb.browser.utils import timestamp


def add_repository(request, repositories, id, title, description):
    """Create and add repository.
    
    ``request``
        webob request
    ``repositories``
        cone.mdb.model.Repositories
    ``id``
        new repository id
    ``title``
        repository title
    ``description``
        repository description
    """
    model = Repository(os.path.join(repositories.dbpath, id))
    repository = RepositoryAdapter(model, None, None)
    metadata = repository.metadata
    metadata.title = title
    metadata.description = description
    metadata.creator = authenticated_userid(request)
    metadata.created = timestamp()
    repository()


def update_repository(request, repository, title, description):
    """Update existing repository.
    
    ``repository``
        cone.mdb.model.RepositoryAdapter
    ``title``
        new title
    ``description``
        new description
    """
    metadata = repository.metadata
    metadata.title = title
    metadata.description = description
    metadata.modified = timestamp()
    metadata.modified_by = authenticated_userid(request)
    repository()


class RepositoryAdapter(AdapterNode, DBLocation):
    
    node_info_name = 'repository'
    
    @property
    def properties(self):
        if not hasattr(self, '_properties'):
            props = Properties()
            props.in_navtree = True
            props.editable = True
            props.action_up = True
            self._properties = props
        return self._properties
    
    @property
    def metadata(self):
        if hasattr(self, '_metadata'):
            return self._metadata
        if self.model.__name__ is not None:
            path = os.path.join(self.model.__name__, 'database.info')
            self._metadata = XMLProperties(path)
            return self._metadata
        return Properties()                                 #pragma NO COVERAGE
    
    def __getitem__(self, name):
        try:
            return AdapterNode.__getitem__(self, name)
        except KeyError:
            if not name in self.iterkeys():
                raise KeyError(name)
            media = MediaAdapter(self.model[name], name, self)
            self[name] = media
            return media
    
    def __call__(self):
        self.model()
        self.metadata()


info = BaseNodeInfo()
info.title = 'Repository'
info.description = 'A repository.'
info.node = RepositoryAdapter
info.addables = ['media']
registerNodeInfo('repository', info)