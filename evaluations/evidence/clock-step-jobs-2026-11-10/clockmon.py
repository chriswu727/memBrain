"""Log wall-minus-monotonic offset changes > 1 ms, sampled every 20 ms."""
import sys, time
out = open(sys.argv[1], 'a', buffering=1)
dur = float(sys.argv[2])
end = time.monotonic() + dur
prev = time.time() - time.monotonic()
out.write(f"start wall={time.time():.6f} offset={prev:.6f}\n")
n = 0
while time.monotonic() < end:
    time.sleep(0.02)
    off = time.time() - time.monotonic()
    d = off - prev
    if abs(d) > 0.001:
        out.write(f"step wall={time.time():.6f} delta={d*1000:+.3f}ms\n")
        n += 1
    prev = off
out.write(f"end wall={time.time():.6f} offset={prev:.6f} steps={n}\n")
