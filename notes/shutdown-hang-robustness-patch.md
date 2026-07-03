# Robustness patch — bound terminateWorkerThread (workerEvents.ts)

## Problem
`await Thread.terminate(worker)` (workerEvents.ts:134) can hang indefinitely: Thread.terminate →
worker.terminate() (Node native, @chainsafe/threads 1.11.3 spawn.js:96). worker.terminate() cannot
preempt a worker blocked in a synchronous native (napi) call — so the intended retryCount×retryMs
(3×1s) bound is unreachable because only the *termination event* wait is raced (line 135), not the
terminate() call itself. Result: ~5min hang until docker SIGKILL.

## Fix (minimal, robustness): race the terminate() CALL against the timeout too
```ts
export async function terminateWorkerThread({worker, retryMs, retryCount, logger}: {...}): Promise<void> {
  const terminated = new Promise((resolve) => {
    Thread.events(worker).subscribe((event) => {
      if (event.type === "termination") resolve(true);
    });
  });

  for (let i = 0; i < retryCount; i++) {
    // worker.terminate() can hang if the worker is stuck in a blocking native call (V8 tears down
    // only at a JS safepoint). Race BOTH the terminate() call and the termination event against the
    // timeout so main-thread shutdown is bounded to retryCount*retryMs regardless.
    const result = await Promise.race([
      Thread.terminate(worker).then(() => terminated),
      sleep(retryMs).then(() => false),
    ]);
    if (result) return;
    logger?.warn("Worker thread failed to terminate, retrying...");
  }
  throw new Error(`Worker thread failed to terminate in ${retryCount * retryMs}ms.`);
}
```
Open question for Nico/PR: on final failure, throw (current behavior, now reachable) vs log-error +
let outer shutdown continue to process.exit(). Throw currently propagates to
networkCoreWorkerHandler.close():174 — verify it doesn't abort the rest of the node close sequence.

## Real root cause (separate, upstream)
Native call in @chainsafe/libp2p-quic (quinn) blocking worker.terminate(). See BACKLOG + probe data.
