import math
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world
from rekindra_core.scenes import SceneError


class InstanceRotationTests(unittest.TestCase):
    def test_optional_rotation_is_bounded(self):
        s=world();placement={'offset':[0,0,0],'scale':[1,1,1],'rotation':[0,0,math.pi/2]}
        s['objects'][0]['instances']=[placement]
        self.assertEqual(validate_world(s,{'a'*32}),s)
        for bad in ([0,0,7],[True,0,0],[0,0,float('nan')],[],None):
            placement['rotation']=bad
            with self.subTest(bad=bad),self.assertRaises(SceneError):validate_world(s,{'a'*32})

    def test_rotation_math_is_charged_to_every_copy(self):
        s=world();s['objects'][0]['segments']=[128,96]
        s['objects'][0]['instances']=[{'offset':[0,0,0],'scale':[1,1,1]}]*2
        validate_world(s,{'a'*32})
        # Extra transform work must be charged, even for identity rotations.
        # A deliberately expensive but permitted position approaches the limit.
        s['objects'][0]['position']['x']='(u-.5)*36'+''.join('+sin(u*'+str(i*2+4)+')' for i in range(14))
        validate_world(s,{'a'*32})
        s['objects'][0]['instances'][0]['rotation']=[0,0,0]
        with self.assertRaisesRegex(SceneError,'budget'):validate_world(s,{'a'*32})
