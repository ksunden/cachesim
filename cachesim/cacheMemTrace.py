#! /usr/bin/env python3 
from cache import Cache
import sys

def test():
    L2 = Cache(size=0x100000, associativity=16)
    L2.accessTime = 8
    L2.tagTime = 3
    L2.accessEnergy = 0.137789
    L2.tagEnergy = 0.00538836
    L1 = Cache(size=0x8000, child=L2)
    nLines = -1
    if len(sys.argv) > 1:
        nLines = int(sys.argv[1])
    skip = 0
    if len(sys.argv) > 2:
        skip = int(sys.argv[2])
    warmup = 0
    if len(sys.argv) > 3:
        warmup = int(sys.argv[3])
    for i, line in enumerate(sys.stdin):
        if i >= skip:
            addr = int(line.split(' ')[-3])
            L1.access(addr, 'Write' in line, i >= skip + warmup)
        if i + 1 == skip + warmup + nLines and nLines != -1:
            break
    print("N:", L1.counter - warmup)
    print("L1 hit:  %d (%0.3f)"%(L1.hit, L1.hit/(L1.counter-warmup)*100))
    print("L1 miss: %d (%0.3f)"%(L1.miss, L1.miss/(L1.counter-warmup)*100))
    print("L2 hit:  %d (%0.3f)"%(L2.hit, L2.hit/(L1.counter-warmup)*100))
    print("L2 miss: %d (%0.3f)"%(L2.miss, L2.miss/(L1.counter-warmup)*100))
    print("Time L1: %d, L2: %d, total: %d"%(L1.cycles, L2.cycles, L1.cycles+L2.cycles))
    print("Energy L1: %0.3f, L2: %0.3f, total: %0.3f"%(L1.energy, L2.energy, L1.energy+L2.energy))

if __name__ == '__main__':
    test()
                                       
