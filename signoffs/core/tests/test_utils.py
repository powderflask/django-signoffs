"""
signoffs.utils test suite
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from signoffs.core import utils


class UtilsTests(SimpleTestCase):
    def test_regexs(self):
        self.assertEqual(
            utils.split_caps_run.sub(r"\1_\2", "abstractHTTPResponseCode"),
            "abstractHTTP_ResponseCode",
        )

    def test_camel_to_snake(self):
        self.assertEqual(
            utils.camel_to_snake("camel2_camel2_case"), "camel2_camel2_case"
        )
        self.assertEqual(utils.camel_to_snake("NormalClassName"), "normal_class_name")
        self.assertEqual(
            utils.camel_to_snake("abstractHTTPResponseCode"),
            "abstract_http_response_code",
        )
        self.assertEqual(
            utils.camel_to_snake("HTTPResponseCodeXYZ"), "http_response_code_xyz"
        )

    def test_id_to_camel(self):
        self.assertEqual(utils.id_to_camel("NormalClassName"), "NormalClassName")
        self.assertEqual(utils.id_to_camel("snake_snake_case"), "SnakeSnakeCase")
        self.assertEqual(utils.id_to_camel("dot.separated-id"), "DotSeparatedId")


data = SimpleNamespace(
    obj1=SimpleNamespace(
        attr1="Dent",
        attr2=42,
    ),
    obj2=SimpleNamespace(obj=SimpleNamespace(attr1="Route", attr2=66)),
)


class AccessorTests(SimpleTestCase):
    def test_basic_resolve(self):
        x = utils.Accessor("obj1__attr1")
        self.assertEqual(x.resolve(data), "Dent")
        x = utils.Accessor("obj1__attr2")
        self.assertEqual(x.resolve(data), 42)

    def test_penultimate(self):
        x = utils.Accessor("obj2__obj__attr2")
        self.assertEqual(x.resolve(data), 66)
        w, r = x.penultimate_accessor()
        self.assertEqual((w, r), ("obj2__obj", "attr2"))
        self.assertEqual(w.resolve(data), data.obj2.obj)
        v, r = w.penultimate_accessor()
        self.assertEqual((v, r), ("obj2", "obj"))
        self.assertEqual(v.resolve(data), data.obj2)
        u, r = v.penultimate_accessor()
        self.assertEqual((u, r), ("", "obj2"))
        self.assertEqual(u.resolve(data), None)
