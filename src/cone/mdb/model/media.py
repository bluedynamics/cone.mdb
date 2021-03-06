import os
import uuid
from plumber import plumber
from node.locking import locktree
from node.utils import instance_property
from node.ext.mdb import (
    Media,
    MediaKeys,
)
from pyramid.security import authenticated_userid
from cone.app.model import (
    Properties,
    ProtectedProperties,
    XMLProperties,
    AdapterNode,
    NodeInfo,
    registerNodeInfo,
)
from cone.app.security import DEFAULT_NODE_PROPERTY_PERMISSIONS
from cone.app.browser.utils import nodepath
from cone.mdb.model.revision import RevisionAdapter
from cone.mdb.model.utils import (
    GroupToRepositoryACL,
    solr_config,
    timestamp,
)
from cone.mdb.solr import (
    index_doc,
    unindex_doc,
)


def index_media(media):
    body = ' '.join([
        media.metadata.get('title', ''),
        media.metadata.get('description', ''), 
        media.metadata.get('author', ''),
    ])
    index_doc(solr_config(media),
              media,
              path='/'.join(nodepath(media)),
              repository=media.__parent__.metadata.title,
              type='Media',
              body=body)


def add_media(request, repository, title, description):
    """Create and add media.
    
    ``request``
        webob request
    ``repository``
        cone.mdb.model.RepositoryAdapter
    ``title``
        repository title
    ``description``
        repository description
    """
    keys = MediaKeys(repository.model.__name__)
    key = keys.next()
    keys.dump(key)
    repository.model[key] = Media()
    media = repository[key]
    media.metadata.uid = str(uuid.uuid4())
    media.metadata.title = title
    media.metadata.description = description
    media.metadata.creator = authenticated_userid(request)
    media.metadata.created = timestamp()
    media()
    index_media(media)
    return media


def update_media(request, media, title, description):
    """Update existing media.
    
    ``media``
        cone.mdb.model.MediaAdapter
    ``title``
        new title
    ``description``
        new description
    """
    metadata = media.metadata
    metadata.title = title
    metadata.description = description
    metadata.modified = timestamp()
    metadata.modified_by = authenticated_userid(request)
    media()
    index_media(media)


class MediaAdapter(AdapterNode):
    __metaclass__ = plumber
    __plumbing__ = GroupToRepositoryACL
    
    node_info_name = 'media'
    
    @instance_property
    def properties(self):
        props = ProtectedProperties(self, DEFAULT_NODE_PROPERTY_PERMISSIONS)
        props.in_navtree = True
        props.action_edit = True
        props.action_delete = True
        props.action_add_reference = True
        props.action_up = True
        props.action_view = True
        props.action_list = True
        return props
    
    @instance_property
    def metadata(self):
        if self.model.__name__ is not None:
            path = os.path.join(self.model.root.__name__,
                                *self.model.mediapath + ['media.info'])
            return XMLProperties(path)
        return Properties()                                 #pragma NO COVERAGE
    
    @property
    def active_revision(self):
        for key in self.keys():
            if self[key].metadata.state == 'active':
                return self[key]
    
    def __getitem__(self, key):
        try:
            return AdapterNode.__getitem__(self, key)
        except KeyError:
            if not key in self.iterkeys():
                raise KeyError(key)
            revision = RevisionAdapter(self.model[key], key, self)
            self[key] = revision
            return revision
    
    @locktree
    def __delitem__(self, key):
        todelete = self[key]
        if hasattr(self, '_todelete'):
            self._todelete.append(todelete)
        else:
            self._todelete = [todelete]
        AdapterNode.__delitem__(self, key)
    
    @locktree
    def __call__(self):
        if hasattr(self, '_todelete'):
            config = solr_config(self)
            for revision in self._todelete:
                unindex_doc(config, revision)
                del self.model[revision.__name__]
            del self._todelete
        self.model()
        self.metadata()


info = NodeInfo()
info.title = 'Media'
info.description = 'A media object.'
info.node = MediaAdapter
info.addables = ['revision']
info.icon = 'mdb-static/images/media16_16.png'
registerNodeInfo('media', info)