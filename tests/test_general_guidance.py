import json
from pathlib import Path
import re
import unittest

from test_plugin import plugin


ROOT = Path(__file__).resolve().parents[1]
SCENE_WORDS = re.compile(r'\b(lighthouses?|boats?|hulls?|masts?|keeper)\b', re.I)
RECIPE_TOKENS = ('320*v', '1F5888', '5A6480', 'B89A78', 'pointed-bow', 'headland', 'check_demo_scene')
PRINCIPLES = ('large surfaces', 'big enough to read', 'never show its ends', 'silhouette', 'proportions', 'palette', 'close the geometry', 'frame size')


class GeneralGuidanceTests(unittest.TestCase):
    def agent_text(self):
        return json.dumps(plugin.schemas.SCHEMAS)

    def test_tool_guidance_names_no_single_scene(self):
        text = self.agent_text()
        self.assertEqual(SCENE_WORDS.findall(text), [])
        for token in RECIPE_TOKENS:
            self.assertNotIn(token, text)

    def test_tool_guidance_teaches_the_general_principles(self):
        text = plugin.schemas.SCHEMAS['rekindra_create_world']['description'].lower()
        for principle in PRINCIPLES:
            self.assertIn(principle, text)

    def test_authoring_doc_carries_no_scene_recipe(self):
        text = (ROOT / 'docs' / 'world-authoring.md').read_text(encoding='utf-8')
        for token in RECIPE_TOKENS:
            self.assertNotIn(token, text)
        lowered = text.lower()
        for principle in PRINCIPLES:
            self.assertIn(principle, lowered)
