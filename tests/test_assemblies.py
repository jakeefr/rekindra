import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, compile_world
from rekindra_core.scenes import SceneError


def assembly(identifier='hinge', **extra):
    return dict(id=identifier,translation={'x':'0','y':'0','z':'0'},
                rotation={'x':'0','y':'0','z':'.3*sin(t)'},pivot=[0,0,0],scale=[1,1,1],**extra)


class AssemblyTests(unittest.TestCase):
    def test_shared_chain_compiles_once_per_surface_and_preserves_legacy(self):
        scene=world();before=compile_world(scene)
        self.assertNotIn('assembly',before[0])
        scene['assemblies']=[assembly('root'),assembly('child',parent='root')]
        scene['objects'][0]['assembly']='child'
        validated=validate_world(scene,{'a'*32});p=compile_world(validated)[0]
        self.assertEqual(p['assembly'].count('p-=vec3('),2)
        self.assertEqual(scene,validated)
        other=copy.deepcopy(scene);other['objects'][0].pop('assembly');other.pop('assemblies')
        self.assertEqual(compile_world(other),before)

    def test_invalid_hierarchies_math_and_missing_references_rejected(self):
        variants=[]
        s=world();s['objects'][0]['assembly']='missing';variants.append(s)
        for groups in ([assembly(parent='hinge')],[assembly(),assembly()],
                       [assembly('child',parent='root'),assembly('root')],
                       [assembly(str(i),**({'parent':str(i-1)} if i else {})) for i in range(5)]):
            s=world();s['assemblies']=groups;variants.append(s)
        for field,value in [('scale',[1,0,1]),('pivot',[False,0,0]),('translation',{'x':'u','y':'0','z':'0'}),
                            ('rotation',{'x':'v','y':'0','z':'0'}),('id',[])]:
            s=world();g=assembly();g[field]=value;s['assemblies']=[g];variants.append(s)
        for s in variants:
            with self.subTest(scene=s),self.assertRaises(SceneError):validate_world(s,{'a'*32})

    def test_transform_work_is_not_free(self):
        s=world();s['objects'][0]['segments']=[128,96]
        s['objects']=[dict(s['objects'][0],id='a'),dict(s['objects'][0],id='b')]
        validate_world(s,{'a'*32})
        s['assemblies']=[assembly(str(i),**({'parent':str(i-1)} if i else {})) for i in range(4)]
        for o in s['objects']:o['assembly']='3'
        with self.assertRaisesRegex(SceneError,'budget'):validate_world(s,{'a'*32})
