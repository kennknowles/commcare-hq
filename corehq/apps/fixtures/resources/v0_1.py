from django.core.urlresolvers import reverse
from tastypie import fields as tp_f
from tastypie.bundle import Bundle

from corehq.apps.api.resources import JsonResource, DomainSpecificResourceMixin
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, DomainAdminAuthorization
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType

def convert_fdt(fdi):
    fdt = FixtureDataType.get(fdi.data_type_id)
    fdi.fixture_type = fdt.tag
    return fdi

class FixtureResource(JsonResource):
    type = "fixture"
    fields = tp_f.DictField(attribute='fields', readonly=True, unique=True)
    fixture_type = tp_f.CharField(attribute='fixture_type', readonly=True)
    id = tp_f.CharField(attribute='_id', readonly=True, unique=True)

    users = tp_f.ListField(attribute='get_user_ids')
    groups = tp_f.ListField(attribute='get_group_ids')

    def obj_get(self, bundle, **kwargs):
        return convert_fdt(get_object_or_not_exist(FixtureDataItem, kwargs['pk'], kwargs['domain']))

    def obj_get_list(self, bundle, **kwargs):
        request = bundle.request    
        domain = kwargs['domain']
        parent_id = request.GET.get("parent_id", None)
        parent_ref_name = request.GET.get("parent_ref_name", None)
        references = request.GET.get("references", None)
        child_type = request.GET.get("child_type", None)
        type_id = request.GET.get("fixture_type_id", None)
        type_tag = request.GET.get("fixture_type", None)

        if parent_id and parent_ref_name and child_type and references:
            parent_fdi = FixtureDataItem.get(parent_id)
            fdis = list(FixtureDataItem.by_field_value(domain, child_type, parent_ref_name, parent_fdi.fields['id']))
        elif type_id or type_tag:
            type_id = type_id or FixtureDataType.by_domain_tag(domain, type_tag).one()
            fdis = list(FixtureDataItem.by_data_type(domain, type_id))
        else:
            fdis = list(FixtureDataItem.by_domain(domain))

        return [convert_fdt(fdi) for fdi in fdis] or []

    def obj_create(self, bundle, request=None, **kwargs):
        # full_dehydrate will handle copying over the fields, but we still must implement *something* here

        bundle.obj.domain = kwargs['domain']
        for key, value in bundle.data.items():
            setattr(bundle.obj, key, value)

        bundle = self.full_hydrate(bundle)
        bundle.obj.save()
        
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj.domain = kwargs['domain']
        bundle.obj._id = kwargs['pk'] # This comes from the URL
        for key, value in bundle.data.items():
            setattr(bundle.obj, key, value)

        bundle = self.full_hydrate(bundle)
        bundle.obj.save()

        return bundle

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None
        else:
            obj = bundle_or_obj

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj.get_id))
                                   


    class Meta(CustomResourceMeta):
        object_class = FixtureDataItem    
        authorization = DomainAdminAuthorization()
        resource_name = 'fixture'
        limit = 0
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get']
