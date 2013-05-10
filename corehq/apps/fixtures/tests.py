import simplejson
from xml.etree import ElementTree

from django.test import TestCase
from django.core.urlresolvers import reverse
from casexml.apps.case.tests.util import check_xml_line_by_line

from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures import fixturegenerators
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership
from corehq.apps.fixtures.resources import v0_1

class FixtureDataTest(TestCase):
    def setUp(self):
        self.domain = 'qwerty'

        self.data_type = FixtureDataType(
            domain=self.domain,
            tag="contact",
            name="Contact",
            fields=['name', 'number']
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
                'name': 'John',
                'number': '+15555555555'
            }
        )
        self.data_item.save()

        self.username = 'rudolph'
        self.password = '***'
        self.user = CommCareUser.create(self.domain, self.username, self.password)

        self.fixture_ownership = FixtureOwnership(
            domain=self.domain,
            owner_id=self.user.get_id,
            owner_type='user',
            data_item_id=self.data_item.get_id
        )
        self.fixture_ownership.save()

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()
        self.user.delete()
        self.fixture_ownership.delete()

    def test_xml(self):
        check_xml_line_by_line(self, """
        <contact>
            <name>John</name>
            <number>+15555555555</number>
        </contact>
        """, ElementTree.tostring(self.data_item.to_xml()))

    def test_ownership(self):
        self.assertItemsEqual([self.data_item.get_id], FixtureDataItem.by_user(self.user, wrap=False))
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

        fixture, = fixturegenerators.item_lists(self.user)

        check_xml_line_by_line(self, """
        <fixture id="item-list:contact" user_id="%s">
            <contact_list>
                <contact>
                    <name>John</name>
                    <number>+15555555555</number>
                </contact>
            </contact_list>
        </fixture>
        """ % self.user.user_id, ElementTree.tostring(fixture))

        self.data_item.remove_user(self.user)
        self.assertItemsEqual([], self.data_item.get_all_users())

        self.fixture_ownership = self.data_item.add_user(self.user)
        self.assertItemsEqual([self.user.get_id], self.data_item.get_all_users(wrap=False))

class FixtureResourceTests(TestCase):
    def setUp(self):
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.data_type = FixtureDataType(
            domain=self.domain.name,
            tag="contact",
            name="Contact",
            fields=['name', 'number']
        )
        self.data_type.save()

        self.data_item = FixtureDataItem(
            domain=self.domain.name,
            data_type_id=self.data_type.get_id,
            fields={
                'name': 'John',
                'number': '+15555555555'
            }
        )
        self.data_item.save()

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

        self.fixture_ownership = FixtureOwnership(
            domain=self.domain.name,
            owner_id=self.user.get_id,
            owner_type='user',
            data_item_id=self.data_item.get_id
        )
        self.fixture_ownership.save()

    def tearDown(self):
        self.data_type.delete()
        self.data_item.delete()
        self.user.delete()
        self.fixture_ownership.delete()
        self.domain.delete()

    def test_get_list(self):
        """
        Ensures that objects created in the backend are accessible in the API.
        This *should* be able to be tested without the use of `urls`, etc,
        but it is most expedient to use Django & Tastypie's harnesses and
        examples.
        """

        self.client.login(username=self.username, password=self.password)
        endpoint_url = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                api_name='v0.1', 
                                                                resource_name=v0_1.FixtureResource.Meta.resource_name))
        response = self.client.get(endpoint_url)
        self.assertEqual(response.status_code, 200)

        fixtures = simplejson.loads(response.content)['objects']
        
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(len(fixtures[0]['users']), 1)
        self.assertEqual(len(fixtures[0]['groups']), 0)

