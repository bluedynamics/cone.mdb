from repoze.workflow import get_workflow
from repoze.workflow import WorkflowError
from cone.tile import (
    tile,
    Tile,
)
from cone.app.model import Properties
from cone.app.browser.ajax import (
    AjaxAction,
    AjaxEvent,
)
from cone.app.browser.utils import (
    make_query,
    make_url,
)

import logging
logger = logging.getLogger('cone.mdb')


@tile('wf_dropdown', 'templates/wf_dropdown.pt', 
      permission='view', strict=False)
class WfDropdown(Tile):
    """Transition dropdown.
    
    If ``do_transition`` is found in ``request.params``, perform given
    transition on ``self.model`` immediately before dropdown gets rendered.
    
    XXX: move me to cone.app
         make continuation for ajax actions (bdajax)
         make bdajax actions work with something like 'actionname:NONE:NONE'
    
    Configuration expected on ``self.model.properties``:
    
    ``wf_state``
        Flag whether model provides workflow.
    ``wf_name``
        Registration name of workflow.
    ``wf_transition_names``
        transition id to transition title mapping. XXX: get rid of
    """
    
    def do_transition(self):
        """if ``do_transition`` is found on request.params, perform transition.
        """
        transition = self.request.params.get('do_transition')
        if not transition:
            return
        workflow = self.workflow
        workflow.transition(self.model, self.request, transition)
        self.model()
        url = make_url(self.request, node=self.model)
        continuation = [
            AjaxAction(url, 'content', 'inner', '#content'),
            AjaxEvent(url, 'contextchanged', '.contextsensitiv'),
        ]
        self.request.environ['cone.app.continuation'] = continuation
        
    @property
    def workflow(self):
        return get_workflow(self.model.__class__, self.model.properties.wf_name)
    
    @property
    def transitions(self):
        self.do_transition()
        ret = list()
        workflow = self.workflow
        try:
            transitions = workflow.get_transitions(
                self.model, self.request, from_state=self.model.state)
        except WorkflowError, e:                            #pragma NO COVERAGE
            logger.error("transitions error: %s" % str(e))  #pragma NO COVERAGE
            return ret                                      #pragma NO COVERAGE
        # XXX: check in repoze.workflow the intended way for naming
        #      transitions
        transition_names = self.model.properties.wf_transition_names
        for transition in transitions:
            query = make_query(do_transition=transition['name'])
            url = make_url(self.request, node=self.model,
                           resource='dotransition', query=query)
            target = make_url(self.request, node=self.model, query=query)
            props = Properties()
            props.url = url
            props.target = target
            props.title = transition_names[transition['name']]
            ret.append(props)
        return ret