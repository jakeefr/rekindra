import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError


class ConstructionHeadroomTests(unittest.TestCase):
    def make(self, count=24):
        s=world();o=s['objects'][0];o['segments']=[4,4]
        s['objects']=[dict(copy.deepcopy(o),id=f'part_{i}') for i in range(count)]
        return s

    def test_distinct_construction_parts_are_bounded_at_24(self):
        s=self.make();self.assertEqual(len(validate_world(s,{'a'*32})['objects']),24)
        self.assertEqual(WORLD_SCHEMA['properties']['objects']['maxItems'],24)
        with self.assertRaisesRegex(SceneError,'24'):validate_world(self.make(25),{'a'*32})

    def test_existing_shared_budgets_are_not_raised(self):
        s=self.make()
        for o in s['objects']:o['instances']=[dict(offset=[0,0,0],scale=[1,1,1])]*3
        with self.assertRaisesRegex(SceneError,'64'):validate_world(s,{'a'*32})
        s=self.make()
        for o in s['objects']:o['segments']=[40,40]
        with self.assertRaisesRegex(SceneError,'32000'):validate_world(s,{'a'*32})
        s=self.make()
        for o in s['objects']:o['color_detail']='.1*sin(u*20)'
        with self.assertRaisesRegex(SceneError,'128 total'):validate_world(s,{'a'*32})
        s=self.make()
        for o in s['objects']:
            o['segments']=[32,32]
            o['bindings']=[dict(name=f'b{i}',expression='sin(u*4+v*8+t)') for i in range(16)]
        with self.assertRaisesRegex(SceneError,'4000000'):validate_world(s,{'a'*32})
