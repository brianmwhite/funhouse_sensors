import time
import board
import analogio

photocell = analogio.AnalogIn(board.A0)

while True:
    print(photocell.value)
    time.sleep(1)
