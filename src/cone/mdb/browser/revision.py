import uuid
from webob import Response
from plumber import plumber
from zope.component import queryUtility
from pyramid.interfaces import IResponseFactory
from pyramid.view import view_config
from yafowil.base import (
    factory,
    ExtractionError,
)
from cone.tile import (
    tile,
    render_tile,
    registerTile,
    Tile,
)
from pyramid.security import authenticated_userid
from cone.app.browser.utils import (
    make_url,
    nodepath,
    format_date,
)
from cone.app.browser.layout import ProtectedContentTile
from cone.app.browser.form import Form
from cone.app.browser.authoring import (
    AddPart,
    EditPart,
)
from node.ext.mdb import (
    Revision,
    Metadata,
    Binary,
)
from cone.mdb.model import (
    RevisionAdapter,
    add_revision,
    update_revision,
)
from cone.mdb.model import solr_config
from cone.mdb.solr import Metadata as SolrMetadata


@tile('revisiondetails', 'templates/revisiondetails.pt',
      interface=RevisionAdapter, permission='view')
class RevisionDetails(Tile):
    
    @property
    def relations(self):
        """XXX: move relations lookup
        """
        relations = self.model.metadata.relations
        ret = list()
        if not relations:
            return ret
        query = ''
        for rel in relations:
            query = '%suid:%s OR ' % (query, rel)
        query = query.strip(' OR ')
        md = SolrMetadata(solr_config(self.model))
        for relmd in md.query(q=query):
            ret.append({
                'target': '%s/%s' % (self.request.application_url, relmd.path),
                'title': relmd.title,
            })
        return ret


@view_config('download', for_=RevisionAdapter, permission='view')
def download(model, request):
    response_factory = queryUtility(IResponseFactory, default=Response)
    response = response_factory(model.model['binary'].payload)
    response.content_type = model.metadata.metatype
    response.content_disposition = 'attachment'
    return response


class RevisionForm(object):
    
    form_name = 'revisionform'
    
    def prepare(self):
        metadata = self.model.metadata
        resource = self.action_resource
        action = make_url(self.request, node=self.model, resource=resource)
        form = factory(
            u'form',
            name = self.formname,
            props = {
                'action': action,
            })
        form['visibility'] = factory(
            'field:label:error:select',
            value = metadata.visibility,
            props = {
                'label': 'Visibility',
                'vocabulary': self.visibility_vocab,
            })
        form['flag'] = factory(
            'field:label:error:select',
            value = metadata.flag,
            props = {
                'label': 'Flag',
                'vocabulary': self.flag_vocab,
            })
        form['title'] = factory(
            'field:label:error:text',
            value = metadata.title,
            props = {
                'required': 'No revision title given',
                'label': 'Revision title',
            })
        form['author'] = factory(
            'field:label:text',
            value = metadata.author,
            props = {
                'label': 'Document author',
            })
        form['description'] = factory(
            'field:label:error:textarea',
            value = metadata.description,
            props = {
                'label': 'Revision description',
                'rows': 5,
            })
        form['keywords'] = factory(
            'field:label:textarea:*keywords',
            value = self.keywords_value,
            props = {
                'label': 'Keywords',
                'rows': 5,
            },
            custom = {
                'keywords': ([self.keywords_extractor], [], [], []),
            })
        form['relations'] = factory(
            'field:label:reference:*relations',
            value = self.relations_value,
            props = {
                'label': 'Relations',
                'multivalued': True,
                'vocabulary': self.relations_vocab,
            },
            custom = {
                'relations': ([self.relations_extractor], [], [], []),
            })
        form['effective'] = factory(
            'field:label:error:datetime',
            value = metadata.effective,
            props = {
                'label': 'Effective date',
                'datepicker': True,
                'time': True,
                'locale': 'de',
            })
        form['expires'] = factory(
            'field:label:error:datetime',
            value = metadata.expires,
            props = {
                'label': 'Expiration date',
                'datepicker': True,
                'time': True,
                'locale': 'de',
            })
        form['alttag'] = factory(
            'field:label:text',
            value = metadata.alttag,
            props = {
                'label': 'Alt Tag for publishing',
            })
        form['data'] = factory(
            'field:label:error:file',
            value = self.data_value,
            props = {
                'label': 'Data',
                'required': 'No file uploaded',
            })
        form['save'] = factory(
            'submit',
            props = {
                'action': 'save',
                'expression': True,
                'handler': self.save,
                'next': self.next,
                'label': 'Save',
            })
        form['cancel'] = factory(
            'submit',
            props = {
                'action': 'cancel',
                'expression': True,
                'handler': None,
                'next': self.next,
                'label': 'Cancel',
                'skip': True,
            })
        self.form = form
    
    @property
    def visibility_vocab(self):
        """XXX: available transitions
        """
        if self.adding or self.model.metadata.flag == 'draft':
            return [('hidden', 'hidden')]
        return [
            ('hidden', 'Hidden'),
            ('anonymous', 'Anonymous'),
        ]
        
    @property
    def flag_vocab(self):
        """XXX: available transitions
        """
        if self.adding:
            return [('draft', 'Draft')]
        if self.model.metadata.flag == 'draft':
            return [
                ('draft', 'Draft'),
                ('active', 'Active'),
            ]
        if self.model.metadata.flag == 'active':
            return [
                ('active', 'Active'),
            ]
        if self.model.metadata.flag == 'frozen':
            return [('frozen', 'Frozen')]
    
    @property
    def relations_vocab(self):
        """XXX: move relations lookup
        """
        vocab = list()
        relations = self.model.metadata.relations
        if not relations:
            return vocab
        md = SolrMetadata(solr_config(self.model))
        for relation in relations:
            rel = md.query(q='uid:%s' % relation)
            if rel and rel[0].get('title'):
                title = rel[0].title
            else:
                title = relation
            vocab.append((relation, title))
        return vocab
    
    @property
    def relations_value(self):
        relations = self.relations_vocab
        return [rel[0] for rel in relations]
    
    @property
    def keywords_value(self):
        keywords = self.model.metadata.keywords
        if not keywords:
            keywords = list()
        return u'\n'.join(keywords)
    
    @property
    def data_value(self):
        payload = None
        if self.model.__name__ is not None:
            payload = self.model.model['binary'].payload
        return payload
    
    def keywords_extractor(self, widget, data):
        keywords = data.extracted.split('\n')
        return [kw.strip('\r') for kw in keywords if kw]
    
    def relations_extractor(self, widget, data):
        relations = data.extracted
        if not relations:
            relations = list()
        if isinstance(relations, basestring):
            relations = [relations]
        return relations

    def revision_data(self, data):
        def id(s):
            return '%s.%s' % (self.formname, s)
        data = {
            'title': data.fetch(id('title')).extracted,
            'author': data.fetch(id('author')).extracted,
            'description': data.fetch(id('description')).extracted,
            'keywords': data.fetch(id('keywords')).extracted,
            'relations': data.fetch(id('relations')).extracted,
            'effective': data.fetch(id('effective')).extracted,
            'expires': data.fetch(id('expires')).extracted,
            'alttag': data.fetch(id('alttag')).extracted,
            'data': data.fetch(id('data')).extracted,
            'visibility': data.fetch(id('visibility')).extracted,
            'flag': data.fetch(id('flag')).extracted,
        }
        data['body'] = ' '.join([
            data['title'],
            data['description'], 
            data['author'],
            data['alttag'],
            ', '.join(data['keywords']),
        ])
        return data


registerTile('content',
             'templates/revision.pt',
             interface=RevisionAdapter,
             class_=ProtectedContentTile,
             permission='login',
             strict=False)


@tile('addform', interface=RevisionAdapter, permission="add")
class RevisionAddForm(RevisionForm, Form):
    __metaclass__ = plumber
    __plumbing__ = AddPart
    
    def save(self, widget, data):
        add_revision(self.request,
                     self.model.__parent__,
                     self.revision_data(data))
        

@tile('editform', interface=RevisionAdapter, permission="edit")
class RevisionEditForm(RevisionForm, Form):
    __metaclass__ = plumber
    __plumbing__ = EditPart
    
    def save(self, widget, data):
        update_revision(self.request,
                        self.model,
                        self.revision_data(data))