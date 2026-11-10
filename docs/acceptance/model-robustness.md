# Model robustness (post-freeze unit 2)

## Pass condition (written before the work)

1. Every rejection a model can trigger through a tool call names what was
   wrong, what to pass instead, and the valid values or where they come from.
   Checked by `tests/test_model_robustness.py`: one test per rejection class,
   asserting the offending value or key, and the valid set, appear in the
   message.
2. A tool call with an argument the tool does not accept is refused, and the
   refusal lists the accepted arguments. Same test file.
3. Full Python and Node suites green, plugin validator green.
4. One lighthouse take on `glm-5.3` (high reasoning) and one on the cheapest
   tool-capable z.ai model. In both transcripts, every Rekindra tool error is
   followed by a successful call of the same tool on the very next call of
   that tool (recovered in one call). Anything the weak model still gets
   wrong is listed below, not hidden.
5. README "Tested models" states only the models and runs listed here.

## Results

Both runs: lighthouse folder (`samples/demo-lighthouse`), provider zai, high
reasoning, plugin at `c2a24d0`, one run at a time.

| | glm-5.3 | glm-4.5-flash (cheapest tool-capable z.ai model tried) |
|---|---|---|
| Run log | `logs/pf2-u2-glm53-c` | `logs/pf2-u2-glm45flash` |
| Wall time | 1811 s | 471 s |
| Cost | $0.8929 | $0.1879 |
| Rekindra rejections | 1 | 0 |
| Recovered in one call | 1 of 1 | n/a |
| Reached export | yes, WebM verified | yes |

**Pass: every Rekindra tool error in both runs was recovered from in one call.**

glm-5.3
- One rejection: a loft ring wound the opposite way from an earlier section.
  The next `rekindra_create_world` call succeeded. The message it got was the
  bare "consistent winding" text; it now names the section, the point, the edge
  and the fix (`tests/test_lofts.py`).
- Not Rekindra: one Hermes-side `tool_call calls[0] requires a 'name'` error,
  and two `vision_analyze` provider timeouts (149 s and 121 s). The agent
  carried on after each.
- The exported contact sheet was reviewed and shows the lighthouse scene.

glm-4.5-flash: where the weak model still fails
- No schema or argument rejections at all, and it walked the gate correctly:
  export was blocked on two palette warnings, it revised, previewed again and
  exported with acknowledgments.
- **The picture is not usable.** The rendered frames are an empty pink
  gradient with no visible lighthouse, and the browser check logged
  "No visual motion detected with the camera fixed".
- It acknowledged the palette drift instead of fixing it, and its one revision
  made no visible difference.
- Rekindra has no gate that refuses an empty or motionless frame, so this run
  passed every check the plugin makes. That is a gap in the plugin, not in the
  model's tool use, and it is left as an open decision.
