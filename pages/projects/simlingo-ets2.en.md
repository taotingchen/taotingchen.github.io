## Goal

SimLingo is a vision-language-action model built on InternVL2-1B: a 24-layer vision transformer, the Qwen2-0.5B language model, and LoRA adapters. I fine-tuned it to drive a truck in Euro Truck Simulator 2 from screen captures alone.

Out of the box one frame took 691 ms, which is far too slow to steer with. The target was 25 ms per frame (40 FPS) on one NVIDIA RTX 5060 Ti with 16 GB of memory.

## What worked

Each row adds one change on top of the previous ones.

| Change | Latency | Speedup |
|---|---|---|
| Original pipeline | 691 ms | 1.0× |
| Decode only the driving output, skip language generation | 95.7 ms | 7.2× |
| Scaled-dot-product attention in the vision transformer | 75.1 ms | 9.2× |
| The same in the language model | 71.4 ms | 9.7× |
| Merge the LoRA weights into the base model | 62.3 ms | 11.1× |
| fp16 instead of bf16 | 62.2 ms | 11.1× |
| `torch.compile` in default mode | 56.9 ms | 12.1× |

{{chart}}

The largest gain was not a low-level optimization. The model was generating a sentence of explanation on every frame, and driving does not need it.

## What did not help

- **INT8 quantization.** Weight-only INT8 measured 78.6 ms without compilation and 64.7 ms with it, both slower than fp16. The weights are converted back to fp16 before every matrix multiply, so the conversion is pure overhead.
- **FP8.** The GPU's math library does not support it on this card yet.
- **Other `torch.compile` modes.** `reduce-overhead` and `max-autotune` both made the vision transformer about twice as slow.
- **ONNX Runtime and TensorRT.** The exported graph loses the fast attention path, so the vision transformer took about 56 ms against 38 ms in PyTorch.
- **A second GPU.** Putting the vision transformer and the language model on separate cards measured 66.7 ms against 62.2 ms on one card. The two stages run one after the other, so splitting them only adds transfer time.

## Two mistakes worth recording

My first dual-GPU measurement said 37.9 ms. It was wrong: the timer only covered the first GPU and missed the work on the second. Timing the whole pipeline gave 66.7 ms.

For a while `torch.compile` gave no speedup at all. A missing system package, `libpython3.12-dev`, stopped the compiler from building its launcher, and every call quietly fell back to the slow path with no error.

## Where the time goes now

In the best configuration the vision transformer takes about 38 ms and the language model about 25 ms, with roughly 6 ms of image preprocessing on the CPU. The vision transformer is the bottleneck.

## Limits and next steps

The 25 ms target has not been reached. 56.9 ms is about 17 frames per second.

These numbers measure latency only. I have not yet measured how the changes affect driving quality in closed loop, and that is the next thing to do. After that: a fused kernel for the vision transformer's MLP layers, the same code on a GPU with more compute units, and distilling the model to fewer layers.
