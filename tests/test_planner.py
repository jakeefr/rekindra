from types import SimpleNamespace
import unittest
from unittest.mock import patch
import json

from rekindra_core.planner import plan_scene
from rekindra_core.scenes import SceneError
from test_scenes import scene
from test_plugin import plugin


class PlannerTests(unittest.TestCase):
    def test_unsolicited_model_text_is_rejected_and_repaired(self):
        calls=[]
        class Host:
            def complete_structured(self, **kwargs):
                calls.append(kwargs)
                result=scene()
                if len(calls)==2:result['layers']=result['layers'][:1]
                return SimpleNamespace(parsed=result,provider='test',model='test')
        sources=[{'asset_id':'a'*32,'name':'source.png','data':b'bytes','mime_type':'image/png','kind':'original'}]
        result=plan_scene(Host(),sources,'dreamy')
        self.assertEqual(len(calls),2)
        self.assertFalse(any(l['kind']=='text' for l in result['scene']['layers']))

    def test_host_call_is_provider_neutral_and_uses_typed_images(self):
        calls=[]
        class Host:
            def complete_structured(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(parsed=scene(), provider='user-provider', model='user-model', usage={})
        sources=[{'asset_id':'a'*32,'name':'source.png','data':b'bytes','mime_type':'image/png','source_sha256':'b'*64,'kind':'original'}]
        result=plan_scene(Host(),sources,'quiet and dreamy with text',allow_text=True)
        self.assertEqual(result['scene']['title'],'Green afterglow')
        self.assertEqual(result['attribution']['provider'],'user-provider')
        self.assertNotIn('provider',calls[0]);self.assertNotIn('model',calls[0])
        self.assertTrue(any(x.get('data')==b'bytes' for x in calls[0]['input']))

    def test_invalid_model_output_has_bounded_repair(self):
        calls=[]
        class Host:
            def complete_structured(self, **kwargs):
                calls.append(kwargs);return SimpleNamespace(parsed={'script':'evil'},provider='test',model='test')
        with self.assertRaises(SceneError):
            plan_scene(Host(),[{'asset_id':'a'*32,'name':'x','mime_type':'image/png','data':b'x','kind':'original'}],'dreamy')
        self.assertEqual(len(calls),2)

    def test_provider_exception_is_not_exposed(self):
        class Host:
            def complete_structured(self, **kwargs):raise ValueError('sensitive-token')
        with self.assertRaises(SceneError) as caught:
            plan_scene(Host(),[{'asset_id':'a'*32,'name':'x','mime_type':'image/png','data':b'x','kind':'original'}],'dreamy')
        self.assertNotIn('sensitive-token',str(caught.exception))

    def test_image_consent_is_required_before_accessing_store(self):
        def unavailable():raise AssertionError('Must not read sources')
        handlers=plugin.handlers.make_handlers(unavailable,llm=object())
        result=json.loads(handlers['rekindra_plan']({'project_id':'a'*32,'asset_ids':['b'*32],'intent':'dreamy','send_images':False}))
        self.assertFalse(result['ok']);self.assertIn('send_images',result['error']['message'])

    def test_unexpected_value_error_from_host_is_redacted(self):
        def unavailable():raise ValueError('sensitive-token')
        result=plugin.handlers.make_handlers(unavailable)['rekindra_inspect']({'folder':'D:/example'})
        self.assertNotIn('sensitive-token',result)


if __name__=='__main__':unittest.main()
