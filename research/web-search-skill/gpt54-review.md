[rebrowser-patches][frames._context] cannot get world, error: ProtocolError: Protocol error (Runtime.evaluate): Cannot find context with specified id
    at /home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/driver/package/lib/server/chromium/crConnection.js:116:57
    at new Promise (<anonymous>)
    at CRSession.send (/home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/driver/package/lib/server/chromium/crConnection.js:115:12)
    at CRSession.__re__getMainWorld (/home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/driver/package/lib/server/chromium/crConnection.js:266:20)
    at runNextTicks (node:internal/process/task_queues:65:5)
    at process.processImmediate (node:internal/timers:459:9)
    at async CRSession.__re__emitExecutionContext (/home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/driver/package/lib/server/chromium/crConnection.js:220:28)
    at async Frame.evaluateExpression (/home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/driver/package/lib/server/frames.js:645:21) {
  type: 'error',
  method: 'Runtime.evaluate',
  logs: undefined
}
==================================================
🔗 Oracle Stealth Bridge v4 (Camoufox + Chrome)
==================================================
[1/2] Bypassing Cloudflare with Camoufox...
   ✅ Authenticated (title: ChatGPT)
   📋 Extracted 25 cookies (3 CF-related)

[2/2] Launching Chrome CDP bridge on port 9222...
   ✅ Chrome authenticated: ChatGPT

==================================================
🔗 Oracle Bridge v4 READY
   CDP: localhost:9222
   Usage: ORACLE_REUSE_TAB=1 oracle --engine browser --remote-chrome localhost:9222 --prompt '...'
==================================================

🤖 Running Oracle...
⏰ Oracle timed out
Task was destroyed but it is pending!
task: <Task pending name='Task-10' coro=<Connection.run() running at /home/openclaw/camoufox-env/lib/python3.12/site-packages/rebrowser_playwright/_impl/_connection.py:281> wait_for=<Future pending cb=[Task.task_wakeup()]>>
Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7f6007265760>
Traceback (most recent call last):
  File "/usr/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
    self.close()
  File "/usr/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
    proto.pipe.close()
  File "/usr/lib/python3.12/asyncio/unix_events.py", line 767, in close
    self.write_eof()
  File "/usr/lib/python3.12/asyncio/unix_events.py", line 753, in write_eof
    self._loop.call_soon(self._call_connection_lost, None)
  File "/usr/lib/python3.12/asyncio/base_events.py", line 795, in call_soon
    self._check_closed()
  File "/usr/lib/python3.12/asyncio/base_events.py", line 541, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed
