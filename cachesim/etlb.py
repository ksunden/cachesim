#! /usr/bin/env python
import math
import sys
from .hub import Hub
from .cache import Cache

class ETLB:
    

    def __init__(self, nLines=64, associativity=8, pageSize=0x1000, cache=None, hub=None):
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
            The next level of cache, must be a hub for etlb, default is None, which means default Hub.
        """
        self.nLines = nLines
        self.associativity = associativity
        self.hub = hub
        self.cache = cache

        if self.associativity == -1:
            self.associativity = self.nLines

        if self.hub is None:
            self.hub = Hub(associativity=self.associativity, pageSize=self.pageSize)
        if self.cache is None:
            self.cache = Cache(size=0x8000, associativity=16)

        self.cacheLine = self.cache.cacheLine

        self.nSets = self.nLines // self.associativity

        self.offsetBits = int(math.ceil(math.log2(self.cacheLine)))
        self.pageBits = int(math.ceil(math.log2(self.pageSize))) - self.offsetBits
        self.setBits = int(math.ceil(math.log2(self.nSets)))
        self.tagBits = 48 - self.setBits - self.pageBits - self.offsetBits

        self.freeList = [list(range(self.associativity)) for i in range(self.nSets)]

        self.counter = 0
        self.entries = [[ETLBEntry(self.pageSize, self.cacheLine) for i in range(self.associativity)] for j in range(self.nSets)]

        self.hit = [0,0,0,0] #DRAM,L1I,L1D,L2  Note: L1 is actually a unified cache at present, for forward compatability if separate caches are ever implemented
        self.miss = 0
        
    def access(self, address, write=False, count=True):
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
        offset = address % self.cacheLine
        setIndex = (address >> self.offsetBits)  % self.nSets
        pageIndex = (address >> (self.offsetBits + self.setBits)) % (1 << self.pageBits)


        tag = address >> (self.setBits + self.pageBits + self.offsetBits)

        #eTLB Hit
        hit = False
        for entry in self.entries[setIndex]:
            if entry.valid and entry.vtag == tag:
                hit = True
                loc = entry.location[pageIndex]
                way = entry.way[pageIndex]
                if count:
                    self.hit[loc] += 1
                # Not in cache
                if loc == 0:
                    #Access to DRAM not simulated at ADDR (entry.paddr << self.offsetBits) + offset
                    #TODO: Evict from L1
                    #TODO: Update way information (gather from where evicted)
                    entry.loc[pageIndex] = 2 #L1D (unified L1)
                # In L1 (data and instruction caches unified, this needs to be split if those are split)
                elif loc == 1 or loc == 2:
                    cacheSetIndex = (address >> self.offsetBits) % self.cache.nSets
                    self.cache.accessDirect(cacheSetIndex, way)
                # In L2
                elif loc == 3:
                    #TODO PAddr usage
                    cacheSetIndex = (address >> self.offsetBits) % self.hub.cache.nSets
                    self.hub.cache.accessDirect(cacheSetIndex, way)
                    #TODO: Evict from L1
                    #TODO: Update way information (gather from where evicted)
                    entry.loc[pageIndex] = 2 #L1D (unified L1)
                # Invalid location
                else:
                    raise ValueError("Location in CLT is invalid, expected 2 bit int, got %d"%loc)
                break
        
        #eTLB Miss
        if not hit:
            if count:
                self.miss += 1
            pass

            if len(self.freeList[setIndex]) == 0:
                self.evict(setIndex)
            way = self.freeList[setIndex].pop()
            self.tags[setIndex][way] = tag
        
        
        self.counter += 1
        self.lastAccess[setIndex][way] = self.counter

    def evict(self, setNumber, way=None):
        """Evict (i.e. add to the free list) a cache line.
        
        If `way` is None, LRU replacement policy is used among occupied lines.
        If `way` is an integer, that integer is added to the free list.
        """
        if way is not None:
            self.freeList[setNumber].append(way)
            return way
        else:
            index = 0
            minAccess = self.entries[setNumber][0].lastAccess
            for i,acc in enumerate(self.lastAccess[setNumber]):
                if i not in self.freeList[setNumber] and self.entries[setNumber][i].lastAccess < minAccess:
                    index = i
                    minAccess = self.lastAccess[setNumber][i]
            if index not in self.freeList[setNumber]:
                self.freeList[setNumber].append(index)
            return index

class ETLBEntry:
    

    def __init__(pageSize=0x1000, cacheLine=64):
        self.vtag = 0
        self.paddr = 0

        self.lastAccess = 0

        self.pageSize = pageSize
        self.cacheLine = cacheLine

        self.nEntries = self.pageSize // self.cacheLine

        self.valid = False
        self.location = [0] * self.nEntries
        self.way = [0] * self.nEntries

def test():
    L2 = Cache(size=0x100000, associativity=16)
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
            addr = int(line.split(' ')[1], 16)
            L1.access(addr, line[0]=='W', i >= skip + warmup)
        if i + 1 == skip + warmup + nLines and nLines != -1:
            break
    print("L1 hit:  %d (%0.3f)"%(L1.hit, L1.hit/(L1.counter-warmup)*100))
    print("L1 miss: %d (%0.3f)"%(L1.miss, L1.miss/(L1.counter-warmup)*100))
    print("L2 hit:  %d (%0.3f)"%(L2.hit, L2.hit/(L1.counter-warmup)*100))
    print("L2 miss: %d (%0.3f)"%(L2.miss, L2.miss/(L1.counter-warmup)*100))

if __name__ == '__main__':
    test()
