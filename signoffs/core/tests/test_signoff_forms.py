"""
App-independent tests for signoff forms - no app logic
"""
from django.test import SimpleTestCase, TestCase
from signoffs.forms import AbstractSignoffForm, SignoffField, signoff_form_factory
from . import fixtures, models


class FormSignoff(models.BasicSignoff):
    signetModel = models.Signet
    label = 'Consent?'


signoff_type = FormSignoff.register(id='test.form_signoff', perm='auth.add_signoff')


class SignoffFieldTests(SimpleTestCase):
    def test_clean_signoff(self):
        f = SignoffField(signoff_type=signoff_type)
        v = f.clean('True')
        self.assertIsNotNone(v)
        self.assertEqual(type(v), signoff_type)
        self.assertEqual(v.id, signoff_type.id)

    def test_clean_none(self):
        f = SignoffField(signoff_type=signoff_type)
        v = f.clean('False')
        self.assertIsNone(v)

    def test_label_default(self):
        f = SignoffField(signoff_type=signoff_type)
        self.assertEqual(f.label, signoff_type.label)

    def test_label_override(self):
        f = SignoffField(signoff_type=signoff_type, label='Custom label')
        self.assertEqual(f.label, 'Custom label')


class SignoffFormTests(SimpleTestCase):
    def setUp(self):
        self.formClass = signoff_form_factory(signoff_type=signoff_type)

    def test_form_factory(self):
        self.assertTrue(issubclass(self.formClass, AbstractSignoffForm))

    def test_bound_form(self):
        data = dict(
            signoff='True',
            signoff_id=signoff_type.id
        )
        bf = self.formClass(data=data)
        self.assertTrue(bf.is_signed_off())

    def test_invalid_bound_form(self):
        data = dict(
            signoff='True',
            signoff_id='invalid.type'
        )
        bf = self.formClass(data)
        self.assertFalse(bf.is_valid())


class SignoffWithUserTests(TestCase):
    def setUp(self):
        self.formClass = signoff_form_factory(signoff_type=signoff_type)

    def test_with_user(self):
        u = fixtures.get_user(perms=('add_signoff',))
        data = dict(
            signoff='True',
            signoff_id=signoff_type.id
        )
        bf = self.formClass(data=data, user=u)
        self.assertTrue(bf.is_signed_off())

    def test_save(self):
        u = fixtures.get_user(perms=('add_signoff',))
        data = dict(
            signoff='True',
            signoff_id=signoff_type.id
        )
        bf = self.formClass(data=data, user=u)
        self.assertTrue(bf.is_valid())
        v = bf.save(commit=False)
        self.assertEqual(v.id, signoff_type.id)
        self.assertEqual(v.signet.user, u)

    def test_invalid_user(self):
        u = fixtures.get_user(username='NoCanDoBoo')
        data = dict(
            signoff='True',
            signoff_id='invalid.type'
        )
        bf = self.formClass(data, user=u)
        self.assertFalse(bf.is_valid())
