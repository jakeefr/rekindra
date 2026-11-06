import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world
from rekindra_core.scenes import SceneError


class LightingControlTests(unittest.TestCase):
    def test_bounded_optional_hemisphere_controls(self):
        s=world();s['environment'].update(ambient_strength=.6,ground_color='#503821',ground_strength=.8)
        self.assertEqual(validate_world(s,{'a'*32}),s)
        for field,value in [('ambient_strength',-1),('ambient_strength',True),('ground_strength',1.1),('ground_color','red')]:
            s=world();s['environment'][field]=value
            with self.subTest(field=field),self.assertRaises(SceneError):validate_world(s,{'a'*32})
