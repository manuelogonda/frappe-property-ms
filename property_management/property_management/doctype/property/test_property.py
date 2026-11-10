# Copyright (c) 2026, mnorg and Contributors
# See license.txt


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list


import frappe
from frappe.tests.utils import FrappeTestCase


class TestProperty(FrappeTestCase):

	def make_landlord(self, national_id, status="Pending"):
		return frappe.get_doc({
			"doctype": "Landlord",
			"landlord_type": "Individual",
			"landlord_name": f"Test {national_id}",
			"phone": "0712345678",
			"national_id_or_registration": national_id,
			"status": status,
		}).insert(ignore_permissions=True)

	def make_property(self, code, landlords, status="Draft"):
		return frappe.get_doc({
			"doctype": "Property",
			"property_name": "Test Property",
			"property_code": code,
			"property_type": "Residential",
			"address": "Test address",
			"county": "Nairobi",
			"townarea": "Westlands",
			"status": status,
			"landlords": [
				{
					"landlord": landlord,
					"share_percent": share,
					"is_primary_contact": primary
				}
				for landlord, share, primary in landlords
			],
		})

	def test_code_is_normalised(self):
		landlord = self.make_landlord("TST0001")

		prop = self.make_property(
			"wst-001",
			[(landlord.name, 100, 1)]
		).insert(ignore_permissions=True)

		self.assertEqual(prop.name, "WST-001")

	def test_draft_allows_incomplete_ownership(self):
		landlord = self.make_landlord("TST0002")

		prop = self.make_property(
			"WST-002",
			[(landlord.name, 60, 1)]
		).insert(ignore_permissions=True)

		self.assertEqual(prop.status, "Draft")

	def test_active_shares_must_total_100(self):
		landlord_a = self.make_landlord("TST0003")
		landlord_b = self.make_landlord("TST0004")

		with self.assertRaises(frappe.ValidationError):
			self.make_property(
				"WST-003",
				[
					(landlord_a.name, 60, 1),
					(landlord_b.name, 30, 0)
				],
				status="Active"
			).insert(ignore_permissions=True)

	def test_active_requires_exactly_one_primary_contact(self):
		landlord_a = self.make_landlord("TST0005")
		landlord_b = self.make_landlord("TST0006")

		with self.assertRaises(frappe.ValidationError):
			self.make_property(
				"WST-004",
				[
					(landlord_a.name, 60, 0),
					(landlord_b.name, 40, 0)
				],
				status="Active"
			).insert(ignore_permissions=True)

	def test_duplicate_landlord_is_rejected(self):
		landlord = self.make_landlord("TST0007")

		with self.assertRaises(frappe.ValidationError):
			self.make_property(
				"WST-005",
				[
					(landlord.name, 50, 1),
					(landlord.name, 50, 0)
				]
			).insert(ignore_permissions=True)

	def test_rejected_landlord_cannot_be_linked(self):
		landlord = self.make_landlord(
			"TST0008",
			status="Rejected"
		)

		with self.assertRaises(frappe.ValidationError):
			self.make_property(
				"WST-006",
				[(landlord.name, 100, 1)]
			).insert(ignore_permissions=True)

	def test_active_requires_landlord(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_property(
				"WST-007",
				[],
				status="Active"
			).insert(ignore_permissions=True)

