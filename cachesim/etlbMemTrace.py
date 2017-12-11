#! /usr/bin/env python3
import sys
from etlb import ETLB

def test():
    etlb = ETLB()
    nLines = -1
    if len(sys.argv) > 1:
        nLines = int(sys.argv[1])
    skip = 0
    if len(sys.argv) > 2:
        skip = int(sys.argv[2])
    warmup = 0
    if len(sys.argv) > 3:
        warmup = int(sys.argv[3])
    counter = 0
    for i, line in enumerate(sys.stdin):
        if i >= skip:
            if i >= skip+warmup:
                counter += 1
            addr = int(line.split(' ')[-3])
            #print(line, i)
            etlb.access(addr, 'Write' in line, i >= skip + warmup)
        if i + 1 == skip + warmup + nLines and nLines != -1:
            break
    print("N:", counter)
    print("ETLB Hit, NIC %d, (%03f)"%(etlb.hit[0], etlb.hit[0]/(counter)*100))
    print("ETLB Hit, L1D %d, (%03f)"%(etlb.hit[2], etlb.hit[2]/(counter)*100))
    print("ETLB Hit, L2  %d, (%03f)"%(etlb.hit[3], etlb.hit[3]/(counter)*100))
    print("ETLB Miss,    %d, (%03f)"%(etlb.miss, etlb.miss/(counter)*100))
    print("Hub Hit, NIC %d, (%03f)"%(etlb.hub.hit[0], etlb.hub.hit[0]/(counter)*100))
    print("Hub Hit, L1  %d, (%03f)"%(etlb.hub.hit[2], etlb.hub.hit[2]/(counter)*100))
    print("Hub Hit, L2  %d, (%03f)"%(etlb.hub.hit[3], etlb.hub.hit[3]/(counter)*100))
    print("Hub Miss,    %d, (%03f)"%(etlb.hub.miss, etlb.hub.miss/(counter)*100))

    print("Time L1: %d, L2: %d, total: %d"%(etlb.cache.cycles, etlb.hub.cache.cycles, etlb.cache.cycles+etlb.hub.cache.cycles))
    print("Energy L1: %0.3f, L2: %0.3f, total: %0.3f"%(etlb.cache.energy, etlb.hub.cache.energy, etlb.cache.energy+etlb.hub.cache.energy))


if __name__ == '__main__':
    test()
                                    
