import simplejson
import dateutil.parser
import time
from datetime import datetime

from django.utils.http import urlencode
from django.test import TestCase
from django.core.urlresolvers import reverse

from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase
from corehq.apps.groups.models import Group

from corehq.pillows.xform import XFormPillow
from corehq.pillows.case import CasePillow
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.api.resources import v0_1, v0_4

class FakeES(object):
    """
    A mock of ES that will return the docs that have been
    added regardless of the query.
    """
    
    def __init__(self):
        self.docs = []

    def add_doc(self, id, doc):
        self.docs.append(doc)
    
    def run_query(self, query):
        return {
            'hits': {
                'total': len(self.docs),
                'hits': [{'_source': doc} for doc in self.docs]
            }
        }


class TestXFormInstanceResource(TestCase):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    
    def setUp(self):
        self.maxDiff = None
        
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                      api_name='v0.4', 
                                                                      resource_name=v0_4.XFormInstanceResource.Meta.resource_name))
        

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_get_resource_list_uri_nomatch(self):
        """
        Checks that a misuse of get_resource_list_uri results in it returning None,
        which is apparently the Tastypie way.
        """
        self.assertEquals(v0_4.XFormInstanceResource().get_resource_list_uri(), None)

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        # In order to test just the API code, we set up a fake XFormES (this should
        # really be a parameter to the XFormInstanceResource constructor)
        # and write the translated form directly; we are not trying to test
        # the ptop infrastructure.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        pillow = XFormPillow(online=False)
        fake_xform_es = FakeES()
        v0_4.MOCK_XFORM_ES = fake_xform_es

        backend_form = XFormInstance(xmlns = 'fake-xmlns',
                                     domain = self.domain.name,
                                     received_on = datetime.utcnow(),
                                     form = {
                                         '#type': 'fake-type',
                                         '@xmlns': 'fake-xmlns'
                                     })
        backend_form.save()
        translated_doc = pillow.change_transform(backend_form.to_json())
        fake_xform_es.add_doc(translated_doc['_id'], translated_doc)

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_forms = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)

        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], backend_form.xmlns)
        self.assertEqual(api_form['received_on'], backend_form.received_on.isoformat())

        backend_form.delete()

    def test_get_list_xmlns(self):
        """
        Forms can be filtered by passing ?xmlns=<xmlns>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        fake_xform_es = FakeES()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        def mock_run_query(es_query):
            self.assertEqual(
                sorted(es_query['filter']['and']), 
                [{'term': {'doc_type': 'xforminstance'}},
                 {'term': {'domain.exact': 'qwerty'}},
                 {'term': {'xmlns.exact': 'foo'}}])
            

            return prior_run_query(es_query)
            
        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        self.client.login(username=self.username, password=self.password)

        response = self.client.get('%s?%s' % (self.list_endpoint, urlencode({'xmlns': 'foo'})))
        self.assertEqual(response.status_code, 200)

    def test_get_list_received_on(self):
        """
        Forms can be filtered by passing ?recieved_on_start=<date>&received_on_end=<date>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        fake_xform_es = FakeES()
        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        def mock_run_query(es_query):
            
            self.assertEqual(sorted(es_query['filter']['and']), [
                {'range': {'received_on': {'from': start_date.isoformat()}}},
                {'range': {'received_on': {'to': end_date.isoformat()}}},
                {'term': {'doc_type': 'xforminstance'}},
                {'term': {'domain.exact': 'qwerty'}},
            ])

            return prior_run_query(es_query)
            
        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        self.client.login(username=self.username, password=self.password)

        response = self.client.get('%s?%s' % (self.list_endpoint, urlencode({
            'received_on_end': end_date.isoformat(),
            'received_on_start': start_date.isoformat(),
        })))

        self.assertEqual(response.status_code, 200)

class TestCommCareCaseResource(TestCase):
    """
    Tests the CommCareCaseResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    
    def setUp(self):
        self.maxDiff = None
        
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                      api_name='v0.4', 
                                                                      resource_name=v0_4.CommCareCaseResource.Meta.resource_name))
        

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        # In order to test just the API code, we set up a fake XFormES (this should
        # really be a parameter to the XFormInstanceResource constructor)
        # and write the translated form directly; we are not trying to test
        # the ptop infrastructure.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        pillow = CasePillow(online=False)
        fake_case_es = FakeES()
        v0_4.MOCK_CASE_ES = fake_case_es

        backend_case = CommCareCase(domain = self.domain.name,
                                    server_modified_on = datetime.utcnow())
        backend_case.save()
        translated_doc = pillow.change_transform(backend_case.to_json())
        fake_case_es.add_doc(translated_doc['_id'], translated_doc)

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_cases = api_cases[0]
        self.assertEqual(dateutil.parser.parse(api_cases['server_date_modified']), backend_case.server_modified_on)

        backend_case.delete()

class TestGroupResource(TestCase):
    """
    Tests the GroupResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    
    def setUp(self):
        self.maxDiff = None
        
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                      api_name='v0.4', 
                                                                      resource_name=v0_4.GroupResource.Meta.resource_name))
        

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_get_list(self):
        """
        Any group in the appropriate domain should be in the list from the API. Currenly does
        not support paging; only ESQuerySet enables this as there's nothing from Couch that makes
        it match Tastypie's concepts.
        """

        backend_group = Group(domain = self.domain.name, name = 'foozle')
        backend_group.save()

        # Poke the view; ensure that if anything gets misconfigured to be 'ok' it does not break the test
        backend_groups = Group.by_domain(self.domain.name)
        time.sleep(0.1)    

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 1)

        api_group = api_groups[0]
        self.assertEqual(api_group['name'], backend_group.name)

        backend_group.delete()

class TestUserResource(TestCase):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
        
    def setUp(self):
        self.maxDiff = None
        
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                      api_name='v0.4', 
                                                                      resource_name=v0_1.CommCareUserResource.Meta.resource_name))
        

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def test_get_list(self):
        self.client.login(username=self.username, password=self.password)

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****')
        backend_id = commcare_user.get_id
        CommCareUser.by_domain(self.domain.name)
        time.sleep(0.1)    

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self.assertEqual(api_users[0]['id'], backend_id)    

        commcare_user.delete()
