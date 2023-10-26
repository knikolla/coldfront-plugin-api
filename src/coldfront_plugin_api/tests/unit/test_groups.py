import json
import os
import unittest
from unittest import mock
import uuid
from os import devnull
import sys

from coldfront_plugin_api import urls
from coldfront_plugin_api.tests.unit import base, fakes

from coldfront.core.resource import models as resource_models
from coldfront.core.allocation import models as allocation_models
from django.core.management import call_command
from rest_framework.test import APIClient


class TestAllocation(base.TestBase):

    def setUp(self) -> None:
        self.maxDiff = None
        super().setUp()
        self.resource = resource_models.Resource.objects.all().first()

    @property
    def admin_client(self):
        client = APIClient()
        client.login(username='admin', password='test1234')
        return client

    @property
    def logged_in_user_client(self):
        client = APIClient()
        client.login(username='cgray', password='test1234')
        return client

    def test_list_groups(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 1)

        response = self.admin_client.get("/api/scim/v2/Groups")
        desired_in_response = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": allocation.id,
            "displayName": f"Members of allocation {allocation.id} of project {allocation.project.title}",
            "members": []
        }

        self.assertEqual(response.status_code, 200)
        self.assertIn(desired_in_response, response.json())

    def test_get_group(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 1)

        response = self.admin_client.get(f"/api/scim/v2/Groups/{allocation.id}")

        desired_response = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": allocation.id,
            "displayName": f"Members of allocation {allocation.id} of project {allocation.project.title}",
            "members": []
        }
        self.assertEqual(response.json(), desired_response)

    def test_add_remove_group_members(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 1)

        payload = {
            "schemas": [
                "urn:ietf:params:scim:api:messages:2.0:PatchOp"
            ],
            "Operations": [
                {
                    "op": "add",
                    "value": {
                        "members": [
                            {
                                "value": user.username
                            }
                        ]
                    }
                }
            ]
        }
        response = self.admin_client.patch(f"/api/scim/v2/Groups/{allocation.id}",
                                           data=payload,
                                           format="json")
        self.assertEqual(response.status_code, 200)

        desired_response = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": allocation.id,
            "displayName": f"Members of allocation {allocation.id} of project {allocation.project.title}",
            "members": [{
                "value": user.username,
                "$ref": user.username,
                "display": user.username,
            }]
        }
        response = self.admin_client.get(f"/api/scim/v2/Groups/{allocation.id}")
        self.assertEqual(response.json(), desired_response)

        payload = {
            "schemas": [
                "urn:ietf:params:scim:api:messages:2.0:PatchOp"
            ],
            "Operations": [
                {
                    "op": "remove",
                    "value": {
                        "members": [
                            {
                                "value": user.username
                            }
                        ]
                    }
                }
            ]
        }
        response = self.admin_client.patch(f"/api/scim/v2/Groups/{allocation.id}",
                                           data=payload,
                                           format="json")
        desired_response = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": allocation.id,
            "displayName": f"Members of allocation {allocation.id} of project {allocation.project.title}",
            "members": []
        }
        self.assertEqual(response.json(), desired_response)

    @mock.patch(
        "coldfront.core.user.utils.CombinedUserSearch",
        fakes.FakeUserSearch
    )
    def test_add_user_fetched(self):
        user = self.new_user()
        project = self.new_project(pi=user)
        allocation = self.new_allocation(project, self.resource, 1)

        # Attempt adding non-existing user
        payload = {
            "schemas": [
                "urn:ietf:params:scim:api:messages:2.0:PatchOp"
            ],
            "Operations": [
                {
                    "op": "add",
                    "value": {
                        "members": [
                            {
                                "value": uuid.uuid4().hex
                            }
                        ]
                    }
                }
            ]
        }
        response = self.admin_client.patch(f"/api/scim/v2/Groups/{allocation.id}",
                                           data=payload,
                                           format="json")
        self.assertEqual(response.status_code, 400)

        # Attempt adding non-existing user, that exists from search
        payload = {
            "schemas": [
                "urn:ietf:params:scim:api:messages:2.0:PatchOp"
            ],
            "Operations": [
                {
                    "op": "add",
                    "value": {
                        "members": [
                            {
                                "value": "fake-user-1"
                            }
                        ]
                    }
                }
            ]
        }
        response = self.admin_client.patch(f"/api/scim/v2/Groups/{allocation.id}",
                                           data=payload,
                                           format="json")
        self.assertEqual(response.status_code, 200)

    def test_normal_user_forbidden(self):
        response = self.logged_in_user_client.get(f"/api/scim/v2/Groups")
        self.assertEqual(response.status_code, 403)

        response = self.logged_in_user_client.get(f"/api/scim/v2/Groups/1234")
        self.assertEqual(response.status_code, 403)

        response = self.logged_in_user_client.patch(
            f"/api/scim/v2/Groups/1234",
            data={},
            format="json"
        )
        self.assertEqual(response.status_code, 403)
