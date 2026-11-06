import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError


def mirror_scene():
    s=world();o=s['objects'][0];o['position']['y']='0';o['reflection']=dict(strength=.5,blur=2)
    return s


class PlanarReflectionTests(unittest.TestCase):
    def test_optional_contract_and_immutable_removal(self):
        s=mirror_scene();self.assertEqual(validate_world(s,{'a'*32}),s)
        original=copy.deepcopy(s)
        clean,changed=revise_world(s,[dict(object_id='sea',field='reflection',value=None)],{'a'*32})
        self.assertEqual(s,original);self.assertNotIn('reflection',clean['objects'][0])
        self.assertEqual(changed,['objects/sea/reflection'])
        self.assertIn('reflection',WORLD_SCHEMA['properties']['objects']['items']['properties'])
        s['objects'][0]['reflection']['strength']=0;validate_world(s,{'a'*32})

    def test_rejects_ambiguous_or_unbounded_reflectors(self):
        bad=[None,{},dict(strength=True,blur=0),dict(strength=1.1,blur=0),
             dict(strength=.5,blur=-1),dict(strength=.5,blur=9),dict(strength=.5,blur=0,extra=1)]
        for value in bad:
            s=mirror_scene();s['objects'][0]['reflection']=value
            with self.subTest(value=value),self.assertRaises(SceneError):validate_world(s,{'a'*32})
        for y in ['u','0*t','1+1','81','nan','inf','1_0']:
            s=mirror_scene();s['objects'][0]['position']['y']=y
            with self.subTest(y=y),self.assertRaises(SceneError):validate_world(s,{'a'*32})
        for field,value in [('caps',[]),('instances',[dict(offset=[0,0,0],scale=[1,1,1])]),('assembly','x'),('loft',[])]:
            s=mirror_scene();s['objects'][0][field]=value
            with self.subTest(field=field),self.assertRaises(SceneError):validate_world(s,{'a'*32})
        s=mirror_scene();s['objects'].append(dict(copy.deepcopy(s['objects'][0]),id='second'))
        with self.assertRaisesRegex(SceneError,'one active'):validate_world(s,{'a'*32})
