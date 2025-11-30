# Terminal Reconnection Test

## Bug Fixed
**Issue**: WebSocket connection fails after page reload, requiring backend restart.

**Root Cause**: Event loop reference captured at connection time becomes stale after reload, causing race condition between thread callbacks and new event loop.

**Files Modified**:
- `code_map/api/terminal.py` - Added loop validation and improved cleanup order
- `code_map/terminal/pty_shell.py` - Added thread join with timeout
- `frontend/src/components/RemoteTerminalView.tsx` - Added isCleanedUp flag for React Strict Mode

## Manual Testing Steps

### 1. Start Backend
```bash
cd /home/jesusramos/Workspace/ATLAS
python3 -m code_map.cli run --root .
```

### 2. Open Frontend
```bash
cd /home/jesusramos/Workspace/ATLAS/frontend
npm run dev
```

### 3. Test Normal Operation
1. Navigate to terminal view
2. Verify terminal connects successfully
3. Type commands (e.g., `ls`, `pwd`, `echo "test"`)
4. Verify output appears correctly

### 4. Test Single Reload
1. Press F5 (or Ctrl+R) to reload page
2. Wait for reconnection
3. Verify terminal connects successfully
4. Type commands again
5. Verify output appears correctly

### 5. Test Rapid Reload
1. Press F5 multiple times rapidly (3-4 times)
2. Wait for final connection
3. Verify terminal connects successfully
4. Type commands
5. Verify output appears correctly

### 6. Test Multiple Tabs
1. Open terminal in tab 1
2. Open terminal in tab 2
3. Type in both terminals
4. Close tab 1
5. Verify tab 2 still works
6. Reload tab 2
7. Verify it reconnects successfully

### 7. Monitor Backend Logs
Watch for these log messages:
- ✅ "Terminal WebSocket connection accepted"
- ✅ "Shell spawned successfully: PID=..."
- ✅ "Cleaning up terminal session"
- ✅ "Waiting for read thread to exit..."
- ✅ "Read thread exited cleanly"
- ⚠️ "Attempted to queue output to closed event loop" (should NOT appear frequently)
- ❌ "Error queueing output" (should NOT appear)

### 8. Check for Zombie Processes
```bash
# Before test
ps aux | grep -E "bash|sh" | wc -l

# After multiple reconnects
ps aux | grep -E "bash|sh" | wc -l

# Should be similar (no accumulation of zombie shells)
```

## Expected Behavior

### Before Fix
- ❌ First connection works
- ❌ Reload causes connection failure
- ❌ Backend logs show "Error queueing output"
- ❌ Must restart backend to fix

### After Fix
- ✅ First connection works
- ✅ Reload works correctly
- ✅ Multiple rapid reloads work
- ✅ Clean thread termination
- ✅ No zombie processes
- ✅ No backend restart needed

## Technical Details

### Fix 1: Event Loop Validation
**File**: `code_map/api/terminal.py:61-65`

```python
if loop.is_running():
    loop.call_soon_threadsafe(output_queue.put_nowait, data)
else:
    logger.warning("Attempted to queue output to closed event loop")
```

Prevents queueing to stale event loop after reconnection.

### Fix 2: Improved Cleanup Order
**File**: `code_map/api/terminal.py:142-146`

```python
# 1. Stop the shell first (sets running = False)
shell.close()

# 2. Wait briefly for read thread to exit cleanly
await asyncio.sleep(0.1)

# 3. Cancel the read task
read_task.cancel()
```

Ensures proper shutdown sequence to avoid race conditions.

### Fix 3: Thread Join with Timeout
**File**: `code_map/terminal/pty_shell.py:207-214`

```python
if self.read_thread is not None and self.read_thread.is_alive():
    logger.debug("Waiting for read thread to exit...")
    self.read_thread.join(timeout=0.5)
    if self.read_thread.is_alive():
        logger.warning("Read thread did not exit cleanly within timeout")
```

Explicitly waits for thread termination before cleaning up resources.

### Fix 4: React Strict Mode Handling
**File**: `frontend/src/main.tsx:16-23`

```typescript
// Note: StrictMode disabled temporarily to fix WebSocket connection issues
// StrictMode causes double-mount in development which closes WebSocket before connection completes
// This is not an issue in production builds where StrictMode effects don't apply
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>
);
```

React Strict Mode was disabled to prevent double-mount issues with WebSockets.

### Fix 5: TanStack Query + Zustand Update Issue (ACTUAL ROOT CAUSE)
**File**: `frontend/src/components/RemoteTerminalView.tsx:26,138-144`

```typescript
const isInitializedRef = useRef(false);

// Connect to WebSocket
useEffect(() => {
  if (!xtermRef.current) {
    console.log("[WS] Effect skipped: terminal not ready");
    return;
  }

  const terminal = xtermRef.current;
  const wsUrl = wsBaseUrl.replace("http://", "ws://").replace("https://", "wss://");

  // Skip if already initialized and WebSocket is active
  // This prevents reconnection when App.tsx updates Zustand from useSettingsQuery
  if (isInitializedRef.current) {
    const currentSocket = wsRef.current;
    if (currentSocket && (currentSocket.readyState === WebSocket.OPEN || currentSocket.readyState === WebSocket.CONNECTING)) {
      console.log(`[WS] Already initialized with active socket (state=${currentSocket.readyState}), skipping reconnect`);
      return;
    }
  }

  isInitializedRef.current = true;
  console.log(`[WS] Effect running, creating WebSocket to ${wsUrl}/api/terminal/ws`);
  // ... rest of WebSocket creation
}, [wsBaseUrl]);
```

**The Real Problem**:
1. Page loads → `useSettingsQuery()` starts fetching (returns `data: undefined` initially)
2. RemoteTerminalView mounts → Reads `wsBaseUrl` from Zustand (persisted from localStorage)
3. useEffect runs, creates WebSocket (state=CONNECTING)
4. `useSettingsQuery()` completes → Returns `{ data: { backend_url: "..." } }`
5. App.tsx useEffect detects change → Calls `setBackendUrl()` → Updates Zustand store
6. Zustand update triggers RemoteTerminalView re-render → useEffect dependency changes
7. useEffect cleanup runs → Closes WebSocket while state=0 (CONNECTING, code=1006)
8. useEffect re-runs, creates new WebSocket

**The Fix**:
- Track initialization state with `isInitializedRef`
- After first WebSocket creation, set `isInitializedRef.current = true`
- On subsequent useEffect runs (from App.tsx updating Zustand), check if already initialized
- If initialized and socket is OPEN or CONNECTING → skip reconnect
- This prevents closing healthy connections when App.tsx syncs settings to Zustand

## Success Criteria

- [ ] Terminal connects on first load
- [ ] Single page reload reconnects successfully
- [ ] Rapid reloads (3-4x) work correctly
- [ ] Multiple concurrent tabs work independently
- [ ] Backend logs show clean cleanup
- [ ] No zombie shell processes accumulate
- [ ] No "Error queueing output" messages in logs
