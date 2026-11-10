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

(filled in after the runs)
