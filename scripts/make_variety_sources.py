"""Original visual references for the renderer's contrasting-input acceptance study.

These are synthetic design studies, not recovered user files or model outputs.
Separate from the other developer's source-intake fixture assignment.
"""
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rekindra_core.png import encode_png
from rekindra_core.tga import Raster


def botanical(x, y):
    color = (237, 224, 197)
    # Branching stems and alternating broad, pointed leaves.
    for cx, base, height, phase in ((.27, .91, .73, 0), (.64, .95, .84, 1)):
        stem = cx + .055 * math.sin((base-y)*5+phase)
        if base-height < y < base and abs(x-stem) < .004:
            color = (91, 112, 54)
        for i in range(7):
            ly = base-.1-i*height/8
            side = 1 if (i+phase)%2 else -1
            lx = cx+.055*math.sin((base-ly)*5+phase)+side*.073
            dx, dy = x-lx, y-ly
            along = dx*.83-dy*side*.56
            across = dx*side*.56+dy*.83
            if (along/.105)**2+(across/.032)**2 < 1:
                color = (48+14*i, 86+12*i, 42+5*i)
                if abs(across)<.002:
                    color = (167, 177, 94)
    # Rust-red seed cluster, deliberately unlike ocean/sun geometry.
    for i in range(9):
        cx=.8+.024*math.sin(i*2.4); cy=.26+i*.022
        if ((x-cx)/.019)**2+((y-cy)/.013)**2<1:
            color=(155+6*(i%3), 55, 35)
    return color


def geometric(x, y):
    color = (20, 18, 43)
    if abs((x*16)%1-.5)<.013 or abs((y*12)%1-.5)<.013:
        color=(45, 43, 69)
    blocks=((.14,.23,.13,.57),(.32,.48,.16,.32),(.54,.15,.12,.65),(.73,.35,.15,.45))
    for i,(bx,by,bw,bh) in enumerate(blocks):
        if bx<x<bx+bw and by<y<by+bh:
            color=((236,76,142),(47,210,216),(248,190,69),(131,95,228))[i]
            if abs(((y-by)*24)%1-.5)<.15:
                color=(26,24,49)
    if .84<y<.86 and .1<x<.9:
        color=(239,218,164)
    return color


def main():
    for name, painter in [('botanical', botanical), ('geometric', geometric)]:
        out=ROOT/'.local/variety-study'/name
        out.mkdir(parents=True, exist_ok=True)
        w,h=640,480
        pixels=bytearray()
        for y in range(h):
            for x in range(w):
                pixels.extend((*painter(x/w,y/h),255))
        target=out/'reference.png'
        target.write_bytes(encode_png(Raster(w,h,bytes(pixels))))
        print(target)


if __name__=='__main__':
    main()
