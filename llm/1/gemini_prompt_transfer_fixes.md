# Gemini Implementation Prompt: Transfer Fixes

## Three Issues to Fix

### Issue 1: Stop Device Polling During Transfer

**Problem**: The device list auto-refresh (every 3 seconds) continues during transfer, creating noise in the logs.

**Solution**: Add an `is_transferring` flag to pause polling during transfers.

### Issue 2: Add Cancel Operation Button

**Problem**: No visible UI button to cancel an ongoing transfer.

**Solution**: Add a "Annuler" (Cancel) button that appears during transfer.

### Issue 3: Chunks Not Being Reassembled

**Problem**: Transfer succeeds but reassembly doesn't happen or files aren't moved to final destination.

**Investigation Points**:

- Check if `_parallel_reassembly_on_all_devices` is being called
- Check if `reassemble_via_adb_shell` is properly executing the script
- Check if the marker file `.reassembly_complete` is being created


---

## Implementation Details

### 1. Stop Polling During Transfer

#### Modify `src/main.py`:

**A. Add `is_transferring` flag (around line 310, in `__init__`):**

```python
# After: self.device_details = {}
self.is_transferring = False  # Flag to pause device polling during transfer
```

**B. Modify `_refresh_devices_background` to check flag (around line 624):**

```python
def _refresh_devices_background(self):
    """Refresh device list in background without blocking UI."""
    # Skip refresh if transfer is in progress
    if self.is_transferring:
        # Still schedule next refresh, but skip this one
        interval = getattr(self, "device_refresh_interval", 3000)
        self.master.after(interval, self._refresh_devices_background)
        return

    def refresh():
        try:
            devices = self.adb.get_devices_detailed()
            current_signature = set((d["id"], d["display_name"]) for d in devices)

            if current_signature != self.previous_device_ids:
                self.previous_device_ids = current_signature
                self.master.after(0, lambda: self._update_device_list(devices))
        except Exception as e:
            pass

    threading.Thread(target=refresh, daemon=True).start()

    interval = getattr(self, "device_refresh_interval", 3000)
    self.master.after(interval, self._refresh_devices_background)
```

**C. Set flag when transfer starts (in `run_multi_device_transfer`, around line 860):**

```python
def run_multi_device_transfer(self, source, target, devices):
    """Run transfer to multiple devices in parallel with per-device worker pools."""
    import time

    # Pause device polling during transfer
    self.is_transferring = True

    # Reset cancel flag
    with self.cancel_lock:
        self.cancel_requested = False
    # ... rest of the method
```

**D. Clear flag when transfer ends (in `run_multi_device_transfer`, around line 978, before re-enabling buttons):**

```python
        # Stop timer
        self.timer_running = False
        elapsed = time.time() - self.transfer_start_time
        self.logger.info(f"Durée totale: {int(elapsed//3600):02d}:{int((elapsed%3600)//60):02d}:{int(elapsed%60):02d}")

        # Resume device polling
        self.is_transferring = False

        # Re-enable buttons
        self.transfer_button.config(state=tk.NORMAL)
        self.settings_button.config(state=tk.NORMAL)
```

**IMPORTANT**: Also ensure the flag is cleared in all early return paths (cancellation, error, etc.)

---

### 2. Add Cancel Operation Button

#### Modify `src/main.py`:

**A. Create Cancel Button in `create_widgets` (around line 503, after transfer_button):**

```python
        # Transfer button
        self.transfer_button = tk.Button(self, text="Démarrer le Transfert", command=self.start_transfer_thread)
        self.transfer_button.pack(pady=10)

        # Cancel button (hidden by default)
        self.cancel_button = tk.Button(
            self,
            text="❌ Annuler l'opération",
            command=self._cancel_current_operation,
            bg="#FF5252",
            fg="white",
            font=("Arial", 10, "bold")
        )
        # Don't pack yet - will be shown during transfer
```

**B. Show cancel button when transfer starts (in `start_transfer_thread`, around line 837):**

```python
        self.save_config()

        self.transfer_button.config(state=tk.DISABLED)
        self.settings_button.config(state=tk.DISABLED)

        # Show cancel button
        self.cancel_button.pack(pady=5)
```

**C. Hide cancel button when transfer ends (in `run_multi_device_transfer`, around line 978):**

```python
        # Resume device polling
        self.is_transferring = False

        # Hide cancel button
        self.master.after(0, lambda: self.cancel_button.pack_forget())

        # Re-enable buttons
        self.transfer_button.config(state=tk.NORMAL)
        self.settings_button.config(state=tk.NORMAL)
```

**D. Add cancel method (new method, add after `run_multi_device_transfer`):**

```python
    def _cancel_current_operation(self):
        """Cancel the current transfer/reassembly operation."""
        confirm = messagebox.askyesno(
            "Confirmation",
            "Voulez-vous vraiment annuler l'opération en cours?\n\n"
            "Les fichiers déjà transférés resteront sur l'appareil."
        )

        if not confirm:
            return

        self.logger.warning("Annulation demandée par l'utilisateur...")

        with self.cancel_lock:
            self.cancel_requested = True

        # Cancel transfer manager
        if hasattr(self, 'transfer_manager') and self.transfer_manager:
            self.transfer_manager.cancel()

        # Cancel any active reassembly managers
        for device_id, mgr in self.current_reassembly_managers.items():
            mgr.cancel()
            self.logger.info(f"[{device_id}] Réassemblage annulé")
```

---

### 3. Fix Reassembly Not Running

**Investigation Required**: The reassembly flow is:

1. `run_multi_device_transfer` calls `_parallel_reassembly_on_all_devices`
2. This should call `ReassemblyManager.reassemble_via_adb_shell` (if `use_adb_shell_mode` is True)
3. The script creates `.reassembly_complete` marker when done
4. Files should be moved to `target_dir`

**Potential Issues**:

1. `_parallel_reassembly_on_all_devices` may not exist or has bugs
2. `use_adb_shell_mode` config may be False (using Termux instead)
3. The shell script may fail silently (no `unzip` command on device)
4. Move command may fail due to path escaping issues

**Add Debug Logging**:

In `_parallel_reassembly_on_all_devices` (or wherever it's defined), add logging:

```python
self.logger.info(f"[DEBUG] Starting reassembly on {len(successful_devices)} devices")
self.logger.info(f"[DEBUG] use_adb_shell_mode = {self.config.get('use_adb_shell_mode', True)}")
self.logger.info(f"[DEBUG] remote_temp_dir = {self.config.get('remote_temp_dir')}")
self.logger.info(f"[DEBUG] target_dir = {target}")
```

**Check if `_parallel_reassembly_on_all_devices` exists**: Look around line 950 in main.py and find this method. If it doesn't exist, that's the bug!

**Verify the config**: Check that `use_adb_shell_mode` is True in config.json. If it's False, the app tries to use Termux which requires user interaction.

---

## Files to Check/Modify

1. **`src/main.py`**:

   - Add `is_transferring` flag
   - Modify `_refresh_devices_background` to check flag
   - Add cancel button
   - Add `_cancel_current_operation` method
   - Find and fix `_parallel_reassembly_on_all_devices`

2. **`src/config.py`**: Verify `DEFAULT_USE_ADB_SHELL_MODE = True`

3. **`src/core/reassembly.py`**: Add more debug logging in `reassemble_via_adb_shell`

---

## Testing Steps

### Test 1: Polling Stops During Transfer

1. Start app, verify device list updates every few seconds (watch log)
2. Start a transfer
3. Verify NO "Recherche des appareils connectés" messages during transfer
4. After transfer completes, verify polling resumes

### Test 2: Cancel Button Works

1. Start a transfer
2. Verify red "❌ Annuler l'opération" button appears
3. Click it, confirm dialog
4. Verify transfer stops and summary shows
5. Verify button disappears and "Démarrer le Transfert" is re-enabled

### Test 3: Reassembly Runs

1. Transfer some files (mix of large and small)
2. Watch logs for:
   - "PHASE 2: Réassemblage parallèle..."
   - "Exécution du script de réassemblage..."
   - "Réassemblage terminé"
3. Check on device:
   - `/sdcard/transfer_temp/.reassembly_complete` file exists
   - Files are in the target directory (e.g., `/sdcard/Download/`)

---

## Priority Order

1. **Fix Issue 3 first** - Most critical, without this the app doesn't work properly
2. **Fix Issue 1** - Quick win, reduces noise
3. **Fix Issue 2** - Nice to have, improves UX
