# Speed (post-freeze unit 3)

## Pass condition (written before the work)

A measured before and after on the same folder and the same model, with time and
call count per stage, recorded here. No quality gate may be lowered to get it:
the export gate, the palette and backdrop checks, the source checks and the
render used by `rekindra_preview` all stay as they were.

## What was measured

Both runs: `samples/demo-lighthouse`, the same prompt, provider zai, `glm-5.3`,
high reasoning, one run at a time, ending in a verified WebM export. Times come
from the Hermes event stream of each run (tool start to tool result); "model and
gateway" is the rest of the wall time.

| | Before (`c2a24d0`) | After (`016ad69`) |
|---|---|---|
| Run log | `logs/pf2-u2-glm53-c` | `logs/pf2-u3-after` |
| Wall time | 1811 s | 647 s |
| Cost | $0.8929 | $0.3882 |
| Tool batches (model round trips with tools) | 26 | 10 |
| Model and gateway time | 938 s | 453 s |
| Input tokens (cached) | 1,476,923 (1,324,480) | 508,924 (446,592) |
| Output tokens | 53,768 | 25,052 |
| Time before the first event | 88 s | 62 s |

Per stage, calls and summed time:

| Stage | Before | After |
|---|---|---|
| `rekindra_inspect` | 1 call, 0.3 s | 1 call, 0.2 s |
| `rekindra_recover` | 4 calls, 6.1 s | 1 call, 3.0 s |
| `rekindra_create_world` | 7 calls, 72.0 s (1 rejected) | 1 call, 9.1 s, preview included |
| `rekindra_revise_world` | 0 calls | 3 calls, 57.6 s, preview included |
| `rekindra_preview` | 5 calls, 127.1 s | 0 separate calls |
| `rekindra_export` | 1 call, 4.6 s | 1 call, 0.6 s |
| All Rekindra tools | 18 calls, 210 s | 7 calls, 70 s |
| `vision_analyze` (Hermes, not Rekindra) | 6 calls, 662 s, 2 timeouts | 1 call, 122 s, 1 timeout |

Disk waits are inside the tool times above; they were not measured separately.

The exported frames of the after run were reviewed: the striped lighthouse on
its rock, the sea, the headland and a sweeping beam are all there, and the
motion probe reports motion. The export gate behaved as before: one palette
warning was still open at the cycle cap and was exported with an
acknowledgment.

## What was cut

1. **One call recovers the whole folder.** `rekindra_recover` without `asset_id`
   recovers every asset through the same per-asset path. 4 calls became 1.
2. **Preview in the same call.** `rekindra_create_world` and
   `rekindra_revise_world` accept `preview: true` and return the same
   `rekindra_preview` result. 5 separate preview calls became 0.
3. **No repeated TGA decode.** Building a world reuses the recovered PNG after
   checking its hash, instead of decoding the TGA again on every call.
4. **No repeated stripe sampling.** The stripe check is memoized per expression
   text. Replaying the seven `rekindra_create_world` calls of the before run
   without a model went from 2.3 to 4.5 s each to 0.4 to 1.3 s each.

## What these numbers do and do not show

- Two live runs are not the same conversation. The model chose a different
  path in the after run (revisions instead of new worlds, one look at the
  picture instead of six), so the wall-time drop is larger than the plugin
  alone explains. The parts that are the plugin's doing: fewer round trips
  (26 to 10), Rekindra tool time (210 s to 70 s), and the model-free replay
  in item 4.
- The largest single cost is not Rekindra's. `vision_analyze` took 662 s of
  the before run, including two provider timeouts of over two minutes each,
  and 122 s of the after run for one call that timed out. That is the Hermes
  vision tool and the provider; nothing in this plugin can shorten it.
- A render still costs 10 to 20 s whether it is its own call or part of
  create or revise. That is the real browser render the export gate relies on
  and it was not shortened.
