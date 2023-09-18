"""
App-independent tests for signoff forms - no app logic
"""
from django.test import SimpleTestCase, TestCase

from signoffs.forms import AbstractSignoffForm, BoundSignoffForms, signoff_form_factory

from . import fixtures, models


class FormTestsSignoff(models.BasicSignoff):
    signetModel = models.Signet
    label = "Consent?"


signoff_type = FormTestsSignoff.register(
    id="test.form_signoff", perm="auth.add_signoff"
)


class SignoffFormTests(SimpleTestCase):
    def setUp(self):
        self.formClass = signoff_form_factory(signoff_type=signoff_type)

    def test_form_factory(self):
        self.assertTrue(issubclass(self.formClass, AbstractSignoffForm))

    def test_bound_form(self):
        data = dict(signed_off="True", signoff_id=signoff_type.id)
        bf = self.formClass(data=data)
        self.assertTrue(bf.is_signed_off())

    def test_invalid_bound_form(self):
        data = dict(signoff="True", signoff_id="invalid.type")
        bf = self.formClass(data)
        self.assertFalse(bf.is_valid())


class SignoffWithUserTests(TestCase):
    def setUp(self):
        self.formClass = signoff_form_factory(signoff_type=signoff_type)

    def test_is_signed_off(self):
        data = dict(signed_off="True", signoff_id=signoff_type.id)
        bf = self.formClass(data=data)
        self.assertTrue(bf.is_signed_off())

    def test_sign(self):
        u = fixtures.get_user(perms=("add_signoff",))
        data = dict(signed_off="True", signoff_id=signoff_type.id)
        bf = self.formClass(data=data)
        self.assertTrue(bf.is_valid())
        v = bf.sign(user=u, commit=False)
        self.assertEqual(v.id, signoff_type.id)
        self.assertEqual(v.signet.user, u)

    def test_invalid_signoff(self):
        data = dict(signed_off="True", signoff_id="invalid.type")
        bf = self.formClass(data)
        self.assertFalse(bf.is_valid())


class BoundSignoffFormTests(TestCase):
    def setUp(self):
        self.data = dict(
            signoff_id=signoff_type.id,
            signed_off="on",
        )

    def get_signoff_form(self):
        """Return a signoff form instance bound to class self.data"""
        forms = BoundSignoffForms(self.data)
        return forms.get_signoff_form()

    def test_create(self):
        self.assertTrue(
            type(self.get_signoff_form()), signoff_type.forms.get_signoff_form_class()
        )

    def test_is_signed_off(self):
        bf = self.get_signoff_form()
        self.assertTrue(bf.is_valid())
        self.assertTrue(bf.is_signed_off())

    def test_not_signed_off(self):
        data = dict(signoff_id=signoff_type.id)
        forms = BoundSignoffForms(data)
        bf = forms.get_signoff_form()
        self.assertTrue(bf.is_valid())
        self.assertFalse(bf.is_signed_off())

    def test_invalid_signoff(self):
        data = dict(signed_off="True", signoff_id="invalid.type")
        forms = BoundSignoffForms(data)
        self.assertIsNone(forms.get_signoff_form())

    def test_invalid_data(self):
        data = dict(signed_off="True")
        forms = BoundSignoffForms(data)
        self.assertIsNone(forms.get_signoff_form())
