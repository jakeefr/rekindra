import json
import re
import tempfile
from pathlib import Path
import unittest
from test_worlds import world
from test_tga import fixture
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.scenes import SceneError


class InspectionCameraTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.local/tests';base.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(temp.cleanup)
        root=Path(temp.name);source=root/'input';source.mkdir();(source/'old.tga').write_bytes(fixture())
        self.projects=ProjectStore(root/'projects');p=self.projects.inspect(source)
        self.pid=p['project_id'];aid=p['assets'][0]['asset_id'];self.store=CompositionStore(self.projects)
        self.plan=self.store.save_plan(self.pid,world(aid),[aid],{'origin':'test'})

    def test_inspection_is_static_separate_and_preserves_original_bytes(self):
        original=self.store.build(self.pid,self.plan['plan_id']);html=Path(original['path']).read_bytes()
        record=Path(original['plan_path']).read_bytes()
        camera={'eye':[1,3,-7],'target':[0,.9,0],'fov':57}
        view=self.store.build(self.pid,self.plan['plan_id'],review_camera=camera)
        self.assertNotEqual(view['path'],original['path']);self.assertTrue(view['inspection_only'])
        self.assertEqual(Path(original['path']).read_bytes(),html)
        self.assertEqual(Path(original['plan_path']).read_bytes(),record)
        content=Path(view['path']).read_text()
        payload=json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>',content,re.S).group(1))
        self.assertTrue(payload['inspection_only'])
        self.assertEqual(payload['scene']['camera'],[dict(camera,at=0),dict(camera,at=12)])
        self.assertEqual(payload['scene']['objects'],self.plan['scene']['objects'])
        self.assertEqual(len(list((self.projects._project(self.pid)/'plans').glob('*.json'))),1)

    def test_bad_override_cannot_write_artifact(self):
        directory=self.projects._project(self.pid)/'artifacts';before=set(directory.iterdir())
        for camera in ({},[],{'eye':[1,1,1],'target':[1,1,1],'fov':50},
                       {'eye':[0,0,6],'target':[0,0,0],'fov':False},
                       {'eye':[0,0,6],'target':[0,0,0],'fov':50,'at':3}):
            with self.subTest(camera=camera),self.assertRaises(SceneError):
                self.store.build(self.pid,self.plan['plan_id'],review_camera=camera)
        self.assertEqual(set(directory.iterdir()),before)
