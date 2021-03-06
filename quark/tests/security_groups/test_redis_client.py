# Copyright 2014 Openstack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#

import uuid

import mock
import netaddr
import redis

from quark.db import models
from quark import exceptions as q_exc
from quark.security_groups import redis_client
from quark.tests import test_base


class TestRedisSerialization(test_base.TestBase):
    def setUp(self):
        super(TestRedisSerialization, self).setUp()

    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_redis_key(self, redis):
        client = redis_client.Client()
        device_id = str(uuid.uuid4())
        mac_address = netaddr.EUI("AA:BB:CC:DD:EE:FF")

        redis_key = client.rule_key(device_id, mac_address.value)
        expected = "%s.%s" % (device_id, str(mac_address))
        self.assertEqual(expected, redis_key)

    @mock.patch("quark.security_groups.redis_client.Client.rule_key")
    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_apply_rules(self, rule_key, redis):
        client = redis_client.Client()
        port_id = 1
        mac_address = netaddr.EUI("AA:BB:CC:DD:EE:FF")
        client.apply_rules(port_id, mac_address.value, [])
        self.assertTrue(client._client.set.called)

    def test_client_connection_fails_gracefully(self):
        conn_err = redis.ConnectionError
        with mock.patch("redis.Redis") as redis_mock:
            redis_mock.side_effect = conn_err
            with self.assertRaises(q_exc.SecurityGroupsCouldNotBeApplied):
                redis_client.Client()

    def test_apply_rules_set_fails_gracefully(self):
        port_id = 1
        mac_address = netaddr.EUI("AA:BB:CC:DD:EE:FF")
        conn_err = redis.ConnectionError
        with mock.patch("redis.Redis") as redis_mock:
            client = redis_client.Client()
            redis_mock.set.side_effect = conn_err
            client.apply_rules(port_id, mac_address.value, [])

    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_serialize_group_no_rules(self, redis):
        client = redis_client.Client()
        group = models.SecurityGroup()
        payload = client.serialize([group])
        self.assertTrue(payload.get("id") is not None)
        self.assertEqual([], payload.get("rules"))

    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_serialize_group_with_rules(self, redis):
        rule_dict = {"ethertype": 0x800, "protocol": 6, "port_range_min": 80,
                     "port_range_max": 443, "direction": "ingress"}
        client = redis_client.Client()
        group = models.SecurityGroup()
        rule = models.SecurityGroupRule()
        rule.update(rule_dict)
        group.rules.append(rule)

        payload = client.serialize([group])
        self.assertTrue(payload.get("id") is not None)
        rule = payload["rules"][0]
        self.assertEqual(0x800, rule["ethertype"])
        self.assertEqual(6, rule["protocol"])
        self.assertEqual(80, rule["port start"])
        self.assertEqual(443, rule["port end"])
        self.assertEqual("allow", rule["action"])
        self.assertEqual("ingress", rule["direction"])
        self.assertEqual("", rule["source network"])
        self.assertEqual("", rule["destination network"])

    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_serialize_group_with_rules_and_remote_network(self, redis):
        rule_dict = {"ethertype": 0x800, "protocol": 1, "direction": "ingress",
                     "remote_ip_prefix": "192.168.0.0/24"}
        client = redis_client.Client()
        group = models.SecurityGroup()
        rule = models.SecurityGroupRule()
        rule.update(rule_dict)
        group.rules.append(rule)

        payload = client.serialize([group])
        self.assertTrue(payload.get("id") is not None)
        rule = payload["rules"][0]
        self.assertEqual(0x800, rule["ethertype"])
        self.assertEqual(1, rule["protocol"])
        self.assertEqual(None, rule["port start"])
        self.assertEqual(None, rule["port end"])
        self.assertEqual("allow", rule["action"])
        self.assertEqual("ingress", rule["direction"])
        self.assertEqual("::ffff:192.168.0.0/120", rule["source network"])
        self.assertEqual("", rule["destination network"])

    @mock.patch("quark.security_groups.redis_client.redis.Redis")
    def test_serialize_group_egress_rules(self, redis):
        rule_dict = {"ethertype": 0x800, "protocol": 1,
                     "direction": "egress",
                     "remote_ip_prefix": "192.168.0.0/24"}
        client = redis_client.Client()
        group = models.SecurityGroup()
        rule = models.SecurityGroupRule()
        rule.update(rule_dict)
        group.rules.append(rule)

        payload = client.serialize([group])
        self.assertTrue(payload.get("id") is not None)
        rule = payload["rules"][0]
        self.assertEqual(0x800, rule["ethertype"])
        self.assertEqual(1, rule["protocol"])
        self.assertEqual(None, rule["port start"])
        self.assertEqual(None, rule["port end"])
        self.assertEqual("allow", rule["action"])
        self.assertEqual("ingress", rule["direction"])
        self.assertEqual("::ffff:192.168.0.0/120", rule["destination network"])
        self.assertEqual("", rule["source network"])
