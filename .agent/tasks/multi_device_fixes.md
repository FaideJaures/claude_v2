# Multi-Device Transfer Fixes - REWRITE

**Created**: 2026-01-06 23:47
**Rewritten**: 2026-01-07 01:15
**Status**: ✅ UNIFIED TRANSFER LOGIC IMPLEMENTED

## Root Cause Found

The original code had **TWO SEPARATE CODE PATHS**:

1. **Standard mode** → Used `run_multi_device_transfer()` for multiple devices
2. **Prepared folder mode** → ONLY transferred to `devices[0]` and ignored all other devices!

```python
# OLD BROKEN CODE:
if use_transfer_folder:
    # This ONLY transferred to devices[0]!
    success = self.transfer_manager.transfer_from_prepared_folder(transfer_folder, target, device_id)
else:
    if len(devices) == 1:
        # single device
    else:
        self.run_multi_device_transfer(...)  # Multi-device path
```

When user had 2 devices and used prepared folder mode, the second device was completely ignored!

---

## Solution: Unified Transfer Logic

Rewrote `start_transfer_thread` with a **single unified transfer function** that:

1. Works for **both single and multiple devices**
2. Works for **both standard and prepared folder modes**
3. Uses `ThreadPoolExecutor` to run **all device transfers in parallel**
4. Each device gets its own `TransferManager` instance
5. Subsidiaries are also transferred in parallel to all successful devices

### New Code Structure:

```python
def run_transfer():
    """UNIFIED TRANSFER LOGIC"""
    
    def transfer_to_device(device_id):
        """Transfer to a single device - used by all devices in parallel."""
        device_transfer_mgr = TransferManager(self.config, self.logger)
        
        if use_transfer_folder:
            return device_transfer_mgr.transfer_from_prepared_folder(...)
        else:
            return device_transfer_mgr.start_transfer_parallel(...)
    
    # Execute ALL devices in parallel
    with ThreadPoolExecutor(max_workers=len(devices)) as executor:
        futures = {
            executor.submit(transfer_to_device, device_id): device_id 
            for device_id in devices
        }
        
        for future in as_completed(futures):
            device_id, success = future.result()
            # Track results...
```

---

## What Changed

### File: `src/main.py`

**Removed complexity:**
- No more separate `run_multi_device_transfer()` for new transfers
- No more conditional branching based on device count
- No more `devices[0]` assumption in prepared folder mode

**Added:**
- Unified `run_transfer()` function that handles ALL cases
- True parallel execution for all devices from the start
- Per-device `TransferManager` instances (each has its own ADB wrapper)
- Parallel subsidiary transfer to all successful devices

---

## Expected Behavior Now

When you run transfer with 2 devices (prepared folder mode):

```
[01:15:00] === TRANSFERT UNIFIÉ: 2 appareil(s) ===
[01:15:00] Mode: Dossier préparé
[01:15:00] Source: C:\...\RGPL2024_for_transfer
[01:15:00] 🔀 Lancement de 2 transfert(s) parallèle(s)...
[01:15:00] ✓ Tous les threads lancés
[01:15:00] [R8YW50DR1WK] ⏱️ Démarrage thread à T+0.000s
[01:15:00] [R9ZY40TL9BV] ⏱️ Démarrage thread à T+0.000s  <-- BOTH start now!
[01:15:00] [R8YW50DR1WK] Transfert depuis dossier préparé...
[01:15:00] [R9ZY40TL9BV] Transfert depuis dossier préparé...
... (interleaved logs from both devices)
[01:17:30] [R8YW50DR1WK] ✅ Terminé en 150.0s
[01:17:35] [R9ZY40TL9BV] ✅ Terminé en 155.0s
[01:17:35] === RÉSUMÉ ===
[01:17:35] Durée totale: 02:35
[01:17:35] Appareils: 2/2 réussis
```

---

## Previous Optimizations (Still Applied)

1. **Batched mkdir** - All directories created in single ADB call
2. **Parallel bundle transfer** - Bundles in ThreadPoolExecutor
3. **Configurable unlock delays** - 50% faster device unlock
4. **Skip resume check option** - For faster fresh transfers
5. **`run_shell_batch()`** - Batch multiple shell commands

---

## Next Steps

1. **Test the unified transfer** with 2+ devices
2. If USB bandwidth is still a bottleneck, consider:
   - Using WiFi for one device while USB for another
   - Staggering device transfers slightly
   - Implementing bandwidth monitoring

---

## Note on `run_multi_device_transfer()`

The old `run_multi_device_transfer()` method is still in the code but is **no longer called by `start_transfer_thread()`**. It can be removed in a future cleanup, or kept as a backup/reference.
