import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, compile_surface
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError

def loft():
    return [{'height':0,'points':[[-1,-1],[1,-1],[1,1],[-1,1]]},
            {'height':3,'points':[[-.4,-.4],[.4,-.4],[.4,.4],[-.4,.4]]}]

def scene():
    s=world();o=s['objects'][0];o.update(loft=loft(),position={'x':'loft_x','y':'loft_y','z':'loft_z'},segments=[8,8]);return s

class LoftTests(unittest.TestCase):
    def test_valid_compilation_and_reserved_coordinates(self):
        s=scene();validate_world(s,{'a'*32});c=compile_surface(s['objects'][0]);self.assertGreater(c['cost'],3)
        self.assertIn('rk_loft',c['definitions'])
        for section in s['objects'][0]['loft']:section['points'].reverse()
        validate_world(s,{'a'*32})
        s['objects'][0]['bindings']=[{'name':'loft_x','expression':'0'}]
        with self.assertRaises(SceneError):validate_world(s,{'a'*32})
        s=scene();del s['objects'][0]['loft']
        with self.assertRaises(SceneError):validate_world(s,{'a'*32})

    def test_invalid_sections(self):
        bad=[None,[],loft()[:1],loft()*5]
        for value in (True,float('nan'),81):
            r=loft();r[0]['points'][0][0]=value;bad.append(r)
        r=loft();r[1]['height']=0;bad.append(r)
        r=loft();r[1]['points'].reverse();bad.append(r)
        r=loft();r[1]['points'][1]=[0,0];bad.append(r)
        r=loft();r[0]['extra']=1;bad.append(r)
        r=loft();r[1]['points'].append(r[1]['points'][0]);bad.append(r)
        for value in bad:
            s=scene();s['objects'][0]['loft']=value
            with self.subTest(value=value),self.assertRaises(SceneError):validate_world(s,{'a'*32})

    def test_alignment_and_work(self):
        s=scene();s['objects'][0]['segments']=[7,8]
        with self.assertRaisesRegex(SceneError,'align'):validate_world(s,{'a'*32})
        s=scene();s['objects'][0]['loft']=[dict(height=i,points=loft()[0]['points']) for i in range(4)]
        with self.assertRaisesRegex(SceneError,'align'):validate_world(s,{'a'*32})
        s=scene();s['objects'][0]['segments']=[128,96];s['objects'][0]['instances']=[{'offset':[0,0,0],'scale':[1,1,1]}]*2
        with self.assertRaisesRegex(SceneError,'budget'):validate_world(s,{'a'*32})

    def test_atomic_revision_and_optional_removal(self):
        s=world();o=s['objects'][0];o['segments']=[8,8]
        edits=[{'object_id':'sea','field':'loft','value':loft()},{'object_id':'sea','field':'position','value':scene()['objects'][0]['position']}]
        new,_=revise_world(s,edits,{'a'*32});self.assertNotIn('loft',o)
        with self.assertRaises(SceneError):revise_world(new,[{'object_id':'sea','field':'loft','value':None}],{'a'*32})
        restored,_=revise_world(new,[{'object_id':'sea','field':'loft','value':None},{'object_id':'sea','field':'position','value':o['position']}],{'a'*32})
        self.assertEqual(s,restored)
