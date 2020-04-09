# This file is executed on every boot (including wake-boot from deepsleep)
import machine
import esp
import gc
esp.osdebug(None)
machine.freq(160000000)
gc.collect()
