#! /usr/bin/env python
import math
import sys

class Cache:
    

    def __init__(self, size=0x8000, associativity=8, cacheLine=64, child=None):
        """Simple associative cache.

        Parameters
        ----------

        size (int):
            Cache size in bytes. (Default 0x8000 (32 kB))
        associtivilty (int):
            Number of ways for an associative cache, -1 for fully associative.
        cacheLine (int):
            Number of bytes per cache line, determiines the number of offset bits.
        child (Cache):
            The next level of cache, default is None, which means DRAM (not simulated).
        """
        self.size = size
        self.associativity = associativity
        self.cacheLine = cacheLine
        self.child = child

        self.nLines = self.size // self.cacheLine

        if self.associativity == -1:
            self.associativity = self.nLines

        self.nSets = self.nLines // self.associativity

        self.offsetBits = int(math.ceil(math.log2(self.cacheLine)))
        self.setBits = int(math.ceil(math.log2(self.nSets)))
        self.tagBits = 48 - self.setBits - self.offsetBits

        self.freeList = [list(range(self.associativity)) for i in range(self.nSets)]

        self.counter = 0
        self.lastAccess = [[0]*self.associativity for i in range(self.nSets)]
        self.tags = [[0]*self.associativity for i in range(self.nSets)]

        self.tagTime = 1
        self.accessTime = 3

        self.tagEnergy = 0.000760707
        self.accessEnergy = 0.0111033

        self.hit = 0
        self.miss = 0
        self.cycles = 0
        self.energy = 0.
        
    def access(self, address, write=False, count=True, countTime=None, countEnergy=None):
        """Access a given address.

        Parameters
        ----------
        address (int):
            The address which is accessed.
        write (bool):
            True if the access is a write, False for a read (default read).
            This parameter is unused currently, but maintained for future use.
        count (bool):
            Whether hit/miss rate should be counted (default is True).
        """
        if countTime is None:
            countTime = count

        if countEnergy is None:
            countEnergy = count

        setIndex = (address >> self.offsetBits)  % self.nSets

        tag = address >> (self.setBits + self.offsetBits)

        if countTime:
            self.cycles += self.tagTime
        if countEnergy:
            self.energy += self.tagEnergy

        if tag in self.tags[setIndex]:
            if count:
                self.hit += 1
            way = list(self.tags[setIndex]).index(tag)
        
        else:
            if count:
                self.miss += 1
            if self.child is not None:
                self.child.access(address, write, count)

            if len(self.freeList[setIndex]) == 0:
                evictedTag = self.evict(setIndex, countEnergy=countEnergy)
            way = self.freeList[setIndex].pop()
            self.tags[setIndex][way] = tag
        
        self.accessDirect(setIndex, way, write, countTime, countEnergy)
    
    def accessDirect(self, setIndex, way, write=False, countTime=True, countEnergy=True):
        if countTime:
            self.cycles += self.accessTime
        if countEnergy:
            self.energy += self.accessEnergy
            if write:
                self.energy += self.accessEnergy
        if way in self.freeList[setIndex]:
            self.freeList[setIndex].remove(way)
        self.counter += 1
        self.lastAccess[setIndex][way] = self.counter

    def evict(self, setNumber, way=None, countEnergy=True):
        """Evict (i.e. add to the free list) a cache line.
        
        If `way` is None, LRU replacement policy is used among occupied lines.
        If `way` is an integer, that integer is added to the free list.
        """
        if way is not None:
            if way not in self.freeList[setNumber]:
                self.freeList[setNumber].append(way)
                if self.child is not None:
                    addr = (self.tags[setNumber][way] << self.setBits) + setNumber
                    self.child.access(addr << self.offsetBits, write=True, count=False, countEnergy=countEnergy)
        else:
            way = self.selectEviction(setNumber)
            if way not in self.freeList[setNumber]:
                self.freeList[setNumber].append(way)
                if self.child is not None:
                    addr = (self.tags[setNumber][way] << self.setBits) + setNumber
                    self.child.access(addr << self.offsetBits, write=True, count=False, countEnergy=countEnergy)
        if countEnergy:
            self.energy += self.tagEnergy
        return self.tags[setNumber][way]

    def selectEviction(self, setNumber):
        way = 0
        minAccess = self.lastAccess[setNumber][0]
        for i,acc in enumerate(self.lastAccess[setNumber]):
            if i not in self.freeList[setNumber] and self.lastAccess[setNumber][i] < minAccess:
                way = i
                minAccess = self.lastAccess[setNumber][i]
        return way

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
        if line.startswith('#eof'):
            break
        if i >= skip:
            addr = int(line.split(' ')[1], 16)
            L1.access(addr, line[0]=='W', i >= skip + warmup)
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
