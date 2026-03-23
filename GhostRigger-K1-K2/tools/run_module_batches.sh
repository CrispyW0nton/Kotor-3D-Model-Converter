#!/bin/bash
# Run module batch renderer in small subprocess chunks to avoid OOM
# Each chunk processes --max N models and exits, then we restart

cd /home/user/webapp/GhostRigger-K1-K2
LOGFILE="logs/batch_modules_chunked.log"
echo "=== Module chunked batch started $(date) ===" | tee -a "$LOGFILE"

BATCH_SIZE=200

count_modules() {
    k2=$(ls audit_output/batch_render/renders/ 2>/dev/null | grep -E "^K2_[0-9]{3}.*_front\.png$" | wc -l)
    k1=$(ls audit_output/batch_render/renders/ 2>/dev/null | grep -E "^K1_m[0-9]{2}.*_front\.png$" | wc -l)
    echo $((k2 + k1))
}

rendered_before=$(ls audit_output/batch_render/renders/ 2>/dev/null | grep "_front\.png$" | wc -l)
echo "Front renders at start: $rendered_before" | tee -a "$LOGFILE"

chunk=1
while true; do
    echo "" | tee -a "$LOGFILE"
    echo "--- Chunk $chunk (size=$BATCH_SIZE) --- $(date)" | tee -a "$LOGFILE"
    
    # Count module renders
    total_mods=$(count_modules)
    echo "  Current module renders: $total_mods / 3296" | tee -a "$LOGFILE"
    
    if [ "$total_mods" -ge 3296 ]; then
        echo "All module models rendered!" | tee -a "$LOGFILE"
        break
    fi
    
    # Run batch - it will auto-resume via skip logic
    timeout 350 python3 tools/batch_modules.py --render-size 128 --max $BATCH_SIZE >> "$LOGFILE" 2>&1
    EXIT_CODE=$?
    echo "  Exit code: $EXIT_CODE" | tee -a "$LOGFILE"
    
    # If killed (OOM = exit 137) or error, wait for memory to settle
    if [ "$EXIT_CODE" -eq 137 ] || [ "$EXIT_CODE" -eq 1 ]; then
        echo "  [WARNING] Process failed/killed, waiting 10s..." | tee -a "$LOGFILE"
        sleep 10
    fi
    
    chunk=$((chunk + 1))
    
    # Safety: max 30 chunks (30 * 200 = 6000 models - more than enough)
    if [ "$chunk" -gt 30 ]; then
        echo "Max chunks reached" | tee -a "$LOGFILE"
        break
    fi
done

echo "" | tee -a "$LOGFILE"
echo "=== Module chunked batch complete $(date) ===" | tee -a "$LOGFILE"
# Final count
total_mods=$(count_modules)
echo "Final module render count: $total_mods / 3296" | tee -a "$LOGFILE"
